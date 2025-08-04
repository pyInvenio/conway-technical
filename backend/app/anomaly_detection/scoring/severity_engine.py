from typing import Dict, Any, List, Optional
from datetime import datetime, time
import logging

from ..models.anomaly_score import AnomalyScore, SeverityLevel

logger = logging.getLogger(__name__)

class SeverityEngine:
    """Mathematical severity scoring engine implementing the comprehensive formula"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        
        # Default component weights
        self.default_weights = {
            'behavioral': 0.25,
            'content': 0.35,
            'temporal': 0.20,
            'repository': 0.20
        }
        
        # Context multipliers
        self.context_multipliers = {
            'protected_branch': 1.5,
            'production_repo': 1.3,
            'high_privilege_user': 1.2,
            'off_hours_likely': 1.1,  # Changed from off_hours since we can't be certain
            'public_repo': 1.1,
            'default': 1.0
        }
        
        # Urgency factors
        self.urgency_factors = {
            'secrets_exposed': 1.8,
            'mass_deletion': 1.5,
            'coordinated_attack': 1.4,
            'privilege_escalation': 1.3,
            'force_push_main': 1.3,
            'build_failure_cascade': 1.2,
            'default': 1.0
        }
        
        # Since we only have GMT and no user geolocation, we'll use statistical likelihood
        # Most development activity happens during business hours across major timezones
        # We'll consider times that are likely to be off-hours for major development regions
        self.likely_off_hours_gmt = [
            (time(2, 0), time(10, 0)),   # 2 AM - 10 AM GMT (covers US night, Asia early morning)
            (time(14, 0), time(18, 0))   # 2 PM - 6 PM GMT (covers Asia night, US early morning)
        ]
    
    def calculate_severity(
        self,
        behavioral_score: float,
        content_score: float,
        temporal_score: float,
        repository_score: float,
        context_data: Dict[str, Any],
        incident_type: str = "unknown",
        confidence: float = 0.0
    ) -> AnomalyScore:
        """Calculate comprehensive severity score"""
        
        # Create anomaly score object
        score = AnomalyScore(
            behavioral_anomaly=max(0.0, min(1.0, behavioral_score)),
            content_risk=max(0.0, min(1.0, content_score)),
            temporal_anomaly=max(0.0, min(1.0, temporal_score)),
            repository_criticality=max(0.0, min(1.0, repository_score)),
            incident_type=incident_type,
            confidence=confidence
        )
        
        # Analyze context for multipliers
        context_factors = self._analyze_context_factors(context_data)
        score.set_context_multiplier(context_factors)
        
        # Analyze urgency indicators
        urgency_indicators = self._analyze_urgency_indicators(context_data, incident_type)
        score.set_urgency_factor(urgency_indicators)
        
        # Calculate final score with configured weights
        weights = self.config.get('component_weights', self.default_weights)
        final_score = score.calculate_final_score(weights)
        
        # Add detailed explanation
        self._add_scoring_explanation(score, context_data)
        
        logger.info(f"Calculated severity: {final_score:.3f} ({score.severity_level.level_name}) for {incident_type}")
        
        return score
    
    def _analyze_context_factors(self, context_data: Dict[str, Any]) -> Dict[str, bool]:
        """Analyze context data to determine multiplier factors"""
        factors = {}
        
        # Protected branch check
        branch_info = context_data.get('branch_info', {})
        ref = branch_info.get('ref', context_data.get('ref', ''))
        factors['protected_branch'] = any(protected in ref.lower() 
                                        for protected in ['main', 'master', 'production', 'prod'])
        
        # Production repository check
        repo_info = context_data.get('repository_info', {})
        repo_name = repo_info.get('name', context_data.get('repo_name', ''))
        factors['production_repo'] = any(prod in repo_name.lower() 
                                       for prod in ['prod', 'production', 'live', 'release'])
        
        # High privilege user check
        user_info = context_data.get('user_info', {})
        factors['high_privilege_user'] = (
            user_info.get('is_admin', False) or
            user_info.get('is_owner', False) or
            'admin' in user_info.get('permissions', [])
        )
        
        # Off-hours likelihood check (since we only have GMT and no user location)
        event_time = context_data.get('timestamp')
        if isinstance(event_time, str):
            # Handle both ISO format and GitHub's format
            if event_time.endswith('Z'):
                event_time = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
            else:
                try:
                    event_time = datetime.fromisoformat(event_time)
                except ValueError:
                    event_time = datetime.utcnow()
        elif not isinstance(event_time, datetime):
            event_time = datetime.utcnow()
        
        factors['off_hours_likely'] = self._is_likely_off_hours(event_time.time())
        
        # Public repository check
        factors['public_repo'] = repo_info.get('visibility') == 'public'
        
        return factors
    
    def _analyze_urgency_indicators(self, context_data: Dict[str, Any], incident_type: str) -> Dict[str, bool]:
        """Analyze data for urgency indicators"""
        indicators = {}
        
        # Secrets exposure check
        indicators['secrets_exposed'] = (
            incident_type == 'secret_exposure' or
            'secret' in context_data.get('detection_keywords', []) or
            context_data.get('contains_secrets', False)
        )
        
        # Mass deletion check
        indicators['mass_deletion'] = (
            incident_type == 'mass_deletion' or
            context_data.get('deletion_count', 0) >= 3
        )
        
        # Coordinated attack check
        actor_count = len(context_data.get('unique_actors', []))
        event_rate = context_data.get('events_per_minute', 0)
        indicators['coordinated_attack'] = (
            actor_count >= 3 and event_rate > 5 or
            context_data.get('is_coordinated', False)
        )
        
        # Privilege escalation check
        indicators['privilege_escalation'] = (
            'privilege' in incident_type.lower() or
            context_data.get('permission_changes', False) or
            'admin' in str(context_data.get('payload', {})).lower()
        )
        
        # Force push to main branch
        ref = context_data.get('ref', '')
        indicators['force_push_main'] = (
            context_data.get('forced', False) and
            any(branch in ref.lower() for branch in ['main', 'master'])
        )
        
        # Build failure cascade
        failure_count = context_data.get('consecutive_failures', 0)
        indicators['build_failure_cascade'] = failure_count >= 3
        
        return indicators
    
    def _is_likely_off_hours(self, event_time_gmt: time) -> bool:
        """
        Check if GMT time is likely to be off-hours for major development regions.
        
        Since we don't have user geolocation, we use statistical analysis:
        - Most GitHub activity comes from US (PST/EST), Europe (CET), and Asia (JST/IST)
        - We identify time windows that are likely to be off-hours for majority of these regions
        """
        for start_time, end_time in self.likely_off_hours_gmt:
            if start_time <= end_time:
                # Normal time range (doesn't cross midnight)
                if start_time <= event_time_gmt <= end_time:
                    return True
            else:
                # Time range crosses midnight
                if event_time_gmt >= start_time or event_time_gmt <= end_time:
                    return True
        
        return False
    
    def _add_scoring_explanation(self, score: AnomalyScore, context_data: Dict[str, Any]):
        """Add detailed explanation of scoring rationale"""
        
        # Component breakdown
        score.add_explanation('component_breakdown', {
            'behavioral_weight': self.default_weights['behavioral'],
            'content_weight': self.default_weights['content'],
            'temporal_weight': self.default_weights['temporal'],
            'repository_weight': self.default_weights['repository']
        })
        
        # Scoring formula
        score.add_explanation('formula', {
            'base_score': f"{score.behavioral_anomaly:.3f} * 0.25 + {score.content_risk:.3f} * 0.35 + "
                         f"{score.temporal_anomaly:.3f} * 0.20 + {score.repository_criticality:.3f} * 0.20 = {score.base_score:.3f}",
            'context_multiplier': score.context_multiplier,
            'urgency_factor': score.urgency_factor,
            'final_calculation': f"min(1.0, {score.base_score:.3f} * {score.context_multiplier:.2f} * {score.urgency_factor:.2f}) = {score.final_score:.3f}"
        })
        
        # GMT timezone note
        event_time = context_data.get('timestamp')
        if event_time:
            score.add_explanation('timezone_note', {
                'event_time_gmt': str(event_time),
                'off_hours_detection': 'Based on statistical likelihood for major development regions (US, Europe, Asia)',
                'limitation': 'User geolocation not available - using GMT-based heuristics'
            })
        
        # Threshold explanation
        score.add_explanation('severity_thresholds', {
            'critical': '0.85 - 1.0 (Auto-escalate)',
            'high': '0.65 - 0.84 (Security team notification)',
            'medium': '0.45 - 0.64 (Daily digest)',
            'low': '0.20 - 0.44 (Weekly report)',
            'info': '0.0 - 0.19 (Log only)'
        })
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update engine configuration"""
        self.config.update(new_config)
        
        if 'component_weights' in new_config:
            # Validate weights sum to 1.0
            weights = new_config['component_weights']
            weight_sum = sum(weights.values())
            if abs(weight_sum - 1.0) > 0.01:
                logger.warning(f"Component weights sum to {weight_sum}, not 1.0")
        
        if 'context_multipliers' in new_config:
            self.context_multipliers.update(new_config['context_multipliers'])
        
        if 'urgency_factors' in new_config:
            self.urgency_factors.update(new_config['urgency_factors'])
        
        if 'off_hours_gmt_ranges' in new_config:
            # Allow customization of off-hours ranges
            self.likely_off_hours_gmt = new_config['off_hours_gmt_ranges']
    
    def get_severity_statistics(self, scores: List[AnomalyScore]) -> Dict[str, Any]:
        """Generate statistics for a list of anomaly scores"""
        if not scores:
            return {}
        
        final_scores = [s.final_score for s in scores]
        severity_counts = {}
        
        for level in SeverityLevel:
            severity_counts[level.level_name] = sum(
                1 for s in scores if s.severity_level == level
            )
        
        return {
            'total_incidents': len(scores),
            'average_score': sum(final_scores) / len(final_scores),
            'max_score': max(final_scores),
            'min_score': min(final_scores),
            'severity_distribution': severity_counts,
            'escalation_rate': severity_counts.get('critical', 0) / len(scores) if scores else 0
        }