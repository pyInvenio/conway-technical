from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import asyncio

logger = logging.getLogger(__name__)

class UserProfileManager:
    """User profiling system for behavioral baseline management using numpy arrays"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        
        # Profile configuration
        self.profile_ttl = 30 * 24 * 3600  # 30 days
        self.max_feature_history = 100     # Maximum historical feature vectors to store
        self.min_events_for_profile = 20   # Minimum events needed for reliable profile
        self.profile_update_interval = 3600  # Update profile at most once per hour
        
        # EWMA parameters for different metrics
        self.alpha_fast = 0.3   # For quickly adapting metrics
        self.alpha_slow = 0.1   # For slowly adapting baselines
        
        # User profile feature names (synchronized with behavioral detector)
        self.profile_feature_names = [
            'avg_events_per_hour',
            'avg_repo_diversity_ratio',
            'avg_inter_event_interval_minutes',
            'avg_commit_message_length',
            'avg_files_changed_per_commit',
            'avg_activity_burst_score',
            'avg_time_spread_hours',
            'avg_event_type_entropy',
            'avg_weekend_activity_ratio',
            'avg_off_hours_activity_ratio'
        ]
        
        # Event type mappings (consistent with behavioral detector)
        self.event_type_mapping = {
            'PushEvent': 0, 'PullRequestEvent': 1, 'IssuesEvent': 2,
            'WorkflowRunEvent': 3, 'CreateEvent': 4, 'DeleteEvent': 5,
            'ForkEvent': 6, 'WatchEvent': 7, 'ReleaseEvent': 8, 'other': 9
        }
    
    async def get_or_create_user_profile(self, user_login: str) -> Dict[str, Any]:
        """Get existing user profile or create new one"""
        
        # Try to get existing profile
        profile = await self._get_user_profile(user_login)
        
        if profile is None:
            # Create new profile
            profile = self._create_empty_profile(user_login)
            await self._save_user_profile(user_login, profile)
        
        return profile
    
    async def update_user_profile(
        self, 
        user_login: str, 
        new_features: np.ndarray,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update user profile with new behavioral features using EWMA"""
        
        # Get existing profile
        profile = await self.get_or_create_user_profile(user_login)
        
        # Check if we should update (rate limiting)
        if not self._should_update_profile(profile):
            return profile
        
        # Update profile with new data
        updated_profile = await self._update_profile_with_ewma(
            profile, new_features, events
        )
        
        # Save updated profile
        await self._save_user_profile(user_login, updated_profile)
        
        return updated_profile
    
    async def get_user_baseline(self, user_login: str) -> Optional[Dict[str, Any]]:
        """Get user's behavioral baseline for anomaly detection"""
        profile = await self._get_user_profile(user_login)
        
        if not profile or profile['total_events'] < self.min_events_for_profile:
            return None
        
        return {
            'mean_features': np.array(profile['mean_features']),
            'std_features': np.array(profile['std_features']),
            'feature_history': np.array(profile.get('feature_history', [])),
            'sample_count': profile['total_events'],
            'confidence_score': min(profile['total_events'] / 100, 1.0),
            'last_updated': profile['last_updated']
        }
    
    async def analyze_user_behavior_change(
        self, 
        user_login: str, 
        current_features: np.ndarray
    ) -> Dict[str, Any]:
        """Analyze how user's current behavior differs from their profile"""
        
        profile = await self._get_user_profile(user_login)
        
        if not profile or profile['total_events'] < self.min_events_for_profile:
            return {
                'has_baseline': False,
                'behavior_change_score': 0.0,
                'changed_features': [],
                'analysis_type': 'insufficient_baseline'
            }
        
        baseline_mean = np.array(profile['mean_features'])
        baseline_std = np.array(profile['std_features'])
        
        # Calculate z-scores for each feature
        z_scores = np.abs((current_features - baseline_mean) / (baseline_std + 1e-10))
        
        # Identify significantly changed features
        change_threshold = 2.0  # 2 standard deviations
        changed_features = []
        
        for i, (z_score, feature_name) in enumerate(zip(z_scores, self.profile_feature_names)):
            if z_score > change_threshold:
                change_direction = 'increase' if current_features[i] > baseline_mean[i] else 'decrease'
                changed_features.append({
                    'feature_name': feature_name,
                    'feature_index': i,
                    'z_score': float(z_score),
                    'current_value': float(current_features[i]),
                    'baseline_mean': float(baseline_mean[i]),
                    'baseline_std': float(baseline_std[i]),
                    'change_direction': change_direction,
                    'percent_change': float(((current_features[i] - baseline_mean[i]) / (baseline_mean[i] + 1e-10)) * 100)
                })
        
        # Calculate overall behavior change score
        behavior_change_score = np.mean(z_scores) / 5.0  # Normalize by expected max z-score
        behavior_change_score = min(behavior_change_score, 1.0)
        
        return {
            'has_baseline': True,
            'behavior_change_score': float(behavior_change_score),
            'changed_features': changed_features,
            'total_features_changed': len(changed_features),
            'max_z_score': float(np.max(z_scores)),
            'analysis_type': 'full_baseline_comparison'
        }
    
    async def get_user_activity_summary(self, user_login: str) -> Dict[str, Any]:
        """Get summary of user's activity patterns"""
        profile = await self._get_user_profile(user_login)
        
        if not profile:
            return {'exists': False}
        
        return {
            'exists': True,
            'user_login': user_login,
            'total_events': profile['total_events'],
            'first_seen': profile['first_seen'],
            'last_updated': profile['last_updated'],
            'profile_age_days': (datetime.utcnow() - datetime.fromisoformat(profile['first_seen'])).days,
            'avg_events_per_day': profile['total_events'] / max((datetime.utcnow() - datetime.fromisoformat(profile['first_seen'])).days, 1),
            'behavioral_features': {
                name: value for name, value in zip(self.profile_feature_names, profile['mean_features'])
            },
            'activity_patterns': {
                'most_active_hour': profile.get('most_active_hour', 'unknown'),
                'preferred_repos': profile.get('top_repositories', [])[:5],
                'common_event_types': profile.get('event_type_distribution', {}),
                'weekend_activity_level': profile['mean_features'][8] if len(profile['mean_features']) > 8 else 0.0
            },
            'confidence_indicators': {
                'has_sufficient_data': profile['total_events'] >= self.min_events_for_profile,
                'data_freshness_hours': (datetime.utcnow() - datetime.fromisoformat(profile['last_updated'])).total_seconds() / 3600,
                'profile_stability_score': self._calculate_profile_stability(profile)
            }
        }
    
    def _create_empty_profile(self, user_login: str) -> Dict[str, Any]:
        """Create empty user profile"""
        now = datetime.utcnow().isoformat()
        
        return {
            'user_login': user_login,
            'total_events': 0,
            'first_seen': now,
            'last_updated': now,
            'mean_features': np.zeros(len(self.profile_feature_names)).tolist(),
            'std_features': np.ones(len(self.profile_feature_names)).tolist(),  # Start with 1.0 std
            'feature_history': [],
            'event_type_distribution': {},
            'hourly_activity_distribution': np.zeros(24).tolist(),
            'top_repositories': [],
            'most_active_hour': 12,  # Default noon
            'profile_version': '1.0'
        }
    
    async def _update_profile_with_ewma(
        self, 
        profile: Dict[str, Any], 
        new_features: np.ndarray,
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update profile using EWMA for behavioral features"""
        
        # Convert existing features to numpy arrays
        old_mean = np.array(profile['mean_features'])
        old_std = np.array(profile['std_features'])
        
        # Update mean using EWMA
        if profile['total_events'] == 0:
            # First update - use new features as baseline
            new_mean = new_features.copy()
            new_std = np.ones(len(new_features)) * 0.1  # Small initial variance
        else:
            # EWMA update
            new_mean = self.alpha_fast * new_features + (1 - self.alpha_fast) * old_mean
            
            # Update variance using EWMA
            variance_old = old_std ** 2
            variance_new = (new_features - new_mean) ** 2
            variance_updated = self.alpha_slow * variance_new + (1 - self.alpha_slow) * variance_old
            new_std = np.sqrt(variance_updated)
        
        # Update feature history (sliding window)
        feature_history = profile.get('feature_history', [])
        feature_history.append(new_features.tolist())
        if len(feature_history) > self.max_feature_history:
            feature_history = feature_history[-self.max_feature_history:]
        
        # Update event type distribution
        event_types = [e.get('type', 'other') for e in events]
        type_counts = Counter(event_types)
        
        old_distribution = profile.get('event_type_distribution', {})
        new_distribution = {}
        
        # EWMA update for event type distribution
        all_types = set(old_distribution.keys()) | set(type_counts.keys())
        total_new_events = len(events)
        
        for event_type in all_types:
            old_prob = old_distribution.get(event_type, 0.0)
            new_count = type_counts.get(event_type, 0)
            new_prob = new_count / max(total_new_events, 1)
            
            updated_prob = self.alpha_fast * new_prob + (1 - self.alpha_fast) * old_prob
            if updated_prob > 0.01:  # Only keep significant probabilities
                new_distribution[event_type] = updated_prob
        
        # Update hourly activity distribution
        old_hourly = np.array(profile.get('hourly_activity_distribution', np.zeros(24)))
        new_hourly = np.zeros(24)
        
        for event in events:
            timestamp_str = event.get('created_at')
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    new_hourly[dt.hour] += 1
                except (ValueError, AttributeError):
                    pass
        
        # Normalize new hourly distribution
        if np.sum(new_hourly) > 0:
            new_hourly = new_hourly / np.sum(new_hourly)
        
        # EWMA update for hourly distribution
        updated_hourly = self.alpha_fast * new_hourly + (1 - self.alpha_fast) * old_hourly
        most_active_hour = int(np.argmax(updated_hourly))
        
        # Update repository preferences
        repos = [e.get('repo_name') for e in events if e.get('repo_name')]
        repo_counts = Counter(repos)
        
        old_repos = profile.get('top_repositories', [])
        # Simple approach: blend old and new top repos
        all_repo_names = set([r['name'] for r in old_repos] + list(repo_counts.keys()))
        
        updated_repos = []
        for repo_name in all_repo_names:
            old_count = next((r['count'] for r in old_repos if r['name'] == repo_name), 0)
            new_count = repo_counts.get(repo_name, 0)
            updated_count = int(self.alpha_fast * new_count + (1 - self.alpha_fast) * old_count)
            
            if updated_count > 0:
                updated_repos.append({'name': repo_name, 'count': updated_count})
        
        # Sort and keep top 20
        updated_repos.sort(key=lambda x: x['count'], reverse=True)
        updated_repos = updated_repos[:20]
        
        # Create updated profile
        updated_profile = profile.copy()
        updated_profile.update({
            'total_events': profile['total_events'] + len(events),
            'last_updated': datetime.utcnow().isoformat(),
            'mean_features': new_mean.tolist(),
            'std_features': new_std.tolist(),
            'feature_history': feature_history,
            'event_type_distribution': new_distribution,
            'hourly_activity_distribution': updated_hourly.tolist(),
            'top_repositories': updated_repos,
            'most_active_hour': most_active_hour
        })
        
        return updated_profile
    
    def _should_update_profile(self, profile: Dict[str, Any]) -> bool:
        """Check if profile should be updated (rate limiting)"""
        last_updated = profile.get('last_updated')
        if not last_updated:
            return True
        
        try:
            last_update_time = datetime.fromisoformat(last_updated)
            time_since_update = (datetime.utcnow() - last_update_time).total_seconds()
            return time_since_update >= self.profile_update_interval
        except (ValueError, AttributeError):
            return True
    
    def _calculate_profile_stability(self, profile: Dict[str, Any]) -> float:
        """Calculate how stable/consistent the user's profile is"""
        feature_history = profile.get('feature_history', [])
        
        if len(feature_history) < 5:
            return 0.5  # Neutral stability for insufficient data
        
        # Calculate coefficient of variation for recent features
        recent_features = np.array(feature_history[-10:])  # Last 10 feature vectors
        
        if len(recent_features) < 2:
            return 0.5
        
        # Calculate stability as inverse of average coefficient of variation
        feature_stds = np.std(recent_features, axis=0)
        feature_means = np.mean(recent_features, axis=0)
        
        cvs = feature_stds / (feature_means + 1e-10)  # Coefficient of variation
        avg_cv = np.mean(cvs)
        
        # Convert to stability score (lower CV = higher stability)
        stability = 1.0 / (1.0 + avg_cv)
        
        return float(stability)
    
    async def _get_user_profile(self, user_login: str) -> Optional[Dict[str, Any]]:
        """Get user profile from Redis"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"user_profile_v2:{user_login}"
            profile_data = await self.redis_client.get(cache_key)
            
            if profile_data:
                return json.loads(profile_data)
        except Exception as e:
            logger.warning(f"Failed to get user profile for {user_login}: {e}")
        
        return None
    
    async def _save_user_profile(self, user_login: str, profile: Dict[str, Any]):
        """Save user profile to Redis"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"user_profile_v2:{user_login}"
            await self.redis_client.setex(
                cache_key,
                self.profile_ttl,
                json.dumps(profile, default=str)
            )
        except Exception as e:
            logger.error(f"Failed to save user profile for {user_login}: {e}")
    
    async def get_multiple_user_profiles(self, user_logins: List[str]) -> Dict[str, Optional[Dict[str, Any]]]:
        """Get multiple user profiles efficiently"""
        profiles = {}
        
        for user_login in user_logins:
            profiles[user_login] = await self._get_user_profile(user_login)
        
        return profiles
    
    async def cleanup_stale_profiles(self, days_threshold: int = 90) -> int:
        """Clean up profiles that haven't been updated in specified days"""
        if not self.redis_client:
            return 0
        
        # This would require scanning Redis keys, which can be expensive
        # For now, we rely on TTL-based expiration
        logger.info(f"Profile cleanup relies on TTL expiration ({self.profile_ttl} seconds)")
        return 0
    
    def get_profile_feature_names(self) -> List[str]:
        """Get list of profile feature names"""
        return self.profile_feature_names.copy()