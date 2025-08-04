from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float, Index, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from pydantic import BaseModel
from datetime import datetime
from typing import List, Dict, Any, Optional
from .database import Base

# SQLAlchemy Models
class GitHubEvent(Base):
    __tablename__ = "github_events"
    
    id = Column(String, primary_key=True)
    type = Column(String, index=True)
    repo_name = Column(String, index=True)
    actor_login = Column(String, index=True)
    created_at = Column(DateTime, index=True)
    payload = Column(JSON)
    raw_response = Column(JSON)  # Complete GitHub API response including actor, repo, org fields
    processed = Column(Boolean, default=False, index=True)
    
    __table_args__ = (
        Index('idx_repo_time', 'repo_name', 'created_at'),
        Index('idx_type_time', 'type', 'created_at'),
    )

# REMOVED: IncidentSummary model - use AnomalyDetection instead for 100x better performance

# REMOVED: IncidentSummaryResponse - use AnomalyDetection directly


# Anomaly Detection Models
class AnomalyDetection(Base):
    """Main anomaly detection record"""
    __tablename__ = 'anomaly_detections'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    event_id = Column(String(255), nullable=False, index=True)
    user_login = Column(String(255), nullable=False, index=True)
    repository_name = Column(String(255), nullable=False, index=True)
    event_type = Column(String(100), nullable=False)
    
    # Timestamp fields
    event_timestamp = Column(DateTime, nullable=False)
    detection_timestamp = Column(DateTime, nullable=False, default=func.now())
    processed_timestamp = Column(DateTime, nullable=True)
    
    # Anomaly scoring
    final_anomaly_score = Column(Float, nullable=False, index=True)
    severity_level = Column(String(20), nullable=False, index=True)
    severity_description = Column(Text, nullable=True)
    
    # Component scores
    behavioral_anomaly_score = Column(Float, nullable=False, default=0.0)
    content_risk_score = Column(Float, nullable=False, default=0.0)
    temporal_anomaly_score = Column(Float, nullable=False, default=0.0)
    repository_criticality_score = Column(Float, nullable=False, default=0.0)
    
    # Detection weights used
    detection_weights = Column(JSON, nullable=True)
    
    # Analysis results (stored as JSON)
    behavioral_analysis = Column(JSON, nullable=True)
    content_analysis = Column(JSON, nullable=True)
    temporal_analysis = Column(JSON, nullable=True)
    repository_context = Column(JSON, nullable=True)
    
    # AI summary and insights
    ai_summary = Column(Text, nullable=True)
    high_risk_indicators = Column(JSON, nullable=True)
    
    # Processing status
    is_processed = Column(Boolean, default=False, index=True)
    is_false_positive = Column(Boolean, default=False, index=True)
    processing_notes = Column(Text, nullable=True)
    
    # Relationships
    secret_detections = relationship("SecretDetection", back_populates="anomaly_detection")
    temporal_patterns = relationship("TemporalPattern", back_populates="anomaly_detection")
    
    # Composite indexes for efficient queries
    __table_args__ = (
        Index('idx_severity_timestamp', 'severity_level', 'detection_timestamp'),
        Index('idx_user_repo_timestamp', 'user_login', 'repository_name', 'detection_timestamp'),
        Index('idx_score_timestamp', 'final_anomaly_score', 'detection_timestamp'),
        Index('idx_processed_severity', 'is_processed', 'severity_level'),
    )


class SecretDetection(Base):
    """Secret detection details"""
    __tablename__ = 'secret_detections'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    anomaly_detection_id = Column(String(36), ForeignKey('anomaly_detections.id'), nullable=False, index=True)
    
    # Secret details
    secret_type = Column(String(100), nullable=False)
    pattern_description = Column(String(255), nullable=False)
    severity = Column(Float, nullable=False)
    location = Column(String(100), nullable=False)  # commit_message, file_content, etc.
    
    # Context
    commit_sha = Column(String(40), nullable=True)
    file_path = Column(String(500), nullable=True)
    line_number = Column(Integer, nullable=True)
    
    # Match details (truncated for security)
    match_preview = Column(String(50), nullable=True)
    position_start = Column(Integer, nullable=True)
    position_end = Column(Integer, nullable=True)
    
    # Timestamps
    detected_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationship
    anomaly_detection = relationship("AnomalyDetection", back_populates="secret_detections")
    
    __table_args__ = (
        Index('idx_secret_type_severity', 'secret_type', 'severity'),
        Index('idx_commit_location', 'commit_sha', 'location'),
    )


class TemporalPattern(Base):
    """Detected temporal patterns"""
    __tablename__ = 'temporal_patterns'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    anomaly_detection_id = Column(String(36), ForeignKey('anomaly_detections.id'), nullable=False, index=True)
    
    # Pattern details
    pattern_type = Column(String(100), nullable=False)  # activity_burst, coordinated_activity, etc.
    severity = Column(Float, nullable=False)
    start_time = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, nullable=True)
    
    # Pattern-specific data
    event_count = Column(Integer, nullable=True)
    actor_count = Column(Integer, nullable=True)
    actors_involved = Column(JSON, nullable=True)  # List of actor logins
    
    # Statistical measures
    events_per_minute = Column(Float, nullable=True)
    chi2_statistic = Column(Float, nullable=True)
    p_value = Column(Float, nullable=True)
    
    # Additional pattern data
    pattern_data = Column(JSON, nullable=True)
    
    # Timestamps
    detected_at = Column(DateTime, nullable=False, default=func.now())
    
    # Relationship
    anomaly_detection = relationship("AnomalyDetection", back_populates="temporal_patterns")
    
    __table_args__ = (
        Index('idx_pattern_type_severity', 'pattern_type', 'severity'),
        Index('idx_start_time_duration', 'start_time', 'duration_minutes'),
    )


class UserProfile(Base):
    """User behavioral profiles"""
    __tablename__ = 'user_profiles'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    user_login = Column(String(255), nullable=False, unique=True, index=True)
    
    # Profile metadata
    total_events = Column(Integer, nullable=False, default=0)
    first_seen = Column(DateTime, nullable=False, default=func.now())
    last_updated = Column(DateTime, nullable=False, default=func.now())
    profile_version = Column(String(10), nullable=False, default='1.0')
    
    # Behavioral features (EWMA-based means and standard deviations)
    mean_features = Column(JSON, nullable=False)  # Array of 10 features
    std_features = Column(JSON, nullable=False)   # Array of 10 std deviations
    
    # Activity patterns
    most_active_hour = Column(Integer, nullable=False, default=12)
    hourly_activity_distribution = Column(JSON, nullable=False)  # 24-element array
    event_type_distribution = Column(JSON, nullable=False)  # Dict of event types -> probabilities
    
    # Top repositories
    top_repositories = Column(JSON, nullable=False)  # List of {name, count}
    
    # Profile quality indicators
    confidence_score = Column(Float, nullable=False, default=0.0)
    stability_score = Column(Float, nullable=False, default=0.5)
    
    __table_args__ = (
        Index('idx_user_updated', 'user_login', 'last_updated'),
        Index('idx_confidence_events', 'confidence_score', 'total_events'),
    )


class RepositoryProfile(Base):
    """Repository activity profiles"""
    __tablename__ = 'repository_profiles'
    
    id = Column(String(36), primary_key=True, default=lambda: str(__import__('uuid').uuid4()))
    repository_name = Column(String(255), nullable=False, unique=True, index=True)
    
    # Profile metadata
    total_events = Column(Integer, nullable=False, default=0)
    first_seen = Column(DateTime, nullable=False, default=func.now())
    last_updated = Column(DateTime, nullable=False, default=func.now())
    profile_version = Column(String(10), nullable=False, default='1.0')
    
    # Activity metrics (EWMA-based)
    avg_events_per_day = Column(Float, nullable=False, default=0.0)
    avg_unique_contributors_per_day = Column(Float, nullable=False, default=0.0)
    avg_commits_per_push = Column(Float, nullable=False, default=0.0)
    contributor_diversity_score = Column(Float, nullable=False, default=0.0)
    activity_regularity_score = Column(Float, nullable=False, default=0.5)
    
    # Time patterns
    peak_activity_hour = Column(Integer, nullable=False, default=12)
    weekend_activity_ratio = Column(Float, nullable=False, default=0.0)
    hourly_distribution = Column(JSON, nullable=False)  # 24-element array
    
    # Quality metrics
    build_success_rate = Column(Float, nullable=False, default=1.0)
    issue_resolution_rate = Column(Float, nullable=False, default=1.0)
    
    # Contributors and event types
    event_type_distribution = Column(JSON, nullable=False)  # Dict of event types -> counts
    top_contributors = Column(JSON, nullable=False)  # List of {name, count}
    
    # Activity history (sliding window)
    activity_history = Column(JSON, nullable=False)  # List of activity summaries
    
    __table_args__ = (
        Index('idx_repo_updated', 'repository_name', 'last_updated'),
        Index('idx_activity_quality', 'avg_events_per_day', 'build_success_rate'),
    )