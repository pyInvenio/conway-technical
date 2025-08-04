# app/poller.py
import aiohttp
import asyncio
import redis.asyncio as redis
from datetime import datetime, timedelta
import json
import logging
from typing import List, Dict, Any, Optional
import random
import math

from .config import settings
from .database import SessionLocal
from .models import GitHubEvent

logger = logging.getLogger(__name__)

class RateLimitManager:
    """Distributed rate limit manager using Redis for coordination"""
    
    def __init__(self, redis_client, safety_margin: int = 500):
        self.redis_client = redis_client
        self.safety_margin = safety_margin
        self.rate_limit_key = "github:rate_limit"
        self.circuit_breaker_key = "github:circuit_breaker"
        self.semaphore_key = "github:api_semaphore"
        self.max_concurrent_requests = 3  # Limit concurrent API calls
        
    async def acquire_api_slot(self, timeout: int = 30) -> bool:
        """Acquire a slot for making API request with distributed coordination"""
        # Check circuit breaker first
        circuit_state = await self.redis_client.get(self.circuit_breaker_key)
        if circuit_state == "open":
            logger.warning("Circuit breaker is open, skipping API request")
            return False
            
        # Try to acquire semaphore slot
        current_slots = await self.redis_client.scard(self.semaphore_key)
        if current_slots >= self.max_concurrent_requests:
            logger.debug(f"All API slots occupied ({current_slots}/{self.max_concurrent_requests})")
            return False
            
        # Check distributed rate limit
        rate_limit_data = await self.redis_client.hgetall(self.rate_limit_key)
        if rate_limit_data:
            remaining = int(rate_limit_data.get("remaining", 5000))
            reset_timestamp = int(rate_limit_data.get("reset", 0))
            
            if remaining < self.safety_margin:
                reset_time = datetime.fromtimestamp(reset_timestamp)
                if datetime.now() < reset_time:
                    logger.warning(f"Rate limit too low: {remaining} remaining, waiting until reset at {reset_time}")
                    return False
        
        # Acquire semaphore slot
        slot_id = f"slot_{random.randint(1000, 9999)}"
        await self.redis_client.sadd(self.semaphore_key, slot_id)
        await self.redis_client.expire(self.semaphore_key, 300)  # 5 minute timeout
        return True
    
    async def release_api_slot(self):
        """Release API slot after request completes"""
        # Remove one slot (Redis will handle which one)
        await self.redis_client.spop(self.semaphore_key)
    
    async def update_rate_limit(self, remaining: int, reset_timestamp: int):
        """Update shared rate limit information"""
        await self.redis_client.hset(self.rate_limit_key, mapping={
            "remaining": remaining,
            "reset": reset_timestamp,
            "updated_at": int(datetime.now().timestamp())
        })
        await self.redis_client.expire(self.rate_limit_key, 3700)  # Slightly longer than 1 hour
        
        # Manage circuit breaker
        if remaining < 50:  # Very low rate limit
            await self.redis_client.setex(self.circuit_breaker_key, 1800, "open")  # 30 minutes
            logger.warning("Circuit breaker opened due to very low rate limit")
        elif remaining > 1000:  # Rate limit recovered
            await self.redis_client.delete(self.circuit_breaker_key)
    
    async def get_shared_rate_limit(self) -> tuple[int, datetime]:
        """Get current shared rate limit information"""
        rate_limit_data = await self.redis_client.hgetall(self.rate_limit_key)
        if rate_limit_data:
            remaining = int(rate_limit_data.get("remaining", 5000))
            reset_timestamp = int(rate_limit_data.get("reset", 0))
            reset_time = datetime.fromtimestamp(reset_timestamp) if reset_timestamp else datetime.now() + timedelta(hours=1)
            return remaining, reset_time
        return 5000, datetime.now() + timedelta(hours=1)


class GitHubPoller:
    def __init__(self, github_token: str):
        self.github_token = github_token
        self.redis_client = None
        self.rate_limiter = None
        self.backoff_until = None
        self.last_etag = None  # For conditional requests
        self.max_pages_per_cycle = 3  # Reduced from 10 to 3 for better rate limit management
        self.consecutive_failures = 0
        self.poller_id = f"poller_{self.github_token[:8]}_{random.randint(1000, 9999)}"
        
    async def setup(self):
        """Initialize Redis connection and rate limiter"""
        self.redis_client = await redis.from_url(settings.redis_url)
        self.rate_limiter = RateLimitManager(self.redis_client, safety_margin=500)
        
    async def run(self):
        """Main polling loop with improved rate limiting and coordination"""
        await self.setup()
        logger.info(f"Starting poller {self.poller_id}...")
        
        while True:
            try:
                # Check if we're in local backoff
                if self.backoff_until and datetime.now() < self.backoff_until:
                    wait_seconds = (self.backoff_until - datetime.now()).total_seconds()
                    logger.debug(f"In backoff for {wait_seconds:.1f}s")
                    await asyncio.sleep(min(wait_seconds, 60))  # Cap wait time
                    continue
                
                # Try to acquire API slot with distributed coordination
                if not await self.rate_limiter.acquire_api_slot():
                    # Wait with jitter before retrying
                    wait_time = 30 + random.uniform(0, 30)
                    logger.debug(f"No API slot available, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
                    continue
                
                try:
                    # Fetch events with smart pagination and rate limiting
                    all_events = await self.fetch_paginated_events()
                    
                    if all_events:
                        await self.process_events(all_events)
                        self.consecutive_failures = 0
                    else:
                        # No events or conditional request returned 304
                        logger.debug("No new events to process")
                
                finally:
                    # Always release the API slot
                    await self.rate_limiter.release_api_slot()
                
                # Smart sleep timing based on shared rate limit state
                remaining, reset_time = await self.rate_limiter.get_shared_rate_limit()
                sleep_time = self._calculate_sleep_time(remaining, reset_time)
                
                logger.info(f"Poller {self.poller_id}: {remaining} rate limit remaining, sleeping {sleep_time}s")
                await asyncio.sleep(sleep_time)
                
            except Exception as e:
                self.consecutive_failures += 1
                backoff_time = min(30 * (2 ** self.consecutive_failures), 1800)  # Max 30 minutes
                logger.error(f"Poller {self.poller_id} error (failure #{self.consecutive_failures}): {e}, backing off {backoff_time}s")
                await asyncio.sleep(backoff_time)
    
    def _calculate_sleep_time(self, remaining: int, reset_time: datetime) -> int:
        """Calculate optimal sleep time based on rate limit status"""
        if remaining < 100:
            # Very low - wait longer
            return 300  # 5 minutes
        elif remaining < 500:
            # Low - moderate wait
            return 120  # 2 minutes
        elif remaining < 1000:
            # Getting low - short wait
            return 60   # 1 minute
        elif remaining < 2000:
            # Medium - brief wait
            return 30   # 30 seconds
        else:
            # High rate limit - minimum wait to be courteous
            return 15   # 15 seconds
    
    async def fetch_paginated_events(self) -> List[Dict[str, Any]]:
        """Fetch events from GitHub API with smart pagination and duplicate detection"""
        all_events = []
        seen_event_ids = set()
        duplicate_count = 0
        max_duplicates = 10  # Stop if we hit this many duplicates in a row
        
        for page in range(1, self.max_pages_per_cycle + 1):
            # Check shared rate limit before each request
            remaining, _ = await self.rate_limiter.get_shared_rate_limit()
            if remaining < 50:  # More conservative threshold
                logger.warning(f"Shared rate limit too low ({remaining}), stopping pagination at page {page}")
                break
                
            events = await self.fetch_events_page(page)
            if not events:
                # No more events or error occurred
                break
                
            # Smart duplicate detection
            new_events_in_page = 0
            for event in events:
                event_id = event.get('id')
                if event_id and event_id not in seen_event_ids:
                    all_events.append(event)
                    seen_event_ids.add(event_id)
                    new_events_in_page += 1
                else:
                    duplicate_count += 1
            
            logger.debug(f"Page {page}: {new_events_in_page} new events, {len(events) - new_events_in_page} duplicates")
            
            # Stop if we're hitting too many duplicates (indicates we've caught up)
            if duplicate_count >= max_duplicates:
                logger.info(f"Stopping pagination due to {duplicate_count} consecutive duplicates - likely caught up")
                break
                
            # If we got less than 100 events, we've reached the end
            if len(events) < 100:
                logger.debug(f"Reached end of events at page {page} ({len(events)} events)")
                break
                
            # Adaptive pause between requests based on rate limit
            remaining, _ = await self.rate_limiter.get_shared_rate_limit()
            pause_time = 0.5 if remaining > 1000 else 1.0 if remaining > 500 else 2.0
            await asyncio.sleep(pause_time)
        
        logger.info(f"Smart pagination: {len(all_events)} unique events across {page} pages, {duplicate_count} duplicates found")
        return all_events
    
    async def fetch_events_page(self, page: int = 1) -> List[Dict[str, Any]]:
        """Fetch a single page of events from GitHub API"""
        headers = {
            "Authorization": f"token {self.github_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHubMonitor/1.0"
        }
        
        # Add conditional request headers for efficiency
        if page == 1 and self.last_etag:
            headers["If-None-Match"] = self.last_etag
        
        params = {
            "per_page": 100,  # Maximum allowed
            "page": page
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/events",
                headers=headers,
                params=params
            ) as response:
                # Update shared rate limit info
                remaining = int(response.headers.get("X-RateLimit-Remaining", 0))
                reset_timestamp = int(response.headers.get("X-RateLimit-Reset", 0))
                
                # Update distributed rate limit tracking
                await self.rate_limiter.update_rate_limit(remaining, reset_timestamp)
                
                # Log rate limit status on first page
                if page == 1:
                    reset_time = datetime.fromtimestamp(reset_timestamp) if reset_timestamp else datetime.now()
                    logger.info(f"Updated shared rate limit: {remaining} remaining, resets at {reset_time}")
                
                # Handle rate limiting with improved backoff and circuit breaker
                if response.status in (403, 429):
                    # Update rate limit to trigger circuit breaker
                    await self.rate_limiter.update_rate_limit(0, reset_timestamp or int((datetime.now() + timedelta(hours=1)).timestamp()))
                    
                    # Calculate jittered exponential backoff based on consecutive failures
                    base_backoff = 60 * (2 ** min(self.consecutive_failures, 6))  # Max ~1 hour base
                    jitter = random.uniform(0.5, 1.5)  # 50% jitter
                    backoff_seconds = min(base_backoff * jitter, 3600)  # Cap at 1 hour
                    
                    self.backoff_until = datetime.now() + timedelta(seconds=backoff_seconds)
                    self.consecutive_failures += 1
                    
                    logger.warning(f"Rate limited (status {response.status}), failure #{self.consecutive_failures}, backing off for {backoff_seconds:.1f}s")
                    return []
                
                # Handle conditional request (no new data)
                if response.status == 304:
                    logger.info("No new events (304 Not Modified)")
                    return []
                
                if response.status == 200:
                    # Store etag for future conditional requests
                    if page == 1:
                        self.last_etag = response.headers.get("ETag")
                    
                    events = await response.json()
                    logger.debug(f"Fetched {len(events)} events from page {page}")
                    return events
                
                logger.error(f"GitHub API returned status {response.status} for page {page}")
                return []
    
    async def process_events(self, events: List[Dict[str, Any]]):
        """Process and store events with smart filtering and priority scoring"""
        # Classify events by priority and value
        high_priority_types = {
            "PushEvent", "WorkflowRunEvent", "DeleteEvent", 
            "MemberEvent", "ReleaseEvent"  # Critical security/operational events
        }
        
        medium_priority_types = {
            "PullRequestEvent", "IssuesEvent", "CreateEvent", 
            "ForkEvent"  # Development activity events
        }
        
        low_priority_types = {
            "WatchEvent", "StarEvent"  # Low signal, high noise events  
        }
        
        # Skip completely uninteresting event types
        skip_types = {
            "FollowEvent", "GollumEvent", "CommitCommentEvent",
            "IssueCommentEvent", "PullRequestReviewCommentEvent",
            "PullRequestReviewEvent"  # Too noisy for security monitoring
        }
        
        db = SessionLocal()
        try:
            new_events_count = 0
            processed_events = []
            skipped_events = 0
            
            for event in events:
                event_type = event["type"]
                
                # Skip uninteresting events entirely
                if event_type in skip_types:
                    skipped_events += 1
                    continue
                
                # Apply smart filtering logic
                should_store = False
                if event_type in high_priority_types:
                    should_store = True  # Always store high priority events
                elif event_type in medium_priority_types:
                    should_store = True  # Store medium priority events  
                elif event_type in low_priority_types:
                    # Only store 20% of low priority events to reduce noise
                    should_store = random.random() < 0.2
                else:
                    # Unknown event type - store occasionally for analysis
                    should_store = random.random() < 0.1
                    if should_store:
                        logger.info(f"Storing unknown event type for analysis: {event_type}")
                
                if not should_store:
                    skipped_events += 1
                    continue
                
                try:
                    # Create event object with reduced payload storage for efficiency
                    payload = event["payload"]
                    raw_response = None
                    
                    # Only store full raw_response for high priority events
                    if event_type in high_priority_types:
                        raw_response = event
                    
                    # Compress payload for medium/low priority events
                    if event_type not in high_priority_types:
                        # Store only essential payload fields to reduce storage
                        if event_type == "PushEvent":
                            payload = {
                                "commits": payload.get("commits", [])[:10],  # Limit to 10 commits
                                "size": payload.get("size", 0),
                                "ref": payload.get("ref", ""),
                                "head": payload.get("head", ""),
                                "before": payload.get("before", "")
                            }
                        elif event_type == "PullRequestEvent":
                            pr = payload.get("pull_request", {})
                            payload = {
                                "action": payload.get("action", ""),
                                "number": pr.get("number"),
                                "state": pr.get("state"),
                                "title": pr.get("title", "")[:200],  # Truncate title
                                "merged": pr.get("merged", False)
                            }
                    
                    db_event = GitHubEvent(
                        id=event["id"],
                        type=event_type,
                        repo_name=event["repo"]["name"],
                        actor_login=event["actor"]["login"],
                        created_at=datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")),
                        payload=payload,
                        raw_response=raw_response,  # Only store for high priority events
                        processed=False
                    )
                    
                    # Use merge to handle duplicates gracefully
                    db.merge(db_event)
                    processed_events.append(event)
                    new_events_count += 1
                    
                except Exception as event_error:
                    # Log individual event errors but continue processing
                    logger.warning(f"Error processing event {event.get('id', 'unknown')}: {event_error}")
                    continue
            
            # Commit all events at once
            if processed_events:
                db.commit()
                logger.info(f"Successfully processed {new_events_count} events")
                
                # Queue events for further processing after successful DB commit
                for event in processed_events:
                    try:
                        await self.redis_client.lpush(
                            "event_queue",
                            json.dumps({
                                "event_id": event["id"],
                                "type": event["type"],
                                "repo_name": event["repo"]["name"]
                            })
                        )
                    except Exception as redis_error:
                        logger.warning(f"Failed to queue event {event['id']} for processing: {redis_error}")
            else:
                logger.info("No new events to process")
            
        except Exception as e:
            logger.error(f"Error processing events batch: {e}")
            db.rollback()
            
            # Fallback: try processing events one by one
            logger.info("Attempting individual event processing as fallback...")
            await self._process_events_individually(events, interesting_types)
            
        finally:
            db.close()
    
    async def _process_events_individually(self, events: List[Dict[str, Any]], interesting_types: set):
        """Fallback method to process events one by one to handle edge cases"""
        successful_count = 0
        
        for event in events:
            if event["type"] not in interesting_types:
                continue
                
            db = SessionLocal()
            try:
                # Check if event already exists
                existing = db.query(GitHubEvent).filter_by(id=event["id"]).first()
                if existing:
                    logger.debug(f"Event {event['id']} already exists, skipping")
                    continue
                
                # Create and save event
                db_event = GitHubEvent(
                    id=event["id"],
                    type=event["type"],
                    repo_name=event["repo"]["name"],
                    actor_login=event["actor"]["login"],
                    created_at=datetime.fromisoformat(event["created_at"].replace("Z", "+00:00")),
                    payload=event["payload"],
                    raw_response=event,
                    processed=False
                )
                
                db.add(db_event)
                db.commit()
                successful_count += 1
                
                # Queue for processing
                try:
                    await self.redis_client.lpush(
                        "event_queue",
                        json.dumps({
                            "event_id": event["id"],
                            "type": event["type"],
                            "repo_name": event["repo"]["name"]
                        })
                    )
                except Exception as redis_error:
                    logger.warning(f"Failed to queue event {event['id']}: {redis_error}")
                
            except Exception as e:
                logger.warning(f"Failed to process individual event {event.get('id', 'unknown')}: {e}")
                db.rollback()
            finally:
                db.close()
        
        if successful_count > 0:
            logger.info(f"Fallback processing completed: {successful_count} events processed individually")