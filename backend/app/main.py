# app/main.py
from fastapi import FastAPI, Request, HTTPException, Depends, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, text
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import asyncio
import json
import logging
import aiohttp
import redis.asyncio as redis
import secrets

from .database import get_db, init_db, SessionLocal
from .models import GitHubEvent, AnomalyDetection
from .poller import GitHubPoller
from .worker import QueueWorker
from .cache import cache_service
from .websocket_manager import websocket_manager
from .config import settings
from .api.v1.anomalies import router as anomalies_router, get_anomalies
from .cleanup import DatabaseCleanup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
active_pollers: Dict[str, asyncio.Task] = {}
redis_client = None
worker_task = None
active_websockets: List[WebSocket] = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global redis_client, worker_task
    
    logger.info("Starting GitHub Monitor Backend")
    redis_client = await redis.from_url(settings.redis_url)
    cache_service.redis_client = redis_client
    await cache_service.setup()
    await websocket_manager.setup(redis_client)
    worker_tasks = []
    num_workers = 3
    for i in range(num_workers):
        worker = QueueWorker(redis_client)
        worker_task = asyncio.create_task(worker.run())
        worker_tasks.append(worker_task)
    
    worker_task = worker_tasks[0]
    asyncio.create_task(start_existing_pollers())
    asyncio.create_task(schedule_daily_cleanup())
    
    yield
    
    logger.info("Shutting down GitHub Monitor Backend")
    for task in active_pollers.values():
        task.cancel()
    await websocket_manager.shutdown()
    if 'worker_tasks' in locals():
        for task in worker_tasks:
            task.cancel()
    elif worker_task:
        worker_task.cancel()
    if redis_client:
        await redis_client.close()

app = FastAPI(
    title="GitHub Monitor API",
    description="Real-time GitHub activity monitoring with AI-powered threat detection",
    version="1.0.0",
    lifespan=lifespan
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(anomalies_router)

async def start_existing_pollers():
    """Start pollers for existing active sessions and configured GitHub token on startup"""
    try:
        if settings.github_token and settings.github_token != "your-github-token-change-in-production":
            try:
                poller_key = f"poller:{settings.github_token[:8]}"
                if poller_key not in active_pollers or active_pollers[poller_key].done():
                    poller = GitHubPoller(settings.github_token)
                    active_pollers[poller_key] = asyncio.create_task(poller.run())
            except Exception as e:
                logger.error(f"Failed to start poller with configured token: {e}")
        session_keys = await redis_client.keys("session:*")
        
        for session_key in session_keys:
            try:
                session_data = await redis_client.get(session_key)
                if session_data:
                    session_info = json.loads(session_data)
                    token = session_info.get('token')
                    user_login = session_info.get('user_data', {}).get('login', 'Unknown')
                    
                    if token:
                        # Start poller for this token (skip if already started above)
                        poller_key = f"poller:{token[:8]}"
                        if poller_key not in active_pollers or active_pollers[poller_key].done():
                            poller = GitHubPoller(token)
                            active_pollers[poller_key] = asyncio.create_task(poller.run())
            
            except Exception as e:
                logger.error(f"Failed to start poller for session {session_key}: {e}")
        
                
    except Exception as e:
        logger.error(f"Failed to start existing pollers: {e}")

async def schedule_daily_cleanup():
    """Schedule daily database cleanup at 2 AM UTC"""
    cleanup = DatabaseCleanup()
    
    while True:
        try:
            # Calculate time until next 2 AM UTC
            now = datetime.utcnow()
            next_cleanup = now.replace(hour=2, minute=0, second=0, microsecond=0)
            
            # If we've passed 2 AM today, schedule for tomorrow
            if now.hour >= 2:
                next_cleanup += timedelta(days=1)
            
            wait_seconds = (next_cleanup - now).total_seconds()
            
            await asyncio.sleep(wait_seconds)
            
            # Run cleanup
            result = await cleanup.run_cleanup(dry_run=False)
            
        except Exception as e:
            logger.error(f"Scheduled cleanup failed: {e}")
            # Wait 1 hour before retrying on error
            await asyncio.sleep(3600)

# Session management
async def store_session(session_id: str, token: str, user_data: dict):
    """Store session in Redis"""
    await redis_client.setex(
        f"session:{session_id}",
        7 * 24 * 60 * 60,  # 7 days
        json.dumps({
            "token": token,
            "user": user_data,
            "created_at": datetime.now().isoformat()
        })
    )

async def get_session(session_id: str) -> Optional[dict]:
    """Get session from Redis"""
    data = await redis_client.get(f"session:{session_id}")
    if data:
        return json.loads(data)
    return None

async def verify_session(request: Request) -> dict:
    """Verify session from cookie"""
    session_id = request.cookies.get("session")
    if not session_id:
        raise HTTPException(status_code=401, detail="No session found")
    
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    
    return session

# Routes
@app.post("/auth/validate")
async def validate_token(request: Request):
    """Validate GitHub token and create session"""
    try:
        body = await request.json()
        token = body.get("token")
        
        if not token:
            raise HTTPException(status_code=400, detail="Token required")
        
        # Validate with GitHub
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
            ) as response:
                if response.status != 200:
                    raise HTTPException(status_code=401, detail="Invalid GitHub token")
                
                user_data = await response.json()
                rate_limit = {
                    "remaining": int(response.headers.get("X-RateLimit-Remaining", 0)),
                    "reset": int(response.headers.get("X-RateLimit-Reset", 0))
                }
        
        # Create session
        session_id = secrets.token_urlsafe(32)
        await store_session(session_id, token, {
            "login": user_data["login"],
            "avatar_url": user_data["avatar_url"],
            "name": user_data.get("name")
        })
        
        # Start poller for this token
        poller_key = f"poller:{token[:8]}"
        if poller_key not in active_pollers or active_pollers[poller_key].done():
            poller = GitHubPoller(token)
            active_pollers[poller_key] = asyncio.create_task(poller.run())
        
        # Create response
        response = JSONResponse({
            "user": {
                "login": user_data["login"],
                "avatar_url": user_data["avatar_url"],
                "name": user_data.get("name")
            },
            "rateLimit": rate_limit
        })
        
        # Set session cookie
        response.set_cookie(
            key="session",
            value=session_id,
            httponly=True,
            secure=False,  # Set to True in production with HTTPS
            samesite="lax",
            max_age=7 * 24 * 60 * 60
        )
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/repositories")
async def get_repositories(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Get paginated repositories with incident counts and Redis caching"""
    
    # Create cache key
    cache_key = f"repositories:page:{page}:limit:{limit}"
    
    # Try to get from Redis cache first
    try:
        cached_result = await redis_client.get(cache_key)
        if cached_result:
            return json.loads(cached_result)
    except Exception as e:
        logger.warning(f"Redis cache read failed: {e}")
    
    # Cache miss - query database
    offset = (page - 1) * limit
    
    
    query = db.query(
        AnomalyDetection.repository_name,
        func.count(AnomalyDetection.id).label('anomaly_count'),
        func.max(AnomalyDetection.detection_timestamp).label('last_activity'),
        func.avg(AnomalyDetection.final_anomaly_score).label('avg_severity')
    ).group_by(AnomalyDetection.repository_name).order_by(
        func.max(AnomalyDetection.detection_timestamp).desc()
    )
    
    total = query.count()
    repositories = query.offset(offset).limit(limit).all()
    
    result = {
        "repositories": [
            {
                "name": repo.repository_name,
                "events": repo.anomaly_count,
                "lastActivity": repo.last_activity.isoformat(),
                "riskScore": min(int(repo.avg_severity * 100), 100),
                "status": "critical" if repo.avg_severity >= 0.8 else "warning" if repo.avg_severity >= 0.6 else "normal"
            } for repo in repositories
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit,
            "has_next": page * limit < total,
            "has_prev": page > 1
        }
    }
    
    # Cache the result for 60 seconds (repositories change less frequently)
    try:
        await redis_client.setex(cache_key, 60, json.dumps(result, default=str))
    except Exception as e:
        logger.warning(f"Redis cache write failed: {e}")
    
    return result

@app.get("/repository/{repo_name:path}")
async def get_repository_details(
    repo_name: str,
    db: Session = Depends(get_db)
):
    """Get repository details with incident summary"""
    try:
        
        # Get repository stats
        stats = db.query(
            func.count(AnomalyDetection.id).label('anomaly_count'),
            func.max(AnomalyDetection.detection_timestamp).label('last_activity'),
            func.avg(AnomalyDetection.final_anomaly_score).label('avg_severity')
        ).filter(AnomalyDetection.repository_name == repo_name).first()
        
        if not stats.anomaly_count:
            # Return default stats for repositories with no anomalies yet
            return {
                "name": repo_name,
                "events": 0,
                "lastActivity": datetime.utcnow().isoformat(),
                "riskScore": 0,
                "status": "normal"
            }
        
        return {
            "name": repo_name,
            "events": stats.anomaly_count,
            "lastActivity": stats.last_activity.isoformat() if stats.last_activity else datetime.utcnow().isoformat(),
            "riskScore": min(int(stats.avg_severity * 100), 100) if stats.avg_severity else 0,
            "status": "critical" if stats.avg_severity and stats.avg_severity >= 0.8 else "warning" if stats.avg_severity and stats.avg_severity >= 0.6 else "normal"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching repository details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/event/{event_id}")
async def get_event_details(
    event_id: str,
    db: Session = Depends(get_db)
):
    """Get individual event details by ID"""
    try:
        
        # Get the event from database
        event = db.query(GitHubEvent).filter(GitHubEvent.id == event_id).first()
        
        if not event:
            raise HTTPException(status_code=404, detail="Event not found")
        
        # Get any related anomaly detections
        related_anomalies = db.query(AnomalyDetection).filter(
            AnomalyDetection.event_id == event_id
        ).all()
        
        return {
            "id": event.id,
            "type": event.type,
            "repo_name": event.repo_name,
            "actor_login": event.actor_login,
            "created_at": event.created_at.isoformat(),
            "payload": event.payload,
            "raw_response": event.raw_response,
            "processed": event.processed,
            "related_anomalies": [
                {
                    "id": anomaly.id,
                    "severity_level": anomaly.severity_level,
                    "severity_description": anomaly.severity_description,
                    "final_anomaly_score": anomaly.final_anomaly_score,
                    "detection_timestamp": anomaly.detection_timestamp.isoformat(),
                    "ai_summary": anomaly.ai_summary
                } for anomaly in related_anomalies
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching event details: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# REMOVED: /anomalies endpoint - now handled by /api/v1/anomalies router for better organization

@app.get("/metrics")
async def get_metrics(db: Session = Depends(get_db)):
    """Get system metrics"""
    
    # Count anomalies by severity
    total_anomalies = db.query(func.count(AnomalyDetection.id)).scalar() or 0
    critical_anomalies = db.query(func.count(AnomalyDetection.id)).filter(
        AnomalyDetection.severity_level.in_(['CRITICAL', 'HIGH'])
    ).scalar() or 0
    
    # Count unique repositories
    unique_repos = db.query(func.count(func.distinct(AnomalyDetection.repository_name))).scalar() or 0
    
    # Calculate average threat score
    avg_threat = db.query(func.avg(AnomalyDetection.final_anomaly_score)).scalar() or 0.0
    
    return {
        "totalEvents": total_anomalies,
        "criticalAlerts": critical_anomalies,
        "repositories": unique_repos,
        "threatScore": float(avg_threat)
    }

@app.get("/analytics/timeline")
async def get_incident_timeline(
    hours: int = Query(24, ge=1, le=168),  # 1 hour to 1 week
    db: Session = Depends(get_db)
):
    """Get incident timeline data for time series visualization"""
    
    # Try to get from cache first
    cached_timeline = await cache_service.get_timeline(hours)
    if cached_timeline:
        return {
            "timeRange": {
                "start": (datetime.now() - timedelta(hours=hours)).isoformat(),
                "end": datetime.now().isoformat(),
                "hours": hours
            },
            "timeline": cached_timeline
        }
    
    # Calculate time range
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=hours)
    
    # Create time buckets based on the range
    if hours <= 24:
        # Hourly buckets for <= 24 hours
        bucket_size = "hour"
        date_format = "YYYY-MM-DD HH24:00"
    elif hours <= 72:
        # 4-hour buckets for <= 3 days - we'll use hour and group manually
        bucket_size = "hour"
        date_format = "YYYY-MM-DD HH24:00"
    else:
        # Daily buckets for > 3 days
        bucket_size = "day"
        date_format = "YYYY-MM-DD"
    
    # Query incidents with time bucketing
    if hours <= 72 and hours > 24:
        # For 4-hour buckets, we need special grouping
        timeline_query = text(f"""
            WITH time_buckets AS (
                SELECT 
                    date_trunc('hour', detection_timestamp) - 
                    INTERVAL '1 hour' * (EXTRACT(hour FROM detection_timestamp)::integer % 4) as time_bucket,
                    COUNT(*) as incident_count,
                    AVG(final_anomaly_score) as avg_severity,
                    COUNT(CASE WHEN severity_level IN ('CRITICAL', 'HIGH') THEN 1 END) as critical_count,
                    COUNT(CASE WHEN severity_level = 'MEDIUM' THEN 1 END) as warning_count,
                    COUNT(CASE WHEN severity_level IN ('LOW', 'INFO') THEN 1 END) as info_count
                FROM anomaly_detections 
                WHERE detection_timestamp >= :start_time AND detection_timestamp <= :end_time
                GROUP BY time_bucket
                ORDER BY time_bucket
            )
            SELECT 
                to_char(time_bucket, :date_format) as time_label,
                time_bucket,
                incident_count,
                COALESCE(avg_severity, 0) as avg_severity,
                critical_count,
                warning_count,
                info_count
            FROM time_buckets
        """)
    else:
        timeline_query = text(f"""
            WITH time_buckets AS (
                SELECT date_trunc(:bucket_size, detection_timestamp) as time_bucket,
                       COUNT(*) as incident_count,
                       AVG(final_anomaly_score) as avg_severity,
                       COUNT(CASE WHEN severity_level IN ('CRITICAL', 'HIGH') THEN 1 END) as critical_count,
                       COUNT(CASE WHEN severity_level = 'MEDIUM' THEN 1 END) as warning_count,
                       COUNT(CASE WHEN severity_level IN ('LOW', 'INFO') THEN 1 END) as info_count
                FROM anomaly_detections 
                WHERE detection_timestamp >= :start_time AND detection_timestamp <= :end_time
                GROUP BY time_bucket
                ORDER BY time_bucket
            )
            SELECT 
                to_char(time_bucket, :date_format) as time_label,
                time_bucket,
                incident_count,
                COALESCE(avg_severity, 0) as avg_severity,
                critical_count,
                warning_count,
                info_count
            FROM time_buckets
        """)
    
    # Execute query with appropriate parameters
    if hours <= 72 and hours > 24:
        # 4-hour bucket case doesn't need bucket_size parameter
        results = db.execute(timeline_query, {
            "start_time": start_time,
            "end_time": end_time,
            "date_format": date_format
        }).fetchall()
    else:
        results = db.execute(timeline_query, {
            "bucket_size": bucket_size,
            "start_time": start_time,
            "end_time": end_time,
            "date_format": date_format
        }).fetchall()
    
    # Convert to list of dictionaries
    timeline_data = []
    for row in results:
        timeline_data.append({
            "time": row.time_label,
            "timestamp": row.time_bucket.isoformat(),
            "incidents": row.incident_count,
            "avgSeverity": float(row.avg_severity),
            "critical": row.critical_count,
            "warning": row.warning_count,
            "info": row.info_count
        })
    
    # Cache the timeline data
    await cache_service.set_timeline(timeline_data, hours, ttl=300)  # 5 minute cache
    
    return {
        "timeRange": {
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "hours": hours,
            "bucketSize": bucket_size
        },
        "timeline": timeline_data
    }

@app.get("/ssr/initial-data")
async def get_initial_data(db: Session = Depends(get_db)):
    """Get initial data for SSR - uses /api/v1/anomalies for consistency"""
    
    # Try to get from cache first
    cached_data = await cache_service.get("initial_data")
    if cached_data:
        return cached_data
    
    # Use the unified /api/v1/anomalies endpoint for anomaly data
    anomalies_data = await get_anomalies(page=1, limit=20, db=db)
    
    # Fetch repositories with aggregated data (first 20)
    repositories_query = db.query(
        AnomalyDetection.repository_name,
        func.count(AnomalyDetection.id).label('anomaly_count'),
        func.max(AnomalyDetection.detection_timestamp).label('last_activity'),
        func.avg(AnomalyDetection.final_anomaly_score).label('avg_severity')
    ).group_by(AnomalyDetection.repository_name).order_by(
        func.max(AnomalyDetection.detection_timestamp).desc()
    )
    
    total_repositories = repositories_query.count()
    repositories = repositories_query.limit(20).all()
    
    # Calculate metrics
    critical_anomalies = db.query(func.count(AnomalyDetection.id)).filter(
        AnomalyDetection.severity_level.in_(['CRITICAL', 'HIGH'])
    ).scalar() or 0
    
    unique_repos = db.query(func.count(func.distinct(AnomalyDetection.repository_name))).scalar() or 0
    avg_threat = db.query(func.avg(AnomalyDetection.final_anomaly_score)).scalar() or 0.0
    
    result = {
        "anomalies": anomalies_data,
        "repositories": {
            "repositories": [
                {
                    "name": repo.repository_name,
                    "events": repo.anomaly_count,
                    "lastActivity": repo.last_activity.isoformat(),
                    "riskScore": min(int(repo.avg_severity * 100), 100),
                    "status": "critical" if repo.avg_severity >= 0.8 else "warning" if repo.avg_severity >= 0.6 else "normal"
                } for repo in repositories
            ],
            "pagination": {
                "page": 1,
                "limit": 20,
                "total": total_repositories,
                "pages": (total_repositories + 19) // 20,
                "has_next": total_repositories > 20,
                "has_prev": False
            }
        },
        "metrics": {
            "totalEvents": anomalies_data["pagination"]["total"],
            "criticalAlerts": critical_anomalies,
            "repositories": unique_repos,
            "threatScore": float(avg_threat or 0.0)
        }
    }
    
    # Cache the result for 2 minutes (short TTL for dashboard data)
    await cache_service.set("initial_data", result, ttl=120)
    
    return result

# WebSocket endpoint removed - using simpler version below

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check database
        db = SessionLocal()
        db.execute("SELECT 1")
        db.close()
        
        # Check Redis
        await redis_client.ping()
        
        return {
            "status": "healthy",
            "database": "connected",
            "redis": "connected",
            "active_pollers": len([t for t in active_pollers.values() if not t.done()]),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )

@app.post("/admin/restart-pollers")
async def restart_pollers():
    """Admin endpoint to restart all pollers from active sessions"""
    try:
        await start_existing_pollers()
        active_count = len([t for t in active_pollers.values() if not t.done()])
        return {
            "status": "success",
            "message": f"Restarted pollers, {active_count} now active",
            "active_pollers": active_count
        }
    except Exception as e:
        logger.error(f"Failed to restart pollers: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/admin/poller-status")
async def get_poller_status():
    """Get detailed status of all pollers"""
    try:
        status = {}
        for poller_key, task in active_pollers.items():
            status[poller_key] = {
                "running": not task.done(),
                "done": task.done(),
                "cancelled": task.cancelled(),
                "exception": str(task.exception()) if task.done() and task.exception() else None
            }
        
        return {
            "total_pollers": len(active_pollers),
            "active_pollers": len([t for t in active_pollers.values() if not t.done()]),
            "poller_details": status
        }
    except Exception as e:
        logger.error(f"Failed to get poller status: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.get("/admin/storage-stats")
async def get_storage_stats():
    """Get database storage statistics"""
    try:
        cleanup = DatabaseCleanup()
        stats = await cleanup.get_storage_stats()
        return {
            "status": "success",
            "storage_stats": stats
        }
    except Exception as e:
        logger.error(f"Failed to get storage stats: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

@app.post("/admin/cleanup")
async def run_manual_cleanup(
    dry_run: bool = Query(True, description="Run in dry-run mode to preview changes")
):
    """Run manual database cleanup"""
    try:
        cleanup = DatabaseCleanup()
        result = await cleanup.run_cleanup(dry_run=dry_run)
        return {
            "status": "success",
            "cleanup_result": result
        }
    except Exception as e:
        logger.error(f"Manual cleanup failed: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

# WebSocket connection manager
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    try:
        await websocket.accept()
        active_websockets.append(websocket)
        
        # Register with WebSocket manager without double-accepting
        websocket_manager.active_connections.append(websocket)
        websocket_manager.user_subscriptions[websocket] = set()
        
        try:
            # Keep connection alive and listen for messages
            while True:
                # Wait for any message (ping/pong to keep alive)
                try:
                    data = await websocket.receive_text()
                    try:
                        message = json.loads(data)
                        # Handle client messages through WebSocket manager
                        await websocket_manager.handle_client_message(websocket, message)
                    except json.JSONDecodeError:
                        # Echo back for simple keep-alive
                        await websocket.send_text(f"pong: {data}")
                except WebSocketDisconnect:
                    break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            if websocket in active_websockets:
                active_websockets.remove(websocket)
            # Clean up from WebSocket manager
            if websocket in websocket_manager.active_connections:
                websocket_manager.active_connections.remove(websocket)
            if websocket in websocket_manager.user_subscriptions:
                del websocket_manager.user_subscriptions[websocket]
            
    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
        try:
            await websocket.close(code=1011, reason="Connection error")
        except:
            pass

# Utility function for broadcasting incidents
async def broadcast_incident(incident: dict):
    """Broadcast incident to all WebSocket clients and invalidate cache"""
    # Broadcast to WebSocket clients
    message = json.dumps({
        "type": "incident",
        "data": incident
    })
    
    # Send to all connected WebSocket clients
    disconnected = []
    for websocket in active_websockets:
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.warning(f"Failed to send to WebSocket: {e}")
            disconnected.append(websocket)
    
    # Remove disconnected WebSockets
    for ws in disconnected:
        if ws in active_websockets:
            active_websockets.remove(ws)
    
    
    # Also broadcast to Redis for SSE clients (backward compatibility)
    await redis_client.publish("incidents", json.dumps(incident))
    
    # Invalidate relevant caches
    try:
        # Clear repositories cache
        keys = await redis_client.keys("repositories:page:*")
        if keys:
            await redis_client.delete(*keys)
        
        # Clear SSR cache
        await cache_service.delete("initial_data")
    except Exception as e:
        logger.warning(f"Cache invalidation failed: {e}")