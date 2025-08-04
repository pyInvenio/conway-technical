from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import numpy as np
import logging
import json
from scipy import stats
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

class BehavioralAnomalyDetector:
    """Behavioral anomaly detection using EWMA and statistical analysis with numpy arrays"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        
        # EWMA configuration  
        self.alpha = 0.3  # Smoothing factor (higher = more weight to recent events)
        
        # Statistical thresholds
        self.z_score_threshold = 2.5  # Standard deviations for anomaly detection
        self.min_baseline_events = 3  # Minimum events needed for reliable baseline (lowered for Conway Technical demo)
        
        # Feature dimensions for numpy arrays
        self.feature_names = [
            'events_per_hour',
            'repository_diversity_ratio',
            'avg_inter_event_interval_minutes',
            'commit_message_length_avg',
            'files_changed_per_commit_avg',
            'activity_burst_score',
            'time_spread_hours',
            'event_type_entropy',
            'weekend_activity_ratio',
            'off_hours_activity_ratio'
        ]
        
        # Event type encoding for consistent numpy representation
        self.event_type_mapping = {
            'PushEvent': 0, 'PullRequestEvent': 1, 'IssuesEvent': 2,
            'WorkflowRunEvent': 3, 'CreateEvent': 4, 'DeleteEvent': 5,
            'ForkEvent': 6, 'WatchEvent': 7, 'ReleaseEvent': 8, 'other': 9
        }
        
        # Time of day buckets (GMT hours grouped)
        self.time_buckets = {
            'night': [0, 1, 2, 3, 4, 5],      # 00:00-05:59 GMT
            'morning': [6, 7, 8, 9, 10, 11],   # 06:00-11:59 GMT
            'afternoon': [12, 13, 14, 15, 16, 17], # 12:00-17:59 GMT
            'evening': [18, 19, 20, 21, 22, 23]    # 18:00-23:59 GMT
        }
        
        self.scaler = StandardScaler()
    
    async def analyze_user_behavior(
        self, 
        user_login: str, 
        recent_events: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze user behavior for anomalies using numpy arrays"""
        
        # Extract feature vector from recent events
        current_features = self._extract_feature_vector(recent_events)
        
        # Get user's historical feature vectors
        baseline_data = await self._get_user_baseline_arrays(user_login)
        
        if baseline_data is None or baseline_data['sample_count'] < self.min_baseline_events:
            logger.info(f"Insufficient baseline data for user {user_login}, using cold start")
            return self._cold_start_analysis_numpy(current_features, recent_events)
        
        # Detect anomalies using statistical methods on numpy arrays
        anomalies = self._detect_anomalies_numpy(current_features, baseline_data)
        
        # Calculate overall behavioral anomaly score
        behavioral_score = self._calculate_behavioral_score_numpy(anomalies, current_features)
        
        # Update user baseline with new feature vector
        await self._update_user_baseline_arrays(user_login, current_features, baseline_data)
        
        return {
            'behavioral_anomaly_score': float(behavioral_score),
            'detected_anomalies': anomalies,
            'current_features': current_features.tolist(),
            'feature_names': self.feature_names,
            'baseline_comparison': self._compare_with_baseline_numpy(current_features, baseline_data),
            'confidence': min(baseline_data['sample_count'] / 100, 1.0),
            'analysis_type': 'statistical_numpy'
        }
    
    def _extract_feature_vector(self, events: List[Dict[str, Any]]) -> np.ndarray:
        """Extract behavioral features as numpy array"""
        if not events:
            return np.zeros(len(self.feature_names))
        
        features = np.zeros(len(self.feature_names))
        
        # Convert events to numpy arrays for efficient processing
        timestamps = []
        event_types = []
        repos = set()
        commit_lengths = []
        files_changed = []
        
        for event in events:
            # Parse timestamp
            timestamp_str = event.get('created_at')
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    timestamps.append(dt)
                except (ValueError, AttributeError):
                    continue
            
            # Event type
            event_type = event.get('type', 'other')
            event_types.append(self.event_type_mapping.get(event_type, self.event_type_mapping['other']))
            
            # Repository
            repo_name = event.get('repo_name')
            if repo_name:
                repos.add(repo_name)
            
            # Commit-specific data
            if event_type == 'PushEvent':
                payload = event.get('payload', {})
                commits = payload.get('commits', [])
                
                for commit in commits:
                    message = commit.get('message', '')
                    commit_lengths.append(len(message))
                
                # Files changed (if available)
                size = payload.get('size', 0)
                if size > 0:
                    files_changed.append(size)
        
        if not timestamps:
            return features
        
        # Convert to numpy arrays
        timestamps = np.array(timestamps)
        event_types = np.array(event_types)
        
        # Feature 0: Events per hour
        time_span_hours = max((timestamps.max() - timestamps.min()).total_seconds() / 3600, 1.0)
        features[0] = len(events) / time_span_hours
        
        # Feature 1: Repository diversity ratio
        features[1] = len(repos) / len(events) if events else 0
        
        # Feature 2: Average inter-event interval (minutes)
        if len(timestamps) > 1:
            sorted_times = np.sort(timestamps)
            intervals = np.diff(sorted_times.astype('datetime64[s]')).astype(float) / 60  # Convert to minutes
            features[2] = np.mean(intervals)
        
        # Feature 3: Average commit message length
        if commit_lengths:
            features[3] = np.mean(commit_lengths)
        
        # Feature 4: Average files changed per commit
        if files_changed:
            features[4] = np.mean(files_changed)
        
        # Feature 5: Activity burst score
        features[5] = self._calculate_burst_score_numpy(timestamps)
        
        # Feature 6: Time spread (hours between first and last event)
        features[6] = time_span_hours
        
        # Feature 7: Event type entropy
        features[7] = self._calculate_entropy_numpy(event_types)
        
        # Feature 8: Weekend activity ratio
        features[8] = self._calculate_weekend_ratio_numpy(timestamps)
        
        # Feature 9: Off-hours activity ratio (likely off-hours in major timezones)
        features[9] = self._calculate_off_hours_ratio_numpy(timestamps)
        
        # Handle NaN values
        features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)
        
        return features
    
    def _calculate_burst_score_numpy(self, timestamps: np.ndarray) -> float:
        """Calculate activity burst score using numpy"""
        if len(timestamps) < 3:
            return 0.0
        
        # Sort timestamps and calculate intervals in minutes
        sorted_times = np.sort(timestamps)
        intervals = np.diff(sorted_times.astype('datetime64[s]')).astype(float) / 60
        
        # Detect bursts: sequences of intervals < 5 minutes
        burst_threshold = 5.0
        short_intervals = intervals < burst_threshold
        
        # Count consecutive sequences of short intervals (length >= 3)
        burst_sequences = 0
        consecutive_count = 0
        
        for is_short in short_intervals:
            if is_short:
                consecutive_count += 1
            else:
                if consecutive_count >= 3:
                    burst_sequences += 1
                consecutive_count = 0
        
        # Check final sequence
        if consecutive_count >= 3:
            burst_sequences += 1
        
        # Normalize by maximum possible sequences
        max_sequences = len(intervals) // 3
        return min(burst_sequences / max_sequences, 1.0) if max_sequences > 0 else 0.0
    
    def _calculate_entropy_numpy(self, values: np.ndarray) -> float:
        """Calculate Shannon entropy using numpy"""
        if len(values) == 0:
            return 0.0
        
        # Count unique values
        unique_values, counts = np.unique(values, return_counts=True)
        
        # Calculate probabilities
        probabilities = counts / len(values)
        
        # Calculate entropy
        entropy = -np.sum(probabilities * np.log2(probabilities + 1e-10))
        
        # Normalize by maximum possible entropy
        max_entropy = np.log2(len(unique_values)) if len(unique_values) > 1 else 1.0
        
        return entropy / max_entropy if max_entropy > 0 else 0.0
    
    def _calculate_weekend_ratio_numpy(self, timestamps: np.ndarray) -> float:
        """Calculate ratio of weekend activity"""
        if len(timestamps) == 0:
            return 0.0
        
        # Convert to weekday (0=Monday, 6=Sunday)
        weekdays = np.array([ts.weekday() for ts in timestamps])
        weekend_events = np.sum((weekdays == 5) | (weekdays == 6))  # Saturday or Sunday
        
        return weekend_events / len(timestamps)
    
    def _calculate_off_hours_ratio_numpy(self, timestamps: np.ndarray) -> float:
        """Calculate ratio of likely off-hours activity (statistical approach for GMT)"""
        if len(timestamps) == 0:
            return 0.0
        
        # Extract GMT hours
        hours = np.array([ts.hour for ts in timestamps])
        
        # Define likely off-hours for major development regions (GMT)
        # 2-10 AM GMT: US night (6PM-2AM PST/9PM-5AM EST), Asia early morning
        # 14-18 PM GMT: Asia night (11PM-3AM JST/JST), US early morning  
        off_hours_mask = ((hours >= 2) & (hours <= 10)) | ((hours >= 14) & (hours <= 18))
        off_hours_count = np.sum(off_hours_mask)
        
        return off_hours_count / len(timestamps)
    
    async def _get_user_baseline_arrays(self, user_login: str) -> Optional[Dict[str, Any]]:
        """Retrieve user's baseline feature statistics as numpy arrays"""
        if not self.redis_client:
            return None
        
        try:
            baseline_key = f"user_baseline_numpy:{user_login}"
            baseline_data = await self.redis_client.get(baseline_key)
            
            if baseline_data:
                data = json.loads(baseline_data)
                # Convert lists back to numpy arrays
                data['mean_features'] = np.array(data['mean_features'])
                data['std_features'] = np.array(data['std_features'])
                if 'feature_history' in data:
                    data['feature_history'] = np.array(data['feature_history'])
                return data
        except Exception as e:
            logger.warning(f"Failed to retrieve numpy baseline for {user_login}: {e}")
        
        return None
    
    async def _update_user_baseline_arrays(
        self, 
        user_login: str, 
        current_features: np.ndarray, 
        existing_baseline: Dict[str, Any]
    ):
        """Update user baseline using EWMA on numpy arrays"""
        if not self.redis_client:
            return
        
        try:
            # Update EWMA mean
            old_mean = existing_baseline['mean_features']
            new_mean = self.alpha * current_features + (1 - self.alpha) * old_mean
            
            # Update EWMA variance (for standard deviation)
            old_var = existing_baseline['std_features'] ** 2
            current_var = (current_features - new_mean) ** 2
            new_var = self.alpha * current_var + (1 - self.alpha) * old_var
            new_std = np.sqrt(new_var)
            
            # Update baseline data
            updated_baseline = {
                'mean_features': new_mean.tolist(),  # Convert to list for JSON
                'std_features': new_std.tolist(),
                'sample_count': existing_baseline['sample_count'] + 1,
                'last_updated': datetime.utcnow().isoformat(),
                'feature_names': self.feature_names
            }
            
            # Keep sliding window of recent features for ML training
            max_history = 100
            if 'feature_history' in existing_baseline:
                history = existing_baseline['feature_history']
                # Add new features and maintain sliding window
                updated_history = np.vstack([history, current_features.reshape(1, -1)])
                if len(updated_history) > max_history:
                    updated_history = updated_history[-max_history:]
                updated_baseline['feature_history'] = updated_history.tolist()
            else:
                updated_baseline['feature_history'] = [current_features.tolist()]
            
            # Store updated baseline
            baseline_key = f"user_baseline_numpy:{user_login}"
            await self.redis_client.setex(
                baseline_key, 
                30 * 24 * 3600,  # 30 days TTL
                json.dumps(updated_baseline, default=str)
            )
            
        except Exception as e:
            logger.error(f"Failed to update numpy baseline for {user_login}: {e}")
    
    def _detect_anomalies_numpy(
        self, 
        current_features: np.ndarray, 
        baseline_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Detect anomalies using numpy statistical methods"""
        anomalies = []
        
        baseline_mean = baseline_data['mean_features']
        baseline_std = baseline_data['std_features']
        
        # Z-score analysis for each feature
        z_scores = np.abs((current_features - baseline_mean) / (baseline_std + 1e-10))
        anomalous_features = z_scores > self.z_score_threshold
        
        for i, is_anomalous in enumerate(anomalous_features):
            if is_anomalous:
                anomalies.append({
                    'type': 'statistical_deviation',
                    'feature_name': self.feature_names[i],
                    'feature_index': i,
                    'current_value': float(current_features[i]),
                    'baseline_mean': float(baseline_mean[i]),
                    'baseline_std': float(baseline_std[i]),
                    'z_score': float(z_scores[i]),
                    'severity': min(float(z_scores[i]) / 5.0, 1.0)
                })
        
        # Multi-variate anomaly detection using Mahalanobis distance
        if baseline_data['sample_count'] > len(self.feature_names):
            try:
                # Calculate covariance matrix from feature history
                if 'feature_history' in baseline_data:
                    history = np.array(baseline_data['feature_history'])
                    if len(history) > len(self.feature_names):
                        cov_matrix = np.cov(history.T)
                        # Add regularization to ensure invertibility
                        cov_matrix += np.eye(cov_matrix.shape[0]) * 1e-6
                        
                        # Calculate Mahalanobis distance
                        diff = current_features - baseline_mean
                        mahal_dist = np.sqrt(diff.T @ np.linalg.inv(cov_matrix) @ diff)
                        
                        # Chi-square critical value for multivariate anomaly
                        chi2_critical = stats.chi2.ppf(0.95, len(self.feature_names))
                        
                        if mahal_dist > chi2_critical:
                            anomalies.append({
                                'type': 'multivariate_anomaly',
                                'mahalanobis_distance': float(mahal_dist),
                                'chi2_critical': float(chi2_critical),
                                'severity': min(float(mahal_dist) / (2 * chi2_critical), 1.0)
                            })
            except np.linalg.LinAlgError:
                logger.warning("Could not compute Mahalanobis distance due to singular covariance matrix")
        
        return anomalies
    
    def _calculate_behavioral_score_numpy(
        self, 
        anomalies: List[Dict[str, Any]], 
        current_features: np.ndarray
    ) -> float:
        """Calculate behavioral anomaly score using numpy"""
        if not anomalies:
            return 0.0
        
        # Weight different types of anomalies
        weights = {
            'statistical_deviation': 0.6,
            'multivariate_anomaly': 0.4
        }
        
        # Convert anomaly severities to numpy array for efficient computation
        severities = []
        type_weights = []
        
        for anomaly in anomalies:
            severities.append(anomaly['severity'])
            anomaly_type = anomaly['type']
            type_weights.append(weights.get(anomaly_type, 0.3))
        
        severities = np.array(severities)
        type_weights = np.array(type_weights)
        
        # Weighted average of anomaly severities
        if len(severities) > 0:
            weighted_score = np.average(severities, weights=type_weights)
            return min(float(weighted_score), 1.0)
        
        return 0.0
    
    async def analyze_behavioral_anomalies(
        self,
        events: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze behavioral anomalies for a batch of events"""
        if not events:
            return {
                'behavioral_anomaly_score': 0.0,
                'detected_anomalies': [],
                'current_features': [0.0] * len(self.feature_names),
                'feature_names': self.feature_names
            }
        
        # Group events by user
        user_events = {}
        for event in events:
            user_login = event.get('actor', {}).get('login', 'unknown')
            if user_login not in user_events:
                user_events[user_login] = []
            user_events[user_login].append(event)
        
        # Analyze each user's behavior
        all_scores = []
        all_anomalies = []
        all_features = []
        
        for user_login, user_event_list in user_events.items():
            result = await self.analyze_user_behavior(user_login, user_event_list, context_data)
            all_scores.append(result.get('behavioral_anomaly_score', 0.0))
            all_anomalies.extend(result.get('detected_anomalies', []))
            all_features.append(result.get('current_features', [0.0] * len(self.feature_names)))
        
        # Aggregate results (take max score as most suspicious)
        max_score = max(all_scores) if all_scores else 0.0
        avg_features = np.mean(all_features, axis=0).tolist() if all_features else [0.0] * len(self.feature_names)
        
        return {
            'behavioral_anomaly_score': max_score,
            'detected_anomalies': all_anomalies,
            'current_features': avg_features,
            'feature_names': self.feature_names,
            'behavioral_features': avg_features  # For backward compatibility
        }
    
    def _cold_start_analysis_numpy(
        self, 
        current_features: np.ndarray, 
        recent_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Cold start analysis using heuristic thresholds on numpy features"""
        anomalies = []
        
        # Multi-tier thresholds for more variable scoring (Conway Technical enhancement)
        thresholds = {
            'events_per_hour': {
                'low': 2.0,      # Moderate activity -> 0.3-0.5 score
                'medium': 5.0,   # High activity -> 0.5-0.7 score  
                'high': 10.0     # Very high activity -> 0.7-0.9 score
            },
            'activity_burst_score': {
                'low': 0.2,      # Some bursting -> 0.4-0.6 score
                'medium': 0.4,   # Moderate bursting -> 0.6-0.7 score
                'high': 0.7      # Significant bursting -> 0.7-0.9 score
            },
            'event_type_entropy': {
                'high': 0.3,     # Very low diversity (suspicious) -> 0.7-0.9 score
                'medium': 0.2,   # Low diversity -> 0.5-0.7 score
                'low': 0.1       # Minimal diversity -> 0.3-0.5 score
            },
            'off_hours_activity_ratio': {
                'low': 0.4,      # Some off-hours -> 0.3-0.5 score
                'medium': 0.6,   # Moderate off-hours -> 0.5-0.7 score
                'high': 0.8      # Mostly off-hours -> 0.7-0.9 score
            },
            'repository_diversity_ratio': {
                'high': 0.15,    # Very focused -> 0.6-0.8 score
                'medium': 0.1,   # Focused -> 0.4-0.6 score
                'low': 0.05      # Extremely focused -> 0.2-0.4 score
            }
        }
        
        for i, feature_name in enumerate(self.feature_names):
            if feature_name in thresholds:
                current_value = current_features[i]
                feature_thresholds = thresholds[feature_name]
                
                # Multi-tier scoring for variable results
                if feature_name == 'event_type_entropy':
                    # Low entropy is suspicious (inverted logic)
                    if current_value < feature_thresholds['low']:
                        severity = 0.8 + (0.1 * (1.0 - current_value))  # 0.8-0.9 range
                        anomaly_type = 'critical_low_diversity'
                    elif current_value < feature_thresholds['medium']:
                        severity = 0.6 + (0.1 * (feature_thresholds['medium'] - current_value) / feature_thresholds['medium'])  # 0.6-0.7 range
                        anomaly_type = 'moderate_low_diversity'
                    elif current_value < feature_thresholds['high']:
                        severity = 0.4 + (0.1 * (feature_thresholds['high'] - current_value) / feature_thresholds['high'])  # 0.4-0.5 range
                        anomaly_type = 'low_diversity_pattern'
                    else:
                        continue  # Normal diversity, no anomaly
                    
                    anomalies.append({
                        'type': anomaly_type,
                        'feature_name': feature_name,
                        'current_value': float(current_value),
                        'threshold': feature_thresholds,
                        'severity': min(severity, 1.0)
                    })
                
                elif feature_name == 'repository_diversity_ratio':
                    # Low repo diversity is suspicious (inverted logic)
                    if current_value < feature_thresholds['low']:
                        severity = 0.7 + (0.1 * (feature_thresholds['low'] - current_value) / feature_thresholds['low'])  # 0.7-0.8 range
                        anomaly_type = 'extremely_focused_activity'
                    elif current_value < feature_thresholds['medium']:
                        severity = 0.5 + (0.1 * (feature_thresholds['medium'] - current_value) / feature_thresholds['medium'])  # 0.5-0.6 range
                        anomaly_type = 'focused_repository_activity'
                    elif current_value < feature_thresholds['high']:
                        severity = 0.3 + (0.1 * (feature_thresholds['high'] - current_value) / feature_thresholds['high'])  # 0.3-0.4 range
                        anomaly_type = 'concentrated_activity'
                    else:
                        continue  # Normal distribution, no anomaly
                    
                    anomalies.append({
                        'type': anomaly_type,
                        'feature_name': feature_name,
                        'current_value': float(current_value),
                        'threshold': feature_thresholds,
                        'severity': min(severity, 1.0)
                    })
                
                else:
                    # High values are suspicious (normal logic)
                    if current_value > feature_thresholds['high']:
                        severity = 0.7 + (0.2 * min(current_value / feature_thresholds['high'] - 1, 1.0))  # 0.7-0.9 range
                        anomaly_type = f'high_{feature_name}'
                    elif current_value > feature_thresholds['medium']:
                        severity = 0.5 + (0.2 * (current_value - feature_thresholds['medium']) / (feature_thresholds['high'] - feature_thresholds['medium']))  # 0.5-0.7 range
                        anomaly_type = f'moderate_{feature_name}'
                    elif current_value > feature_thresholds['low']:
                        severity = 0.3 + (0.2 * (current_value - feature_thresholds['low']) / (feature_thresholds['medium'] - feature_thresholds['low']))  # 0.3-0.5 range
                        anomaly_type = f'elevated_{feature_name}'
                    else:
                        continue  # Below threshold, no anomaly
                    
                    anomalies.append({
                        'type': anomaly_type,
                        'feature_name': feature_name,
                        'current_value': float(current_value),
                        'threshold': feature_thresholds,
                        'severity': min(severity, 1.0)
                    })
        
        # Add Conway Technical specific patterns
        force_push_score = self._detect_force_push_patterns(recent_events)
        if force_push_score > 0:
            anomalies.append({
                'type': 'force_push_pattern',
                'feature_name': 'force_push_detection',
                'current_value': force_push_score,
                'threshold': 0.5,
                'severity': force_push_score
            })

        # Calculate simple heuristic score
        behavioral_score = 0.0
        if anomalies:
            severities = np.array([a['severity'] for a in anomalies])
            behavioral_score = np.mean(severities)
        
        return {
            'behavioral_anomaly_score': float(behavioral_score),
            'detected_anomalies': anomalies,
            'current_features': current_features.tolist(),
            'feature_names': self.feature_names,
            'confidence': 0.3,  # Low confidence for cold start
            'analysis_type': 'cold_start_numpy_heuristic'
        }
    
    def _compare_with_baseline_numpy(
        self, 
        current_features: np.ndarray, 
        baseline_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare current features with baseline using numpy"""
        baseline_mean = baseline_data['mean_features']
        baseline_std = baseline_data['std_features']
        
        # Calculate percent changes and z-scores
        percent_changes = ((current_features - baseline_mean) / (baseline_mean + 1e-10)) * 100
        z_scores = (current_features - baseline_mean) / (baseline_std + 1e-10)
        
        comparison = {}
        for i, feature_name in enumerate(self.feature_names):
            comparison[feature_name] = {
                'current': float(current_features[i]),
                'baseline_mean': float(baseline_mean[i]),
                'baseline_std': float(baseline_std[i]),
                'percent_change': float(percent_changes[i]),
                'z_score': float(z_scores[i]),
                'direction': 'increase' if percent_changes[i] > 5 else 'decrease' if percent_changes[i] < -5 else 'stable'
            }
        
        return comparison
    
    def _detect_force_push_patterns(self, events: List[Dict[str, Any]]) -> float:
        """Detect force push patterns - Conway Technical specific"""
        force_push_score = 0.0
        
        for event in events:
            event_type = event.get('type', '')
            payload = event.get('payload', {})
            
            # Check for force push indicators
            if event_type == 'PushEvent':
                # Check for force push in payload
                forced = payload.get('forced', False)
                if forced:
                    force_push_score = max(force_push_score, 0.9)
                
                # Check commit messages for force push indicators
                commits = payload.get('commits', [])
                for commit in commits:
                    message = commit.get('message', '').lower()
                    if any(indicator in message for indicator in ['force push', 'rewrite', 'amend', '--force']):
                        force_push_score = max(force_push_score, 0.7)
                
                # Check for single commit with many changes (typical of force push)
                if len(commits) == 1 and commits[0].get('distinct', False):
                    # This could indicate a rewritten history
                    force_push_score = max(force_push_score, 0.6)
        
        return force_push_score
