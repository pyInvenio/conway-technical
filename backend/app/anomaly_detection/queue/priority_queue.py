from typing import Dict, Any, List, Optional, Tuple
import json
import logging
import asyncio
from datetime import datetime, timedelta
import redis.asyncio as redis

from ..models.anomaly_score import SeverityLevel

logger = logging.getLogger(__name__)

class AnomalyPriorityQueue:
    """Redis-based priority queue for anomaly processing with severity-based routing"""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis_client = redis_client
        
        # Queue configurations
        self.queue_names = {
            SeverityLevel.CRITICAL: 'anomaly_queue:critical',
            SeverityLevel.HIGH: 'anomaly_queue:high', 
            SeverityLevel.MEDIUM: 'anomaly_queue:medium',
            SeverityLevel.LOW: 'anomaly_queue:low',
            SeverityLevel.INFO: 'anomaly_queue:info'
        }
        
        # Processing configuration
        self.max_queue_size = {
            SeverityLevel.CRITICAL: 1000,
            SeverityLevel.HIGH: 2000,
            SeverityLevel.MEDIUM: 5000,
            SeverityLevel.LOW: 10000,
            SeverityLevel.INFO: 20000
        }
        
        # TTL for different severity levels (seconds)
        self.queue_ttl = {
            SeverityLevel.CRITICAL: 3600,      # 1 hour
            SeverityLevel.HIGH: 7200,          # 2 hours
            SeverityLevel.MEDIUM: 14400,       # 4 hours
            SeverityLevel.LOW: 28800,          # 8 hours
            SeverityLevel.INFO: 86400          # 24 hours
        }
        
        # Score multipliers for priority calculation
        self.severity_multipliers = {
            SeverityLevel.CRITICAL: 1000000,
            SeverityLevel.HIGH: 100000,
            SeverityLevel.MEDIUM: 10000,
            SeverityLevel.LOW: 1000,
            SeverityLevel.INFO: 100
        }
        
        # Metadata keys
        self.metadata_key = 'anomaly_queue:metadata'
        self.stats_key = 'anomaly_queue:stats'
    
    async def enqueue_anomaly(
        self, 
        anomaly_data: Dict[str, Any], 
        severity_level: SeverityLevel,
        priority_boost: float = 0.0
    ) -> bool:
        """Enqueue an anomaly with appropriate priority"""
        
        try:
            queue_name = self.queue_names[severity_level]
            
            # Check queue size limits
            current_size = await self.redis_client.zcard(queue_name)
            if current_size >= self.max_queue_size[severity_level]:
                # Remove oldest items to make space
                await self._cleanup_old_items(queue_name, severity_level)
            
            # Calculate priority score
            priority_score = self._calculate_priority_score(
                anomaly_data, severity_level, priority_boost
            )
            
            # Prepare queue item
            queue_item = {
                'id': anomaly_data.get('event_id', f"anomaly_{datetime.utcnow().timestamp()}"),
                'data': anomaly_data,
                'severity': severity_level.name,
                'enqueued_at': datetime.utcnow().isoformat(),
                'priority_score': priority_score,
                'processing_attempts': 0,
                'ttl': self.queue_ttl[severity_level]
            }
            
            # Add to Redis sorted set
            await self.redis_client.zadd(
                queue_name,
                {json.dumps(queue_item): priority_score}
            )
            
            # Set expiration on the queue
            await self.redis_client.expire(queue_name, self.queue_ttl[severity_level])
            
            # Update metadata
            await self._update_queue_metadata(severity_level, 'enqueued')
            
            logger.debug(f"Enqueued anomaly {queue_item['id']} with priority {priority_score}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to enqueue anomaly: {e}")
            return False
    
    async def dequeue_anomaly(
        self, 
        severity_levels: List[SeverityLevel] = None,
        timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """Dequeue highest priority anomaly from specified severity levels"""
        
        if severity_levels is None:
            # Default priority order: Critical -> High -> Medium -> Low -> Info
            severity_levels = [
                SeverityLevel.CRITICAL,
                SeverityLevel.HIGH,
                SeverityLevel.MEDIUM,
                SeverityLevel.LOW,
                SeverityLevel.INFO
            ]
        
        try:
            # Check each severity level in order
            for severity_level in severity_levels:
                queue_name = self.queue_names[severity_level]
                
                # Get highest priority item (ZREVRANGE gets highest scores first)
                items = await self.redis_client.zrevrange(
                    queue_name, 0, 0, withscores=True
                )
                
                if items:
                    item_data, priority_score = items[0]
                    
                    # Remove from queue
                    await self.redis_client.zrem(queue_name, item_data)
                    
                    # Parse item
                    queue_item = json.loads(item_data)
                    queue_item['dequeued_at'] = datetime.utcnow().isoformat()
                    queue_item['processing_attempts'] += 1
                    
                    # Update metadata
                    await self._update_queue_metadata(severity_level, 'dequeued')
                    
                    logger.debug(f"Dequeued anomaly {queue_item['id']} from {severity_level.name}")
                    return queue_item
            
            # No items found in any queue
            return None
            
        except Exception as e:
            logger.error(f"Failed to dequeue anomaly: {e}")
            return None
    
    async def peek_queue(
        self, 
        severity_level: SeverityLevel, 
        count: int = 10
    ) -> List[Dict[str, Any]]:
        """Peek at top items in a queue without removing them"""
        
        try:
            queue_name = self.queue_names[severity_level]
            
            # Get top items with scores
            items = await self.redis_client.zrevrange(
                queue_name, 0, count - 1, withscores=True
            )
            
            result = []
            for item_data, priority_score in items:
                queue_item = json.loads(item_data)
                queue_item['current_priority_score'] = priority_score
                result.append(queue_item)
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to peek queue {severity_level.name}: {e}")
            return []
    
    async def get_queue_stats(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics"""
        
        try:
            stats = {
                'timestamp': datetime.utcnow().isoformat(),
                'queues': {},
                'total_items': 0,
                'processing_stats': await self._get_processing_stats()
            }
            
            # Get stats for each severity level
            for severity_level, queue_name in self.queue_names.items():
                queue_size = await self.redis_client.zcard(queue_name)
                
                # Get oldest and newest items
                oldest_items = await self.redis_client.zrange(queue_name, 0, 0, withscores=True)
                newest_items = await self.redis_client.zrevrange(queue_name, 0, 0, withscores=True)
                
                oldest_timestamp = None
                newest_timestamp = None
                
                if oldest_items:
                    oldest_item = json.loads(oldest_items[0][0])
                    oldest_timestamp = oldest_item.get('enqueued_at')
                
                if newest_items:
                    newest_item = json.loads(newest_items[0][0])
                    newest_timestamp = newest_item.get('enqueued_at')
                
                stats['queues'][severity_level.name] = {
                    'size': queue_size,
                    'max_size': self.max_queue_size[severity_level],
                    'utilization': queue_size / self.max_queue_size[severity_level],
                    'oldest_item': oldest_timestamp,
                    'newest_item': newest_timestamp,
                    'ttl_seconds': self.queue_ttl[severity_level]
                }
                
                stats['total_items'] += queue_size
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return {'error': str(e)}
    
    async def cleanup_expired_items(self) -> Dict[str, int]:
        """Clean up expired items from all queues"""
        
        cleanup_stats = {}
        current_time = datetime.utcnow()
        
        try:
            for severity_level, queue_name in self.queue_names.items():
                ttl_seconds = self.queue_ttl[severity_level]
                cutoff_time = current_time - timedelta(seconds=ttl_seconds)
                
                # Get all items
                all_items = await self.redis_client.zrange(queue_name, 0, -1)
                
                expired_items = []
                for item_data in all_items:
                    try:
                        queue_item = json.loads(item_data)
                        enqueued_at = datetime.fromisoformat(queue_item['enqueued_at'])
                        
                        if enqueued_at < cutoff_time:
                            expired_items.append(item_data)
                    except (json.JSONDecodeError, ValueError, KeyError):
                        # Malformed item, mark for removal
                        expired_items.append(item_data)
                
                # Remove expired items
                if expired_items:
                    await self.redis_client.zrem(queue_name, *expired_items)
                
                cleanup_stats[severity_level.name] = len(expired_items)
            
            logger.info(f"Cleaned up expired items: {cleanup_stats}")
            return cleanup_stats
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired items: {e}")
            return {}
    
    async def requeue_failed_item(
        self, 
        queue_item: Dict[str, Any], 
        delay_seconds: int = 60,
        max_attempts: int = 3
    ) -> bool:
        """Requeue a failed item with delay and attempt tracking"""
        
        try:
            attempts = queue_item.get('processing_attempts', 0)
            
            # Check if max attempts exceeded
            if attempts >= max_attempts:
                await self._move_to_dead_letter_queue(queue_item)
                return False
            
            # Update item metadata
            queue_item['processing_attempts'] = attempts + 1
            queue_item['last_failed_at'] = datetime.utcnow().isoformat()
            queue_item['requeue_delay'] = delay_seconds
            
            # Reduce priority slightly for failed items
            original_priority = queue_item.get('priority_score', 0)
            new_priority = original_priority * 0.9  # 10% reduction
            
            # Determine severity level
            severity_level = SeverityLevel[queue_item.get('severity', 'MEDIUM')]
            queue_name = self.queue_names[severity_level]
            
            # Schedule requeue after delay
            await asyncio.sleep(delay_seconds)
            
            # Re-add to queue
            await self.redis_client.zadd(
                queue_name,
                {json.dumps(queue_item): new_priority}
            )
            
            logger.info(f"Requeued failed item {queue_item['id']} after {delay_seconds}s delay")
            return True
            
        except Exception as e:
            logger.error(f"Failed to requeue item: {e}")
            return False
    
    async def _move_to_dead_letter_queue(self, queue_item: Dict[str, Any]):
        """Move item to dead letter queue for manual inspection"""
        
        try:
            dead_letter_queue = 'anomaly_queue:dead_letter'
            
            queue_item['moved_to_dlq_at'] = datetime.utcnow().isoformat()
            queue_item['reason'] = 'max_attempts_exceeded'
            
            # Add to dead letter queue with low priority
            await self.redis_client.zadd(
                dead_letter_queue,
                {json.dumps(queue_item): 1}
            )
            
            # Set TTL on dead letter queue (7 days)
            await self.redis_client.expire(dead_letter_queue, 7 * 24 * 3600)
            
            logger.warning(f"Moved item {queue_item['id']} to dead letter queue")
            
        except Exception as e:
            logger.error(f"Failed to move item to dead letter queue: {e}")
    
    def _calculate_priority_score(
        self, 
        anomaly_data: Dict[str, Any], 
        severity_level: SeverityLevel, 
        priority_boost: float = 0.0
    ) -> float:
        """Calculate priority score for queue ordering"""
        
        # Base score from severity level
        base_score = self.severity_multipliers[severity_level]
        
        # Add anomaly score component
        anomaly_score = anomaly_data.get('final_anomaly_score', 0.0)
        anomaly_component = anomaly_score * 1000
        
        # Add timestamp component (newer items get higher priority)
        timestamp = datetime.utcnow().timestamp()
        timestamp_component = timestamp / 1000  # Scale down
        
        # Add repository criticality component
        repo_criticality = anomaly_data.get('detection_scores', {}).get('repository_criticality', 0.0)
        criticality_component = repo_criticality * 100
        
        # Add user priority boost (for VIP users, etc.)
        user_boost = priority_boost * 50
        
        # Calculate final priority score
        priority_score = (
            base_score + 
            anomaly_component + 
            timestamp_component + 
            criticality_component + 
            user_boost
        )
        
        return priority_score
    
    async def _cleanup_old_items(self, queue_name: str, severity_level: SeverityLevel):
        """Remove oldest items when queue is full"""
        
        try:
            # Calculate how many items to remove (10% of max size)
            items_to_remove = max(1, self.max_queue_size[severity_level] // 10)
            
            # Get lowest priority items (oldest)
            old_items = await self.redis_client.zrange(queue_name, 0, items_to_remove - 1)
            
            if old_items:
                # Remove old items
                await self.redis_client.zrem(queue_name, *old_items)
                logger.info(f"Removed {len(old_items)} old items from {severity_level.name} queue")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old items: {e}")
    
    async def _update_queue_metadata(self, severity_level: SeverityLevel, operation: str):
        """Update queue operation metadata"""
        
        try:
            metadata_key = f"{self.metadata_key}:{severity_level.name}"
            current_time = datetime.utcnow().isoformat()
            
            # Update operation counters
            await self.redis_client.hincrby(metadata_key, f"{operation}_count", 1)
            await self.redis_client.hset(metadata_key, f"last_{operation}_at", current_time)
            
            # Set TTL on metadata
            await self.redis_client.expire(metadata_key, 86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Failed to update queue metadata: {e}")
    
    async def _get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics from metadata"""
        
        try:
            stats = {
                'total_enqueued': 0,
                'total_dequeued': 0,
                'by_severity': {}
            }
            
            for severity_level in SeverityLevel:
                metadata_key = f"{self.metadata_key}:{severity_level.name}"
                metadata = await self.redis_client.hgetall(metadata_key)
                
                enqueued_count = int(metadata.get('enqueued_count', 0))
                dequeued_count = int(metadata.get('dequeued_count', 0))
                
                stats['total_enqueued'] += enqueued_count
                stats['total_dequeued'] += dequeued_count
                
                stats['by_severity'][severity_level.name] = {
                    'enqueued': enqueued_count,
                    'dequeued': dequeued_count,
                    'last_enqueued_at': metadata.get('last_enqueued_at'),
                    'last_dequeued_at': metadata.get('last_dequeued_at')
                }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get processing stats: {e}")
            return {}
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the priority queue system"""
        
        try:
            # Test Redis connection
            await self.redis_client.ping()
            
            # Get queue sizes
            queue_sizes = {}
            for severity_level, queue_name in self.queue_names.items():
                queue_sizes[severity_level.name] = await self.redis_client.zcard(queue_name)
            
            # Check for any oversized queues
            health_status = 'healthy'
            issues = []
            
            for severity_level, size in queue_sizes.items():
                max_size = self.max_queue_size[SeverityLevel[severity_level]]
                if size >= max_size * 0.9:  # 90% full
                    health_status = 'warning'
                    issues.append(f"{severity_level} queue is {size}/{max_size} full")
            
            return {
                'status': health_status,
                'timestamp': datetime.utcnow().isoformat(),
                'queue_sizes': queue_sizes,
                'issues': issues,
                'redis_connection': 'healthy'
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'timestamp': datetime.utcnow().isoformat(),
                'error': str(e),
                'redis_connection': 'failed'
            }