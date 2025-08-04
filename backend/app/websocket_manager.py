# app/websocket_manager.py
import asyncio
import json
import logging
from typing import List, Dict, Set
from datetime import datetime
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, redis_client=None):
        self.active_connections: List[WebSocket] = []
        self.user_subscriptions: Dict[WebSocket, Set[str]] = {}
        self.redis_client = redis_client
        self.pubsub_task = None
        
    async def setup(self, redis_client):
        """Initialize WebSocket manager with Redis client"""
        self.redis_client = redis_client
        # Start Redis pub/sub listener
        self.pubsub_task = asyncio.create_task(self._listen_to_redis())
        logger.info("WebSocket manager initialized")
    
    async def connect(self, websocket: WebSocket, user_id: str = None):
        """Accept WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.user_subscriptions[websocket] = set()
        
        # Send connection confirmation
        await self._send_to_connection(websocket, {
            "type": "connection",
            "status": "connected",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id
        })
        
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.user_subscriptions:
            del self.user_subscriptions[websocket]
        
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, websocket: WebSocket, message: dict):
        """Send message to specific WebSocket connection"""
        await self._send_to_connection(websocket, message)
    
    async def broadcast_message(self, message: dict, message_type: str = None):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
            
        # Add timestamp and type to message
        message.update({
            "timestamp": datetime.now().isoformat(),
            "broadcast": True
        })
        
        if message_type:
            message["type"] = message_type
            
        logger.info(f"Broadcasting {message_type} to {len(self.active_connections)} connections")
        
        # Send to all connections concurrently
        tasks = []
        for connection in self.active_connections.copy():  # Copy to avoid modification during iteration
            tasks.append(self._send_to_connection(connection, message))
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def handle_client_message(self, websocket: WebSocket, data: dict):
        """Handle incoming messages from clients"""
        message_type = data.get("type")
        
        if message_type == "subscribe":
            # Client wants to subscribe to specific channels
            channels = data.get("channels", [])
            for channel in channels:
                self.user_subscriptions[websocket].add(channel)
            
            await self._send_to_connection(websocket, {
                "type": "subscription_confirmed",
                "channels": list(self.user_subscriptions[websocket])
            })
            
        elif message_type == "unsubscribe":
            # Client wants to unsubscribe from channels
            channels = data.get("channels", [])
            for channel in channels:
                self.user_subscriptions[websocket].discard(channel)
                
            await self._send_to_connection(websocket, {
                "type": "unsubscription_confirmed", 
                "channels": list(self.user_subscriptions[websocket])
            })
            
        elif message_type == "ping":
            # Heartbeat/ping-pong
            await self._send_to_connection(websocket, {
                "type": "pong",
                "timestamp": datetime.now().isoformat()
            })
            
        elif message_type == "get_status":
            # Client requesting connection status
            await self._send_to_connection(websocket, {
                "type": "status",
                "connected": True,
                "total_connections": len(self.active_connections),
                "subscriptions": list(self.user_subscriptions[websocket]),
                "timestamp": datetime.now().isoformat()
            })
    
    async def _send_to_connection(self, websocket: WebSocket, message: dict):
        """Send message to a single WebSocket connection"""
        try:
            await websocket.send_text(json.dumps(message))
        except Exception as e:
            logger.error(f"Error sending message to WebSocket: {e}")
            # Remove broken connection
            self.disconnect(websocket)
    
    async def _listen_to_redis(self):
        """Listen to Redis pub/sub for anomaly broadcasts and real-time events"""
        if not self.redis_client:
            logger.warning("No Redis client available for pub/sub")
            return
            
        pubsub = self.redis_client.pubsub()
        # Subscribe to anomaly channels for high-performance real-time updates
        channels = [
            "anomalies",           # All anomaly detections
            "anomalies_critical",  # Critical anomalies
            "anomalies_high",      # High severity anomalies
            "anomalies_medium",    # Medium severity anomalies
            "events_processed",    # Real-time event processing updates
            "processing_stats"     # Batch processing statistics
        ]
        await pubsub.subscribe(*channels)
        
        logger.info(f"Started listening to Redis pub/sub for anomalies and events: {channels}")
        
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message and message["type"] == "message":
                    try:
                        channel = message["channel"].decode()
                        data = json.loads(message["data"].decode())
                        
                        # Route messages based on channel for optimal frontend handling
                        if channel.startswith("anomalies"):
                            await self.broadcast_message(data, "anomaly")
                        elif channel == "events_processed":
                            await self.broadcast_message(data, "events_processed")
                        elif channel == "processing_stats":
                            await self.broadcast_message(data, "processing_stats")
                        else:
                            # Generic broadcast
                            await self.broadcast_message(data, channel)
                            
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to decode pub/sub data from {message.get('channel', 'unknown')}: {e}")
                else:
                    # Prevent busy waiting
                    await asyncio.sleep(0.01)  # Reduced sleep for faster updates
                    
        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener cancelled")
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
        except Exception as e:
            logger.error(f"Redis pub/sub listener error: {e}")
    
    async def shutdown(self):
        """Shutdown WebSocket manager"""
        if self.pubsub_task:
            self.pubsub_task.cancel()
            try:
                await self.pubsub_task
            except asyncio.CancelledError:
                pass
        
        # Close all connections
        for websocket in self.active_connections.copy():
            try:
                await websocket.close()
            except:
                pass
        
        self.active_connections.clear()
        self.user_subscriptions.clear()
        logger.info("WebSocket manager shutdown complete")

# Global WebSocket manager instance
websocket_manager = WebSocketManager()