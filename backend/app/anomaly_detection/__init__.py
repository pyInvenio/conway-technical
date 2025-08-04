"""
Anomaly Detection System for GitHub Activity Monitoring

This module provides a comprehensive anomaly detection system with multiple detection layers:
- Behavioral anomaly detection (user activity patterns)
- Content-based detection (secrets, suspicious files)  
- Temporal anomaly detection (burst activity, coordinated actions)
- Repository context scoring (importance-based severity)

The system uses statistical algorithms, machine learning, and configurable rules
to detect security threats and unusual activity patterns in GitHub repositories.
"""

from .models.anomaly_score import AnomalyScore, SeverityLevel
from .scoring.severity_engine import SeverityEngine
from .stream_processor import AnomalyStreamProcessor

__version__ = "1.0.0"
__all__ = ["AnomalyScore", "SeverityLevel", "SeverityEngine", "AnomalyStreamProcessor"]