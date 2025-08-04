# app/worker.py
import asyncio
import redis.asyncio as redis
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
from decimal import Decimal

from sqlalchemy.orm import Session
from .config import settings
from .database import SessionLocal
from .models import GitHubEvent, AnomalyDetection, SecretDetection, TemporalPattern
from .anomaly_detection.stream_processor import AnomalyStreamProcessor
from .cache import cache_service

logger = logging.getLogger(__name__)

def make_json_serializable(obj):
    """Convert objects to JSON-serializable format with comprehensive type handling"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        # Handle nested dictionaries recursively
        result = {}
        for k, v in obj.items():
            # Ensure keys are strings
            key = str(k) if not isinstance(k, str) else k
            result[key] = make_json_serializable(v)
        return result
    if isinstance(obj, (list, tuple)):
        return [make_json_serializable(item) for item in obj]
    if isinstance(obj, set):
        return list(make_json_serializable(item) for item in obj)
    if hasattr(obj, '__dict__'):
        # Handle objects with attributes (convert to dict)
        return make_json_serializable(obj.__dict__)
    if hasattr(obj, 'tolist'):
        # Handle numpy arrays and similar objects
        try:
            return make_json_serializable(obj.tolist())
        except:
            pass
    if hasattr(obj, '__iter__') and not isinstance(obj, (str, bytes)):
        # Handle other iterable objects
        try:
            return [make_json_serializable(item) for item in obj]
        except:
            pass
    # For any other type, try to convert to string as fallback
    try:
        return str(obj)
    except:
        return f"<unserializable:{type(obj).__name__}>"

class QueueWorker:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.anomaly_processor = None  # Will be initialized in setup()
        
    async def setup(self):
        """Initialize Redis connection if not provided"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.redis_url)
        
        # Initialize cache service with the same Redis client
        cache_service.redis_client = self.redis_client
        
        # Initialize anomaly detection processor
        self.anomaly_processor = AnomalyStreamProcessor(
            redis_client=self.redis_client,
            websocket_manager=None,  # Will be set if needed
            github_token=getattr(settings, 'github_token', None),
            openai_api_key=getattr(settings, 'openai_api_key', None)
        )
        
    async def run(self):
        """Main worker loop with batch processing for better performance"""
        await self.setup()
        logger.info("Starting queue worker with batch processing")
        
        while True:
            try:
                # Process events in batches for better performance
                batch = await self.get_event_batch(batch_size=50, timeout=5)
                
                if batch:
                    logger.info(f"Processing batch of {len(batch)} events")
                    await self.process_event_batch(batch)
                    
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)
    
    async def get_event_batch(self, batch_size: int = 50, timeout: int = 5) -> List[Dict[str, Any]]:
        """Get a batch of events from the queue"""
        batch = []
        
        # Get first event with timeout
        result = await self.redis_client.brpop("event_queue", timeout=timeout)
        if not result:
            return batch
        
        _, data = result
        batch.append(json.loads(data))
        
        # Get additional events without timeout (non-blocking)
        for _ in range(batch_size - 1):
            try:
                result = await self.redis_client.rpop("event_queue")
                if result:
                    batch.append(json.loads(result))
                else:
                    break
            except Exception:
                break
        
        return batch
    
    async def process_event_batch(self, batch: List[Dict[str, Any]]):
        """Process a batch of events efficiently"""
        if not batch:
            return
            
        db = SessionLocal()
        try:
            # Group events by repo for more efficient processing
            events_by_repo = {}
            for event_data in batch:
                repo_name = event_data.get("repo_name", "unknown")
                if repo_name not in events_by_repo:
                    events_by_repo[repo_name] = []
                events_by_repo[repo_name].append(event_data)
            
            processed_count = 0
            anomaly_count = 0
            
            # Process each repository's events together
            for repo_name, repo_events in events_by_repo.items():
                try:
                    # Get all event IDs to fetch from database
                    event_ids = [e.get("event_id") for e in repo_events]
                    
                    # Fetch events from database in one query
                    db_events = db.query(GitHubEvent).filter(
                        GitHubEvent.id.in_(event_ids),
                        GitHubEvent.processed == False
                    ).all()
                    
                    if not db_events:
                        continue
                    
                    # Fast processing: Only run full anomaly detection on suspicious patterns
                    # For most events, just mark as processed
                    suspicious_events = []
                    normal_events = []
                    
                    for event in db_events:
                        # Quick heuristics to identify potentially suspicious events
                        if self.is_potentially_suspicious(event):
                            suspicious_events.append(event)
                        else:
                            normal_events.append(event)
                    
                    # Mark normal events as processed immediately
                    for event in normal_events:
                        event.processed = True
                        processed_count += 1
                    
                    # Only run expensive anomaly detection on suspicious events
                    if suspicious_events:
                        event_dicts = []
                        for event in suspicious_events:
                            event_dict = {
                                'id': event.id,
                                'type': event.type,
                                'actor': {'login': event.actor_login},
                                'repo': {'name': event.repo_name},
                                'created_at': event.created_at.isoformat(),
                                'payload': event.payload or {}
                            }
                            event_dicts.append(event_dict)
                        
                        # Run anomaly detection only on suspicious events
                        try:
                            anomaly_results = await self.anomaly_processor.process_event_stream(event_dicts)
                            anomaly_count += len(anomaly_results)
                            
                            # Store significant anomalies and broadcast them
                            for result in anomaly_results:
                                if result.get('final_anomaly_score', 0) > 0.3:
                                    await self.store_anomaly(result, db)
                                    # Broadcast high-priority anomalies immediately
                                    if result.get('severity_level') in ['CRITICAL', 'HIGH']:
                                        await self.broadcast_anomaly(result)
                        except Exception as e:
                            logger.warning(f"Anomaly detection failed for {repo_name}: {e}")
                        
                        # Mark suspicious events as processed
                        for event in suspicious_events:
                            event.processed = True
                            processed_count += 1
                
                except Exception as e:
                    logger.error(f"Error processing repo {repo_name}: {e}")
                    continue
            
            # Commit all changes at once
            db.commit()
            logger.info(f"Batch processed: {processed_count} events, {anomaly_count} anomalies detected")
            
            # Broadcast processing statistics for real-time dashboard updates
            if processed_count > 0:
                # Calculate suspicious events count properly
                suspicious_count = 0
                for repo_events in events_by_repo.values():
                    event_ids = [e.get("event_id") for e in repo_events]
                    repo_db_events = db.query(GitHubEvent).filter(GitHubEvent.id.in_(event_ids)).all()
                    suspicious_count += len([event for event in repo_db_events if self.is_potentially_suspicious(event)])
                
                await self.broadcast_processing_stats({
                    "events_processed": processed_count,
                    "anomalies_detected": anomaly_count,
                    "suspicious_events": suspicious_count,
                    "batch_size": len(batch),
                    "repositories_processed": len(events_by_repo),
                    "processing_timestamp": datetime.utcnow().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Error processing event batch: {e}")
            db.rollback()
        finally:
            db.close()
    
    def is_potentially_suspicious(self, event: GitHubEvent) -> bool:
        """Quick heuristics to identify potentially suspicious events without expensive analysis"""
        event_type = event.type
        payload = event.payload or {}
        
        # Always analyze these high-risk event types
        if event_type in ['DeleteEvent', 'ForkEvent', 'MemberEvent']:
            return True
        
        # Check for suspicious patterns in PushEvents
        if event_type == 'PushEvent':
            commits = payload.get('commits', [])
            if len(commits) > 10:  # Large number of commits
                return True
            
            # Check commit messages for suspicious keywords
            for commit in commits:
                message = commit.get('message', '').lower()
                if any(word in message for word in ['hack', 'exploit', 'backdoor', 'malware', 'virus']):
                    return True
        
        # Check for workflow failures
        if event_type == 'WorkflowRunEvent':
            conclusion = payload.get('workflow_run', {}).get('conclusion')
            if conclusion == 'failure':
                return True
        
        # Force pushes are always suspicious
        if event_type == 'PushEvent' and payload.get('forced'):
            return True
        
        # For now, analyze only ~10% of normal events to catch other patterns
        return hash(event.id) % 10 == 0
    
    async def store_anomaly(self, result: Dict[str, Any], db: Session):
        """Store anomaly detection result in database"""
        try:
            detection_scores = result.get('detection_scores', {})
            
            # Ensure all JSON fields are properly serialized
            anomaly_data = {
                'event_id': str(result.get('event_id', '')),
                'user_login': str(result.get('user_login', '')),
                'repository_name': str(result.get('repository_name', '')),
                'event_type': str(result.get('event_type', '')),
                'event_timestamp': datetime.fromisoformat(result['timestamp']) if result.get('timestamp') else datetime.utcnow(),
                'final_anomaly_score': float(result.get('final_anomaly_score', 0.0)),
                'severity_level': str(result.get('severity_level', 'LOW')),
                'severity_description': str(result.get('severity_description', '')),
                'behavioral_anomaly_score': float(detection_scores.get('behavioral', 0.0)),
                'content_risk_score': float(detection_scores.get('content', 0.0)),
                'temporal_anomaly_score': float(detection_scores.get('temporal', 0.0)),
                'repository_criticality_score': float(detection_scores.get('repository_criticality', 0.0)),
                # Use json.dumps to properly serialize dictionaries for PostgreSQL
                'detection_weights': json.dumps(make_json_serializable(result.get('detection_weights', {}))),
                'behavioral_analysis': json.dumps(make_json_serializable(result.get('behavioral_analysis', {}))),
                'content_analysis': json.dumps(make_json_serializable(result.get('content_analysis', {}))),
                'temporal_analysis': json.dumps(make_json_serializable(result.get('temporal_analysis', {}))),
                'repository_context': json.dumps(make_json_serializable(result.get('repository_context', {}))),
                'high_risk_indicators': json.dumps(make_json_serializable(result.get('high_risk_indicators', []))),
                'ai_summary': str(result.get('ai_summary', ''))
            }
            
            from .models import AnomalyDetection
            anomaly = AnomalyDetection(**anomaly_data)
            db.add(anomaly)
            
        except Exception as e:
            logger.error(f"Error storing anomaly for event {result.get('event_id')}: {e}")
    
    async def broadcast_processing_stats(self, stats: Dict[str, Any]):
        """Broadcast processing statistics for real-time dashboard updates"""
        try:
            await self.redis_client.publish("processing_stats", json.dumps({
                "type": "processing_stats",
                "data": stats
            }))
            
            # Also broadcast individual events processed for live feed
            await self.redis_client.publish("events_processed", json.dumps({
                "type": "batch_processed",
                "data": stats
            }))
        except Exception as e:
            logger.error(f"Error broadcasting processing stats: {e}")
    
    async def process_event(self, event_data: Dict[str, Any]):
        """Process a single event with new anomaly detection system"""
        db = SessionLocal()
        try:
            # Get recent events for this repo that don't already belong to incidents
            repo_name = event_data.get("repo_name")
            time_window = datetime.now() - timedelta(minutes=30)
            
            recent_events = db.query(GitHubEvent).filter(
                GitHubEvent.repo_name == repo_name,
                GitHubEvent.created_at > time_window,
                GitHubEvent.incident_id.is_(None)  # Only unassigned events
            ).order_by(GitHubEvent.created_at.desc()).all()
            
            if not recent_events:
                logger.debug(f"No unassigned recent events for {repo_name}")
                return
            
            # Convert SQLAlchemy events to dict format for anomaly detection
            event_dicts = []
            for event in recent_events:
                event_dict = {
                    'id': event.id,
                    'type': event.type,
                    'actor': {
                        'login': event.actor_login
                    },
                    'repo': {
                        'name': event.repo_name
                    },
                    'created_at': event.created_at.isoformat(),
                    'payload': event.payload or {}
                }
                event_dicts.append(event_dict)
            
            # Process events through anomaly detection system
            anomaly_results = await self.anomaly_processor.process_event_stream(event_dicts)
            
            # Store anomaly detection results
            stored_anomalies = []
            high_severity_anomalies = []
            
            for result in anomaly_results:
                if result.get('final_anomaly_score', 0) > 0.3:  # Only store significant anomalies
                    # Store anomaly detection record with JSON-serialized fields
                    try:
                        # Safely extract detection scores with defaults
                        detection_scores = result.get('detection_scores', {})
                        
                        # Ensure all required fields exist with proper types
                        anomaly_data = {
                            'event_id': str(result.get('event_id', '')),
                            'user_login': str(result.get('user_login', '')),
                            'repository_name': str(result.get('repository_name', '')),
                            'event_type': str(result.get('event_type', '')),
                            'event_timestamp': datetime.fromisoformat(result['timestamp']) if result.get('timestamp') else datetime.utcnow(),
                            'final_anomaly_score': float(result.get('final_anomaly_score', 0.0)),
                            'severity_level': str(result.get('severity_level', 'LOW')),
                            'severity_description': str(result.get('severity_description', '')),
                            'behavioral_anomaly_score': float(detection_scores.get('behavioral', 0.0)),
                            'content_risk_score': float(detection_scores.get('content', 0.0)),
                            'temporal_anomaly_score': float(detection_scores.get('temporal', 0.0)),
                            'repository_criticality_score': float(detection_scores.get('repository_criticality', 0.0)),
                            'detection_weights': make_json_serializable(result.get('detection_weights', {})),
                            'behavioral_analysis': make_json_serializable(result.get('behavioral_analysis', {})),
                            'content_analysis': make_json_serializable(result.get('content_analysis', {})),
                            'temporal_analysis': make_json_serializable(result.get('temporal_analysis', {})),
                            'repository_context': make_json_serializable(result.get('repository_context', {})),
                            'high_risk_indicators': make_json_serializable(result.get('high_risk_indicators', [])),
                            'ai_summary': make_json_serializable(result.get('ai_summary', ''))
                        }
                        
                        anomaly = AnomalyDetection(**anomaly_data)
                        
                    except (ValueError, KeyError, TypeError) as e:
                        logger.error(f"Error creating anomaly object for event {result.get('event_id')}: {e}")
                        logger.error(f"Result keys: {list(result.keys())}")
                        logger.error(f"Detection scores: {result.get('detection_scores', 'Missing')}")
                        logger.error(f"Problematic result data types: {[(k, type(v).__name__) for k, v in result.items()]}")
                        continue
                    except Exception as e:
                        logger.error(f"Unexpected error creating anomaly object for event {result.get('event_id')}: {e}")
                        continue
                    db.add(anomaly)
                    stored_anomalies.append(anomaly)
                    
                    # Track high severity anomalies for backward compatibility
                    if result['severity_level'] in ['CRITICAL', 'HIGH']:
                        high_severity_anomalies.append(result)
            
            # Broadcast high-severity anomalies directly via WebSocket
            if high_severity_anomalies:
                for anomaly in high_severity_anomalies:
                    await self.broadcast_anomaly(anomaly)
            
            # Mark events as processed
            for event in recent_events:
                event.processed = True
            
            db.commit()
            
            # Invalidate relevant caches
            if stored_anomalies or high_severity_anomalies:
                invalidated_count = await cache_service.invalidate_all()
                logger.info(f"Processed {len(stored_anomalies)} anomalies, {len(high_severity_anomalies)} high-severity")
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            db.rollback()
        finally:
            db.close()
    
    async def broadcast_anomaly(self, anomaly: dict):
        """Broadcast anomaly to all clients via WebSocket channels"""
        try:
            # Send to general anomaly channel
            await self.redis_client.publish("anomalies", json.dumps({
                "type": "anomaly_detected",
                "data": anomaly
            }))
            
            # Send to severity-specific channel
            severity_level = anomaly.get('severity_level', 'INFO').lower()
            await self.redis_client.publish(f"anomalies_{severity_level}", json.dumps({
                "type": "severity_anomaly",
                "severity": anomaly.get('severity_level'),
                "data": anomaly
            }))
            
            logger.info(f"Broadcast anomaly {anomaly['event_id']} with severity {anomaly['severity_level']}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast anomaly: {e}")