from dataclasses import dataclass
from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime

class SeverityLevel(Enum):
    """Severity levels with score ranges"""
    CRITICAL = ("critical", 0.85, 1.0)
    HIGH = ("high", 0.65, 0.84)
    MEDIUM = ("medium", 0.45, 0.64)
    LOW = ("low", 0.20, 0.44)
    INFO = ("info", 0.0, 0.19)
    
    def __init__(self, name: str, min_score: float, max_score: float):
        self.level_name = name
        self.min_score = min_score
        self.max_score = max_score
    
    @classmethod
    def from_score(cls, score: float) -> 'SeverityLevel':
        """Get severity level from score"""
        for level in cls:
            if level.min_score <= score <= level.max_score:
                return level
        return cls.INFO

@dataclass
class AnomalyScore:
    """Comprehensive anomaly scoring with breakdown"""
    
    # Base component scores (0-1)
    behavioral_anomaly: float = 0.0
    content_risk: float = 0.0
    temporal_anomaly: float = 0.0
    repository_criticality: float = 0.0
    
    # Context multipliers
    context_multiplier: float = 1.0
    urgency_factor: float = 1.0
    
    # Final calculated scores
    base_score: float = 0.0
    final_score: float = 0.0
    severity_level: SeverityLevel = SeverityLevel.INFO
    
    # Additional metadata
    incident_type: str = "unknown"
    confidence: float = 0.0
    explanation: Dict[str, Any] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.explanation is None:
            self.explanation = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def calculate_final_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate final severity score using the mathematical formula"""
        
        # Default weights for base score components
        if weights is None:
            weights = {
                'behavioral': 0.25,
                'content': 0.35,
                'temporal': 0.20,
                'repository': 0.20
            }
        
        # Calculate weighted base score
        self.base_score = (
            self.behavioral_anomaly * weights['behavioral'] +
            self.content_risk * weights['content'] +
            self.temporal_anomaly * weights['temporal'] +
            self.repository_criticality * weights['repository']
        )
        
        # Apply formula: severity_score = min(1.0, base_score * context_multiplier * urgency_factor)
        self.final_score = min(1.0, self.base_score * self.context_multiplier * self.urgency_factor)
        
        # Determine severity level
        self.severity_level = SeverityLevel.from_score(self.final_score)
        
        return self.final_score
    
    def set_context_multiplier(self, context_factors: Dict[str, bool]) -> float:
        """Set context multiplier based on context factors"""
        multiplier = 1.0
        
        context_multipliers = {
            'protected_branch': 1.5,
            'production_repo': 1.3,
            'high_privilege_user': 1.2,
            'off_hours': 1.1,
            'public_repo': 1.1
        }
        
        applied_factors = []
        for factor, is_present in context_factors.items():
            if is_present and factor in context_multipliers:
                multiplier *= context_multipliers[factor]
                applied_factors.append(factor)
        
        self.context_multiplier = multiplier
        self.explanation['context_factors'] = applied_factors
        return multiplier
    
    def set_urgency_factor(self, urgency_indicators: Dict[str, bool]) -> float:
        """Set urgency factor based on threat indicators"""
        factor = 1.0
        
        urgency_factors = {
            'secrets_exposed': 1.8,
            'mass_deletion': 1.5,
            'coordinated_attack': 1.4,
            'privilege_escalation': 1.3,
            'force_push_main': 1.3,
            'build_failure_cascade': 1.2
        }
        
        applied_indicators = []
        for indicator, is_present in urgency_indicators.items():
            if is_present and indicator in urgency_factors:
                factor *= urgency_factors[indicator]
                applied_indicators.append(indicator)
        
        self.urgency_factor = factor
        self.explanation['urgency_indicators'] = applied_indicators
        return factor
    
    def add_explanation(self, category: str, details: Any):
        """Add explanation details for the score"""
        self.explanation[category] = details
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'base_components': {
                'behavioral_anomaly': self.behavioral_anomaly,
                'content_risk': self.content_risk,
                'temporal_anomaly': self.temporal_anomaly,
                'repository_criticality': self.repository_criticality
            },
            'multipliers': {
                'context_multiplier': self.context_multiplier,
                'urgency_factor': self.urgency_factor
            },
            'scores': {
                'base_score': self.base_score,
                'final_score': self.final_score,
                'confidence': self.confidence
            },
            'classification': {
                'severity_level': self.severity_level.level_name,
                'incident_type': self.incident_type
            },
            'explanation': self.explanation,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnomalyScore':
        """Create instance from dictionary"""
        score = cls()
        
        # Base components
        if 'base_components' in data:
            comp = data['base_components']
            score.behavioral_anomaly = comp.get('behavioral_anomaly', 0.0)
            score.content_risk = comp.get('content_risk', 0.0)
            score.temporal_anomaly = comp.get('temporal_anomaly', 0.0)
            score.repository_criticality = comp.get('repository_criticality', 0.0)
        
        # Multipliers
        if 'multipliers' in data:
            mult = data['multipliers']
            score.context_multiplier = mult.get('context_multiplier', 1.0)
            score.urgency_factor = mult.get('urgency_factor', 1.0)
        
        # Scores
        if 'scores' in data:
            scores = data['scores']
            score.base_score = scores.get('base_score', 0.0)
            score.final_score = scores.get('final_score', 0.0)
            score.confidence = scores.get('confidence', 0.0)
        
        # Classification
        if 'classification' in data:
            classif = data['classification']
            score.incident_type = classif.get('incident_type', 'unknown')
            severity_name = classif.get('severity_level', 'info')
            score.severity_level = next((s for s in SeverityLevel if s.level_name == severity_name), SeverityLevel.INFO)
        
        # Metadata
        score.explanation = data.get('explanation', {})
        if data.get('timestamp'):
            score.timestamp = datetime.fromisoformat(data['timestamp'])
        
        return score