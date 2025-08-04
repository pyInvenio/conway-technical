from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func

from ...database import get_db
from ...models import AnomalyDetection, SecretDetection, TemporalPattern, GitHubEvent
from ...anomaly_detection.models.anomaly_score import SeverityLevel
# Authentication handled by session middleware

router = APIRouter(prefix="/api/v1", tags=["anomalies"])

@router.get("/anomalies")
async def get_anomalies(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    severity: Optional[str] = None,
    user: Optional[str] = None,
    repo: Optional[str] = None,
    since: Optional[datetime] = None,
    db: Session = Depends(get_db),
):
    """Get paginated list of anomalies with filtering"""
    
    # Build query
    query = db.query(AnomalyDetection)
    
    # Apply filters
    if severity:
        query = query.filter(AnomalyDetection.severity_level == severity.upper())
    
    if user:
        query = query.filter(AnomalyDetection.user_login == user)
    
    if repo:
        query = query.filter(AnomalyDetection.repository_name == repo)
    
    if since:
        query = query.filter(AnomalyDetection.detection_timestamp >= since)
    
    # Get total count
    total = query.count()
    
    # Apply pagination and ordering
    offset = (page - 1) * limit
    anomalies = (
        query
        .order_by(desc(AnomalyDetection.detection_timestamp))
        .offset(offset)
        .limit(limit)
        .all()
    )
    
    # Transform to response format
    response_anomalies = []
    for anomaly in anomalies:
        # Get the related GitHub event for payload data
        github_event = db.query(GitHubEvent).filter(GitHubEvent.id == anomaly.event_id).first()
        
        response_anomalies.append({
            "event_id": anomaly.event_id,
            "timestamp": anomaly.detection_timestamp.isoformat(),
            "user_login": anomaly.user_login,
            "repository_name": anomaly.repository_name,
            "event_type": anomaly.event_type,
            
            "final_anomaly_score": anomaly.final_anomaly_score,
            "severity_level": anomaly.severity_level,
            "severity_description": anomaly.severity_description,
            
            "detection_scores": {
                "behavioral": anomaly.behavioral_anomaly_score,
                "content": anomaly.content_risk_score,
                "temporal": anomaly.temporal_anomaly_score,
                "repository_criticality": anomaly.repository_criticality_score
            },
            
            "behavioral_analysis": anomaly.behavioral_analysis,
            "content_analysis": anomaly.content_analysis,
            "temporal_analysis": anomaly.temporal_analysis,
            "repository_context": anomaly.repository_context,
            
            "ai_summary": anomaly.ai_summary,
            "processing_timestamp": anomaly.processed_timestamp.isoformat() if anomaly.processed_timestamp else None,
            "is_processed": anomaly.is_processed,
            "is_false_positive": anomaly.is_false_positive,
            
            # Include event payload for GitHub URL generation
            "event_payload": github_event.payload if github_event else None,
            "event_created_at": github_event.created_at.isoformat() if github_event else None
        })
    
    # Calculate pagination info
    pages = (total + limit - 1) // limit
    has_next = page < pages
    has_prev = page > 1
    
    return {
        "anomalies": response_anomalies,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": pages,
            "has_next": has_next,
            "has_prev": has_prev
        },
        "stats": {
            "total_anomalies": total,
            "severity_breakdown": get_severity_breakdown(db, since),
            "top_users": get_top_users(db, since, limit=5),
            "top_repositories": get_top_repositories(db, since, limit=5)
        }
    }

@router.get("/anomalies/{event_id}")
async def get_anomaly_detail(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Get detailed information about a specific anomaly"""
    
    anomaly = db.query(AnomalyDetection).filter(
        AnomalyDetection.event_id == event_id
    ).first()
    
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    # Get related secret detections
    secret_detections = db.query(SecretDetection).filter(
        SecretDetection.anomaly_detection_id == anomaly.id
    ).all()
    
    # Get related temporal patterns
    temporal_patterns = db.query(TemporalPattern).filter(
        TemporalPattern.anomaly_detection_id == anomaly.id
    ).all()
    
    return {
        "event_id": anomaly.event_id,
        "timestamp": anomaly.detection_timestamp.isoformat(),
        "user_login": anomaly.user_login,
        "repository_name": anomaly.repository_name,
        "event_type": anomaly.event_type,
        "event_timestamp": anomaly.event_timestamp.isoformat(),
        
        "final_anomaly_score": anomaly.final_anomaly_score,
        "severity_level": anomaly.severity_level,
        "severity_description": anomaly.severity_description,
        
        "detection_scores": {
            "behavioral": anomaly.behavioral_anomaly_score,
            "content": anomaly.content_risk_score,
            "temporal": anomaly.temporal_anomaly_score,
            "repository_criticality": anomaly.repository_criticality_score
        },
        
        "detection_weights": anomaly.detection_weights,
        
        "behavioral_analysis": anomaly.behavioral_analysis,
        "content_analysis": anomaly.content_analysis,
        "temporal_analysis": anomaly.temporal_analysis,
        "repository_context": anomaly.repository_context,
        
        "secret_detections": [
            {
                "secret_type": s.secret_type,
                "pattern_description": s.pattern_description,
                "severity": s.severity,
                "location": s.location,
                "commit_sha": s.commit_sha,
                "file_path": s.file_path,
                "line_number": s.line_number,
                "match_preview": s.match_preview,
                "detected_at": s.detected_at.isoformat()
            }
            for s in secret_detections
        ],
        
        "temporal_patterns": [
            {
                "pattern_type": p.pattern_type,
                "severity": p.severity,
                "start_time": p.start_time.isoformat(),
                "duration_minutes": p.duration_minutes,
                "event_count": p.event_count,
                "actor_count": p.actor_count,
                "actors_involved": p.actors_involved,
                "events_per_minute": p.events_per_minute,
                "pattern_data": p.pattern_data,
                "detected_at": p.detected_at.isoformat()
            }
            for p in temporal_patterns
        ],
        
        "ai_summary": anomaly.ai_summary,
        "high_risk_indicators": anomaly.high_risk_indicators,
        
        "processing_info": {
            "detection_timestamp": anomaly.detection_timestamp.isoformat(),
            "processed_timestamp": anomaly.processed_timestamp.isoformat() if anomaly.processed_timestamp else None,
            "is_processed": anomaly.is_processed,
            "is_false_positive": anomaly.is_false_positive,
            "processing_notes": anomaly.processing_notes
        }
    }

@router.post("/anomalies/{event_id}/mark-false-positive")
async def mark_false_positive(
    event_id: str,
    db: Session = Depends(get_db),
):
    """Mark an anomaly as a false positive"""
    
    anomaly = db.query(AnomalyDetection).filter(
        AnomalyDetection.event_id == event_id
    ).first()
    
    if not anomaly:
        raise HTTPException(status_code=404, detail="Anomaly not found")
    
    anomaly.is_false_positive = True
    anomaly.is_processed = True
    anomaly.processed_timestamp = datetime.utcnow()
    anomaly.processing_notes = f"Marked as false positive by {current_user.get('username', 'user')}"
    
    db.commit()
    
    return {"message": "Anomaly marked as false positive"}

@router.get("/anomalies/stats/summary")
async def get_anomaly_stats(
    days: int = Query(7, ge=1, le=90),
    db: Session = Depends(get_db),
):
    """Get anomaly statistics for the specified time period"""
    
    since = datetime.utcnow() - timedelta(days=days)
    
    # Basic counts
    total_anomalies = db.query(AnomalyDetection).filter(
        AnomalyDetection.detection_timestamp >= since
    ).count()
    
    processed_anomalies = db.query(AnomalyDetection).filter(
        and_(
            AnomalyDetection.detection_timestamp >= since,
            AnomalyDetection.is_processed == True
        )
    ).count()
    
    false_positives = db.query(AnomalyDetection).filter(
        and_(
            AnomalyDetection.detection_timestamp >= since,
            AnomalyDetection.is_false_positive == True
        )
    ).count()
    
    # Severity breakdown
    severity_breakdown = get_severity_breakdown(db, since)
    
    # Top entities
    top_users = get_top_users(db, since, limit=10)
    top_repositories = get_top_repositories(db, since, limit=10)
    
    # Detection type breakdown
    detection_types = get_detection_type_breakdown(db, since)
    
    return {
        "time_period_days": days,
        "total_anomalies": total_anomalies,
        "processed_anomalies": processed_anomalies,
        "false_positives": false_positives,
        "processing_rate": processed_anomalies / total_anomalies if total_anomalies > 0 else 0,
        "false_positive_rate": false_positives / total_anomalies if total_anomalies > 0 else 0,
        
        "severity_breakdown": severity_breakdown,
        "detection_types": detection_types,
        "top_users": top_users,
        "top_repositories": top_repositories
    }

def get_severity_breakdown(db: Session, since: Optional[datetime] = None):
    """Get breakdown of anomalies by severity level"""
    query = db.query(AnomalyDetection)
    if since:
        query = query.filter(AnomalyDetection.detection_timestamp >= since)
    
    breakdown = {}
    for severity in SeverityLevel:
        count = query.filter(AnomalyDetection.severity_level == severity.name).count()
        breakdown[severity.name] = count
    
    return breakdown

def get_top_users(db: Session, since: Optional[datetime] = None, limit: int = 5):
    """Get top users by anomaly count"""
    query = db.query(
        AnomalyDetection.user_login,
        func.count(AnomalyDetection.id).label('anomaly_count')
    )
    
    if since:
        query = query.filter(AnomalyDetection.detection_timestamp >= since)
    
    results = (
        query
        .group_by(AnomalyDetection.user_login)
        .order_by(desc('anomaly_count'))
        .limit(limit)
        .all()
    )
    
    return [{"user": user, "count": count} for user, count in results]

def get_top_repositories(db: Session, since: Optional[datetime] = None, limit: int = 5):
    """Get top repositories by anomaly count"""
    query = db.query(
        AnomalyDetection.repository_name,
        func.count(AnomalyDetection.id).label('anomaly_count')
    )
    
    if since:
        query = query.filter(AnomalyDetection.detection_timestamp >= since)
    
    results = (
        query
        .group_by(AnomalyDetection.repository_name)
        .order_by(desc('anomaly_count'))
        .limit(limit)
        .all()
    )
    
    return [{"repository": repo, "count": count} for repo, count in results]

def get_detection_type_breakdown(db: Session, since: Optional[datetime] = None):
    """Get breakdown by detection type based on highest scoring component"""
    query = db.query(AnomalyDetection)
    if since:
        query = query.filter(AnomalyDetection.detection_timestamp >= since)
    
    anomalies = query.all()
    
    breakdown = {
        "behavioral": 0,
        "content": 0,
        "temporal": 0,
        "repository": 0
    }
    
    for anomaly in anomalies:
        scores = {
            "behavioral": anomaly.behavioral_anomaly_score,
            "content": anomaly.content_risk_score,
            "temporal": anomaly.temporal_anomaly_score,
            "repository": anomaly.repository_criticality_score
        }
        
        # Find the detection type with highest score
        max_type = max(scores, key=scores.get)
        breakdown[max_type] += 1
    
    return breakdown