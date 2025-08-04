# app/cache.py
import json
import logging
from typing import Any, Optional, List, Dict
from datetime import datetime, timedelta
import redis.asyncio as redis

from .config import settings

logger = logging.getLogger(__name__)

class CacheService:
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.default_ttl = 300  # 5 minutes default TTL
        
    async def setup(self):
        """Initialize Redis connection if not provided"""
        if not self.redis_client:
            self.redis_client = await redis.from_url(settings.redis_url)
    
    def _make_key(self, prefix: str, **kwargs) -> str:
        """Create a cache key from prefix and parameters"""
        parts = [prefix]
        for key, value in sorted(kwargs.items()):
            if value is not None:
                parts.append(f"{key}:{value}")
        return ":".join(parts)
    
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            data = await self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None
    
    async def set(self, key: str, value: Any, ttl: int = None) -> bool:
        """Set value in cache with TTL"""
        try:
            ttl = ttl or self.default_ttl
            data = json.dumps(value, default=str)  # default=str for datetime serialization
            await self.redis_client.setex(key, ttl, data)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False
    
    async def delete(self, key: str) -> bool:
        """Delete key from cache"""
        try:
            await self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern"""
        try:
            keys = await self.redis_client.keys(pattern)
            if keys:
                return await self.redis_client.delete(*keys)
            return 0
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return 0
    
    # Dashboard-specific cache methods
    async def get_incidents(self, page: int = 1, limit: int = 20) -> Optional[Dict]:
        """Get cached incidents page"""
        key = self._make_key("incidents", page=page, limit=limit)
        return await self.get(key)
    
    async def set_incidents(self, incidents_data: Dict, page: int = 1, limit: int = 20, ttl: int = None) -> bool:
        """Cache incidents page"""
        key = self._make_key("incidents", page=page, limit=limit)
        return await self.set(key, incidents_data, ttl)
    
    async def get_repositories(self, page: int = 1, limit: int = 20, search: str = None) -> Optional[Dict]:
        """Get cached repositories page"""
        key = self._make_key("repositories", page=page, limit=limit, search=search)
        return await self.get(key)
    
    async def set_repositories(self, repo_data: Dict, page: int = 1, limit: int = 20, search: str = None, ttl: int = None) -> bool:
        """Cache repositories page"""
        key = self._make_key("repositories", page=page, limit=limit, search=search)
        return await self.set(key, repo_data, ttl)
    
    async def get_metrics(self) -> Optional[Dict]:
        """Get cached dashboard metrics"""
        return await self.get("metrics:dashboard")
    
    async def set_metrics(self, metrics_data: Dict, ttl: int = None) -> bool:
        """Cache dashboard metrics"""
        return await self.set("metrics:dashboard", metrics_data, ttl)
    
    async def get_timeline(self, hours: int = 24) -> Optional[List]:
        """Get cached timeline data"""
        key = self._make_key("timeline", hours=hours)
        return await self.get(key)
    
    async def set_timeline(self, timeline_data: List, hours: int = 24, ttl: int = None) -> bool:
        """Cache timeline data"""
        key = self._make_key("timeline", hours=hours)
        return await self.set(key, timeline_data, ttl)
    
    # Cache invalidation methods
    async def invalidate_incidents(self) -> int:
        """Invalidate all incidents cache"""
        return await self.delete_pattern("incidents:*")
    
    async def invalidate_repositories(self) -> int:
        """Invalidate all repositories cache"""
        return await self.delete_pattern("repositories:*")
    
    async def invalidate_metrics(self) -> bool:
        """Invalidate metrics cache"""
        return await self.delete("metrics:dashboard")
    
    async def invalidate_timeline(self) -> int:
        """Invalidate all timeline cache"""
        return await self.delete_pattern("timeline:*")
    
    async def invalidate_all(self) -> int:
        """Invalidate all dashboard cache"""
        count = 0
        count += await self.invalidate_incidents()
        count += await self.invalidate_repositories()
        count += await self.invalidate_timeline()
        await self.invalidate_metrics()
        return count

# Global cache service instance
cache_service = CacheService()