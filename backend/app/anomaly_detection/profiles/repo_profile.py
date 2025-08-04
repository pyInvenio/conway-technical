from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import json
import logging
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import asyncio

logger = logging.getLogger(__name__)

class RepositoryProfileManager:
    """Repository profiling system for activity patterns and contributor behavior"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        
        # Profile configuration
        self.profile_ttl = 7 * 24 * 3600  # 7 days (shorter than user profiles)
        self.max_contributor_history = 50   # Maximum contributors to track
        self.min_events_for_profile = 10    # Minimum events for reliable profile
        self.profile_update_interval = 1800  # Update at most every 30 minutes
        
        # EWMA parameters
        self.alpha_activity = 0.4   # For activity patterns
        self.alpha_contributors = 0.2  # For contributor patterns (slower)
        
        # Repository profile feature names
        self.repo_feature_names = [
            'avg_events_per_day',
            'avg_unique_contributors_per_day',
            'avg_commits_per_push',
            'avg_files_changed_per_commit',
            'contributor_diversity_score',
            'activity_regularity_score',
            'peak_activity_hour',
            'weekend_activity_ratio',
            'build_success_rate',
            'issue_resolution_rate'
        ]
        
        # Event type weights for repository health scoring
        self.event_type_weights = {
            'PushEvent': 1.0,
            'PullRequestEvent': 1.2,  # Collaborative development
            'IssuesEvent': 0.8,       # Issue activity
            'WorkflowRunEvent': 0.9,  # CI/CD activity
            'ReleaseEvent': 1.5,      # Release activity
            'CreateEvent': 0.7,       # Branch/tag creation
            'DeleteEvent': 0.5,       # Deletion events
            'ForkEvent': 0.6,         # Fork activity
            'WatchEvent': 0.3         # Watch activity
        }
    
    async def get_or_create_repo_profile(self, repo_name: str) -> Dict[str, Any]:
        """Get existing repository profile or create new one"""
        
        # Try to get existing profile
        profile = await self._get_repo_profile(repo_name)
        
        if profile is None:
            # Create new profile
            profile = self._create_empty_repo_profile(repo_name)
            await self._save_repo_profile(repo_name, profile)
        
        return profile
    
    async def update_repo_profile(
        self,
        repo_name: str,
        events: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Update repository profile with new activity data"""
        
        # Get existing profile
        profile = await self.get_or_create_repo_profile(repo_name)
        
        # Check if we should update (rate limiting)
        if not self._should_update_profile(profile):
            return profile
        
        # Extract activity patterns from events
        activity_patterns = self._extract_activity_patterns(events)
        
        # Update profile with new data
        updated_profile = await self._update_profile_with_patterns(
            profile, activity_patterns, events
        )
        
        # Save updated profile
        await self._save_repo_profile(repo_name, updated_profile)
        
        return updated_profile
    
    async def analyze_repo_activity_anomalies(
        self,
        repo_name: str,
        current_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze current repository activity against historical patterns"""
        
        profile = await self._get_repo_profile(repo_name)
        
        if not profile or profile['total_events'] < self.min_events_for_profile:
            return {
                'has_baseline': False,
                'activity_anomaly_score': 0.0,
                'anomalous_patterns': [],
                'analysis_type': 'insufficient_baseline'
            }
        
        # Extract current activity patterns
        current_patterns = self._extract_activity_patterns(current_events)
        
        # Compare with baseline
        anomalies = self._detect_repository_anomalies(profile, current_patterns)
        
        # Calculate overall anomaly score
        anomaly_score = self._calculate_repo_anomaly_score(anomalies)
        
        return {
            'has_baseline': True,
            'activity_anomaly_score': float(anomaly_score),
            'anomalous_patterns': anomalies,
            'current_patterns': current_patterns,
            'baseline_patterns': self._extract_baseline_patterns(profile),
            'analysis_type': 'full_repository_analysis'
        }
    
    def _extract_activity_patterns(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract activity patterns from events"""
        if not events:
            return {}
        
        patterns = {}
        
        # Basic activity metrics
        patterns['total_events'] = len(events)
        patterns['unique_actors'] = len(set(e.get('actor_login') for e in events if e.get('actor_login')))
        
        # Time span analysis
        timestamps = []
        for event in events:
            timestamp_str = event.get('created_at')
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    timestamps.append(dt)
                except (ValueError, AttributeError):
                    pass
        
        if len(timestamps) >= 2:
            timestamps.sort()
            time_span_hours = (timestamps[-1] - timestamps[0]).total_seconds() / 3600
            patterns['time_span_hours'] = max(time_span_hours, 1.0)
            patterns['events_per_hour'] = len(events) / patterns['time_span_hours']
            
            # Hour-of-day distribution
            hours = [ts.hour for ts in timestamps]
            hour_counts = Counter(hours)
            patterns['hourly_distribution'] = dict(hour_counts)
            patterns['peak_activity_hour'] = hour_counts.most_common(1)[0][0] if hour_counts else 12
            
            # Weekend activity
            weekend_events = sum(1 for ts in timestamps if ts.weekday() >= 5)
            patterns['weekend_activity_ratio'] = weekend_events / len(timestamps)
        else:
            patterns['time_span_hours'] = 1.0
            patterns['events_per_hour'] = len(events)
            patterns['hourly_distribution'] = {}
            patterns['peak_activity_hour'] = 12
            patterns['weekend_activity_ratio'] = 0.0
        
        # Event type analysis
        event_types = [e.get('type', 'unknown') for e in events]
        type_counts = Counter(event_types)
        patterns['event_type_distribution'] = dict(type_counts)
        
        # Push event analysis
        push_events = [e for e in events if e.get('type') == 'PushEvent']
        if push_events:
            commit_counts = []
            for event in push_events:
                commits = event.get('payload', {}).get('commits', [])
                commit_counts.append(len(commits))
            
            patterns['avg_commits_per_push'] = np.mean(commit_counts) if commit_counts else 0
            patterns['total_commits'] = sum(commit_counts)
        else:
            patterns['avg_commits_per_push'] = 0
            patterns['total_commits'] = 0
        
        # Workflow/build analysis
        workflow_events = [e for e in events if e.get('type') == 'WorkflowRunEvent']
        if workflow_events:
            successful_workflows = 0
            total_workflows = 0
            
            for event in workflow_events:
                workflow_run = event.get('payload', {}).get('workflow_run', {})
                if workflow_run.get('conclusion'):
                    total_workflows += 1
                    if workflow_run.get('conclusion') == 'success':
                        successful_workflows += 1
            
            patterns['build_success_rate'] = successful_workflows / max(total_workflows, 1)
            patterns['total_workflows'] = total_workflows
        else:
            patterns['build_success_rate'] = 1.0  # Assume success if no data
            patterns['total_workflows'] = 0
        
        # Issue analysis
        issue_events = [e for e in events if e.get('type') == 'IssuesEvent']
        if issue_events:
            closed_issues = sum(1 for e in issue_events 
                              if e.get('payload', {}).get('action') == 'closed')
            opened_issues = sum(1 for e in issue_events 
                              if e.get('payload', {}).get('action') == 'opened')
            
            patterns['issue_resolution_rate'] = closed_issues / max(opened_issues, 1)
            patterns['total_issue_events'] = len(issue_events)
        else:
            patterns['issue_resolution_rate'] = 1.0  # Assume good resolution if no data
            patterns['total_issue_events'] = 0
        
        # Contributor diversity
        if patterns['unique_actors'] > 1:
            actor_event_counts = Counter(e.get('actor_login') for e in events if e.get('actor_login'))
            event_counts = list(actor_event_counts.values())
            
            # Shannon entropy for contributor diversity
            total_events = sum(event_counts)
            probabilities = [count / total_events for count in event_counts]
            entropy = -sum(p * np.log2(p + 1e-10) for p in probabilities)
            max_entropy = np.log2(len(event_counts))
            
            patterns['contributor_diversity_score'] = entropy / max_entropy if max_entropy > 0 else 0
        else:
            patterns['contributor_diversity_score'] = 0.0
        
        # Activity regularity (coefficient of variation of inter-event intervals)
        if len(timestamps) > 2:
            intervals = [(timestamps[i+1] - timestamps[i]).total_seconds() 
                        for i in range(len(timestamps)-1)]
            mean_interval = np.mean(intervals)
            std_interval = np.std(intervals)
            cv = std_interval / (mean_interval + 1e-10)
            patterns['activity_regularity_score'] = 1.0 / (1.0 + cv)  # Higher = more regular
        else:
            patterns['activity_regularity_score'] = 0.5
        
        return patterns
    
    def _create_empty_repo_profile(self, repo_name: str) -> Dict[str, Any]:
        """Create empty repository profile"""
        now = datetime.utcnow().isoformat()
        
        return {
            'repo_name': repo_name,
            'total_events': 0,
            'first_seen': now,
            'last_updated': now,
            'avg_events_per_day': 0.0,
            'avg_unique_contributors_per_day': 0.0,
            'avg_commits_per_push': 0.0,
            'contributor_diversity_score': 0.0,
            'activity_regularity_score': 0.5,
            'peak_activity_hour': 12,
            'weekend_activity_ratio': 0.0,
            'build_success_rate': 1.0,
            'issue_resolution_rate': 1.0,
            'hourly_distribution': np.zeros(24).tolist(),
            'event_type_distribution': {},
            'top_contributors': [],
            'activity_history': [],
            'profile_version': '1.0'
        }
    
    async def _update_profile_with_patterns(
        self,
        profile: Dict[str, Any],
        activity_patterns: Dict[str, Any],
        events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Update repository profile with new activity patterns using EWMA"""
        
        if not activity_patterns:
            return profile
        
        # Calculate time-based metrics
        days_since_first_seen = max(
            (datetime.utcnow() - datetime.fromisoformat(profile['first_seen'])).days,
            1
        )
        
        new_events_count = len(events)
        old_total_events = profile['total_events']
        new_total_events = old_total_events + new_events_count
        
        # Update basic metrics using EWMA
        new_events_per_day = activity_patterns.get('events_per_hour', 0) * 24
        old_events_per_day = profile['avg_events_per_day']
        updated_events_per_day = (
            self.alpha_activity * new_events_per_day +
            (1 - self.alpha_activity) * old_events_per_day
        )
        
        # Update contributor metrics
        new_contributors_per_day = activity_patterns.get('unique_actors', 0) / max(activity_patterns.get('time_span_hours', 24) / 24, 1)
        old_contributors_per_day = profile['avg_unique_contributors_per_day']
        updated_contributors_per_day = (
            self.alpha_contributors * new_contributors_per_day +
            (1 - self.alpha_contributors) * old_contributors_per_day
        )
        
        # Update other EWMA metrics
        ewma_updates = {
            'avg_commits_per_push': activity_patterns.get('avg_commits_per_push', 0),
            'contributor_diversity_score': activity_patterns.get('contributor_diversity_score', 0),
            'activity_regularity_score': activity_patterns.get('activity_regularity_score', 0.5),
            'weekend_activity_ratio': activity_patterns.get('weekend_activity_ratio', 0),
            'build_success_rate': activity_patterns.get('build_success_rate', 1.0),
            'issue_resolution_rate': activity_patterns.get('issue_resolution_rate', 1.0)
        }
        
        updated_profile = profile.copy()
        
        for key, new_value in ewma_updates.items():
            old_value = profile.get(key, 0)
            updated_value = self.alpha_activity * new_value + (1 - self.alpha_activity) * old_value
            updated_profile[key] = updated_value
        
        # Update hourly distribution
        old_hourly = np.array(profile.get('hourly_distribution', np.zeros(24)))
        new_hourly = np.zeros(24)
        
        for hour, count in activity_patterns.get('hourly_distribution', {}).items():
            new_hourly[hour] = count
        
        # Normalize new distribution
        if np.sum(new_hourly) > 0:
            new_hourly = new_hourly / np.sum(new_hourly)
        
        # EWMA update
        updated_hourly = self.alpha_activity * new_hourly + (1 - self.alpha_activity) * old_hourly
        updated_profile['hourly_distribution'] = updated_hourly.tolist()
        updated_profile['peak_activity_hour'] = int(np.argmax(updated_hourly))
        
        # Update event type distribution
        old_event_types = profile.get('event_type_distribution', {})
        new_event_types = activity_patterns.get('event_type_distribution', {})
        
        all_types = set(old_event_types.keys()) | set(new_event_types.keys())
        updated_event_types = {}
        
        total_new_events = sum(new_event_types.values()) if new_event_types else 1
        
        for event_type in all_types:
            old_count = old_event_types.get(event_type, 0)
            new_count = new_event_types.get(event_type, 0)
            new_prob = new_count / total_new_events
            old_prob = old_count / max(old_total_events, 1)
            
            updated_prob = self.alpha_activity * new_prob + (1 - self.alpha_activity) * old_prob
            if updated_prob > 0.01:  # Keep only significant event types
                updated_event_types[event_type] = updated_prob * new_total_events
        
        # Update contributor list
        contributors = [e.get('actor_login') for e in events if e.get('actor_login')]
        contributor_counts = Counter(contributors)
        
        old_contributors = {c['name']: c['count'] for c in profile.get('top_contributors', [])}
        
        all_contributors = set(old_contributors.keys()) | set(contributor_counts.keys())
        updated_contributors = []
        
        for contributor in all_contributors:
            old_count = old_contributors.get(contributor, 0)
            new_count = contributor_counts.get(contributor, 0)
            updated_count = int(self.alpha_contributors * new_count + (1 - self.alpha_contributors) * old_count)
            
            if updated_count > 0:
                updated_contributors.append({'name': contributor, 'count': updated_count})
        
        # Sort and keep top contributors
        updated_contributors.sort(key=lambda x: x['count'], reverse=True)
        updated_contributors = updated_contributors[:self.max_contributor_history]
        
        # Update activity history (sliding window)
        activity_summary = {
            'timestamp': datetime.utcnow().isoformat(),
            'events_count': new_events_count,
            'unique_contributors': activity_patterns.get('unique_actors', 0),
            'commits': activity_patterns.get('total_commits', 0),
            'workflows': activity_patterns.get('total_workflows', 0)
        }
        
        activity_history = profile.get('activity_history', [])
        activity_history.append(activity_summary)
        if len(activity_history) > 50:  # Keep last 50 activity windows
            activity_history = activity_history[-50:]
        
        # Finalize profile updates
        updated_profile.update({
            'total_events': new_total_events,
            'last_updated': datetime.utcnow().isoformat(),
            'avg_events_per_day': updated_events_per_day,
            'avg_unique_contributors_per_day': updated_contributors_per_day,
            'event_type_distribution': updated_event_types,
            'top_contributors': updated_contributors,
            'activity_history': activity_history
        })
        
        return updated_profile
    
    def _detect_repository_anomalies(
        self,
        profile: Dict[str, Any],
        current_patterns: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies in repository activity patterns"""
        anomalies = []
        
        # Activity rate anomaly
        baseline_rate = profile['avg_events_per_day']
        current_rate = current_patterns.get('events_per_hour', 0) * 24
        
        if baseline_rate > 0:
            rate_ratio = current_rate / baseline_rate
            if rate_ratio > 3.0:  # 3x normal activity
                anomalies.append({
                    'type': 'high_activity_burst',
                    'severity': min((rate_ratio - 1) / 5, 1.0),
                    'current_rate': current_rate,
                    'baseline_rate': baseline_rate,
                    'rate_multiplier': rate_ratio
                })
            elif rate_ratio < 0.2:  # Very low activity
                anomalies.append({
                    'type': 'low_activity_period',
                    'severity': min((1 - rate_ratio) / 2, 1.0),
                    'current_rate': current_rate,
                    'baseline_rate': baseline_rate,
                    'rate_multiplier': rate_ratio
                })
        
        # Contributor anomaly
        baseline_contributors = profile['avg_unique_contributors_per_day']
        current_contributors = current_patterns.get('unique_actors', 0)
        
        if baseline_contributors > 0:
            contributor_ratio = current_contributors / baseline_contributors
            if contributor_ratio > 2.0:  # Unusual number of contributors
                anomalies.append({
                    'type': 'unusual_contributor_surge',
                    'severity': min((contributor_ratio - 1) / 3, 1.0),
                    'current_contributors': current_contributors,
                    'baseline_contributors': baseline_contributors
                })
        
        # Build failure anomaly
        baseline_success_rate = profile['build_success_rate']
        current_success_rate = current_patterns.get('build_success_rate', 1.0)
        
        if current_success_rate < baseline_success_rate - 0.3:  # 30% drop in success rate
            anomalies.append({
                'type': 'build_failure_increase',
                'severity': min((baseline_success_rate - current_success_rate) / 0.5, 1.0),
                'current_success_rate': current_success_rate,
                'baseline_success_rate': baseline_success_rate
            })
        
        # Time pattern anomaly (significant change in activity hours)
        baseline_peak_hour = profile['peak_activity_hour']
        current_peak_hour = current_patterns.get('peak_activity_hour', 12)
        
        hour_diff = min(abs(current_peak_hour - baseline_peak_hour), 
                       24 - abs(current_peak_hour - baseline_peak_hour))
        
        if hour_diff > 6:  # More than 6 hours difference
            anomalies.append({
                'type': 'activity_time_shift',
                'severity': min(hour_diff / 12, 1.0),
                'current_peak_hour': current_peak_hour,
                'baseline_peak_hour': baseline_peak_hour,
                'hour_difference': hour_diff
            })
        
        return anomalies
    
    def _calculate_repo_anomaly_score(self, anomalies: List[Dict[str, Any]]) -> float:
        """Calculate overall repository anomaly score"""
        if not anomalies:
            return 0.0
        
        # Weight different anomaly types
        weights = {
            'high_activity_burst': 0.8,
            'low_activity_period': 0.4,
            'unusual_contributor_surge': 0.7,
            'build_failure_increase': 0.9,
            'activity_time_shift': 0.5
        }
        
        total_score = 0.0
        total_weight = 0.0
        
        for anomaly in anomalies:
            anomaly_type = anomaly['type']
            severity = anomaly['severity']
            weight = weights.get(anomaly_type, 0.5)
            
            total_score += severity * weight
            total_weight += weight
        
        if total_weight > 0:
            return min(total_score / total_weight, 1.0)
        
        return 0.0
    
    def _extract_baseline_patterns(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Extract baseline patterns from profile for comparison"""
        return {
            'avg_events_per_day': profile['avg_events_per_day'],
            'avg_contributors_per_day': profile['avg_unique_contributors_per_day'],
            'peak_activity_hour': profile['peak_activity_hour'],
            'weekend_activity_ratio': profile['weekend_activity_ratio'],
            'build_success_rate': profile['build_success_rate'],
            'contributor_diversity_score': profile['contributor_diversity_score'],
            'top_contributors': profile.get('top_contributors', [])[:5]
        }
    
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
    
    async def _get_repo_profile(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get repository profile from Redis"""
        if not self.redis_client:
            return None
        
        try:
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_profile_v2:{safe_repo_name}"
            profile_data = await self.redis_client.get(cache_key)
            
            if profile_data:
                return json.loads(profile_data)
        except Exception as e:
            logger.warning(f"Failed to get repo profile for {repo_name}: {e}")
        
        return None
    
    async def _save_repo_profile(self, repo_name: str, profile: Dict[str, Any]):
        """Save repository profile to Redis"""
        if not self.redis_client:
            return
        
        try:
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_profile_v2:{safe_repo_name}"
            await self.redis_client.setex(
                cache_key,
                self.profile_ttl,
                json.dumps(profile, default=str)
            )
        except Exception as e:
            logger.error(f"Failed to save repo profile for {repo_name}: {e}")
    
    async def get_repo_health_summary(self, repo_name: str) -> Dict[str, Any]:
        """Get repository health summary"""
        profile = await self._get_repo_profile(repo_name)
        
        if not profile:
            return {'exists': False}
        
        # Calculate health score
        health_factors = {
            'activity_level': min(profile['avg_events_per_day'] / 10, 1.0),  # Normalize by 10 events/day
            'contributor_diversity': profile['contributor_diversity_score'],
            'build_success_rate': profile['build_success_rate'],
            'issue_resolution_rate': profile['issue_resolution_rate'],
            'activity_regularity': profile['activity_regularity_score']
        }
        
        health_score = np.mean(list(health_factors.values()))
        
        return {
            'exists': True,
            'repo_name': repo_name,
            'health_score': float(health_score),
            'health_factors': health_factors,
            'activity_summary': {
                'avg_events_per_day': profile['avg_events_per_day'],
                'avg_contributors_per_day': profile['avg_unique_contributors_per_day'],
                'peak_activity_hour': profile['peak_activity_hour'],
                'weekend_activity_ratio': profile['weekend_activity_ratio']
            },
            'quality_indicators': {
                'build_success_rate': profile['build_success_rate'],
                'issue_resolution_rate': profile['issue_resolution_rate'],
                'contributor_diversity': profile['contributor_diversity_score']
            },
            'top_contributors': profile.get('top_contributors', [])[:10],
            'profile_age_days': (datetime.utcnow() - datetime.fromisoformat(profile['first_seen'])).days,
            'last_updated': profile['last_updated']
        }