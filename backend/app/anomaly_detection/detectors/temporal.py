from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
import logging
from collections import defaultdict
from scipy import stats
import json
import aiohttp
import asyncio

logger = logging.getLogger(__name__)

class TemporalAnomalyDetector:
    """Temporal anomaly detection using burst analysis and time-series methods with numpy"""
    
    def __init__(self, redis_client=None, github_token: Optional[str] = None):
        self.redis_client = redis_client
        self.github_token = github_token
        
        # Time window configurations
        self.burst_window_minutes = 5      # Window for burst detection
        self.coordination_window_minutes = 15  # Window for coordinated activity
        self.baseline_hours = 24           # Hours of baseline data needed
        
        # Thresholds for anomaly detection
        self.burst_threshold_events = 5    # Events in burst window
        self.burst_threshold_rate = 2.0    # Events per minute
        self.coordination_threshold_actors = 3  # Actors for coordination
        self.unusual_timing_z_threshold = 2.0   # Z-score for timing anomalies
        
        # GitHub API configurations
        self.max_baseline_events = 300     # Max events to fetch for baseline
        self.baseline_cache_ttl = 3600     # 1 hour cache for baseline data
        
        # Temporal feature vector for ML integration
        self.temporal_feature_names = [
            'events_per_minute_current',
            'events_per_minute_baseline_ratio',
            'burst_intensity_score',
            'inter_event_regularity_score',
            'coordination_score',
            'off_hours_intensity_ratio',
            'weekend_activity_ratio',
            'time_concentration_score',
            'velocity_acceleration'
        ]
        
        # Time buckets for analysis (GMT hours)
        self.time_buckets = {
            'deep_night': list(range(0, 6)),     # 00:00-05:59 GMT
            'morning': list(range(6, 12)),       # 06:00-11:59 GMT  
            'afternoon': list(range(12, 18)),    # 12:00-17:59 GMT
            'evening': list(range(18, 24))       # 18:00-23:59 GMT
        }
    
    async def analyze_temporal_anomalies(
        self,
        events: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze temporal anomalies in event stream"""
        
        if not events:
            return {
                'temporal_anomaly_score': 0.0,
                'temporal_features': np.zeros(len(self.temporal_feature_names)).tolist(),
                'detected_patterns': [],
                'analysis_type': 'insufficient_data'
            }
        
        # Extract timestamps and convert to numpy arrays
        timestamps, event_data = self._extract_temporal_data(events)
        
        if len(timestamps) < 2:
            return {
                'temporal_anomaly_score': 0.0,
                'temporal_features': np.zeros(len(self.temporal_feature_names)).tolist(),
                'detected_patterns': [],
                'analysis_type': 'insufficient_timestamps'
            }
        
        # Extract temporal features (including baseline comparison)
        temporal_features = await self._extract_temporal_features(timestamps, event_data, events)
        
        # Detect temporal patterns
        detected_patterns = self._detect_temporal_patterns(timestamps, event_data)
        
        # Calculate overall temporal anomaly score
        temporal_score = self._calculate_temporal_score(temporal_features, detected_patterns)
        
        return {
            'temporal_anomaly_score': float(temporal_score),
            'temporal_features': temporal_features.tolist(),
            'feature_names': self.temporal_feature_names,
            'detected_patterns': detected_patterns,
            'analysis_type': 'full_temporal_analysis'
        }
    
    def _extract_temporal_data(self, events: List[Dict[str, Any]]) -> Tuple[np.ndarray, Dict[str, np.ndarray]]:
        """Extract temporal data from events as numpy arrays"""
        timestamps = []
        actors = []
        repos = []
        event_types = []
        
        for event in events:
            timestamp_str = event.get('created_at')
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    timestamps.append(dt)
                    actors.append(event.get('actor_login', 'unknown'))
                    repos.append(event.get('repo_name', 'unknown'))
                    event_types.append(event.get('type', 'unknown'))
                except (ValueError, AttributeError):
                    continue
        
        if not timestamps:
            return np.array([]), {}
        
        # Convert to numpy arrays and sort by time
        timestamps = np.array(timestamps)
        sort_indices = np.argsort(timestamps)
        
        event_data = {
            'actors': np.array(actors)[sort_indices],
            'repos': np.array(repos)[sort_indices], 
            'types': np.array(event_types)[sort_indices]
        }
        
        return timestamps[sort_indices], event_data
    
    async def _extract_temporal_features(
        self, 
        timestamps: np.ndarray, 
        event_data: Dict[str, np.ndarray],
        original_events: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Extract temporal features as numpy array"""
        features = np.zeros(len(self.temporal_feature_names))
        
        if len(timestamps) < 2:
            return features
        
        # Calculate time spans and intervals
        time_span_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
        time_span_minutes = max(time_span_seconds / 60, 1.0)
        
        # Inter-event intervals in minutes
        intervals = np.diff(timestamps.astype('datetime64[s]')).astype(float) / 60
        
        # Feature 0: Current events per minute
        current_rate = len(timestamps) / time_span_minutes
        features[0] = current_rate
        
        # Feature 1: Events per minute ratio vs baseline (using GitHub API data)
        baseline_rate = await self._get_baseline_event_rate(original_events)
        if baseline_rate > 0:
            features[1] = current_rate / baseline_rate
        else:
            features[1] = 1.0  # No baseline available
        
        # Feature 2: Burst intensity score
        features[2] = self._calculate_burst_intensity(timestamps, intervals)
        
        # Feature 3: Inter-event regularity score (lower = more regular)
        if len(intervals) > 1:
            features[3] = np.std(intervals) / (np.mean(intervals) + 1e-10)
        
        # Feature 4: Coordination score (multiple actors acting together)
        features[4] = self._calculate_coordination_score(timestamps, event_data['actors'])
        
        # Feature 5: Off-hours intensity ratio
        features[5] = self._calculate_off_hours_ratio(timestamps)
        
        # Feature 6: Weekend activity ratio  
        features[6] = self._calculate_weekend_ratio(timestamps)
        
        # Feature 7: Time concentration score (how concentrated in time)
        features[7] = self._calculate_time_concentration(timestamps)
        
        # Feature 8: Velocity acceleration (increasing event rate)
        features[8] = self._calculate_velocity_acceleration(timestamps)
        
        return features
    
    async def _get_baseline_event_rate(self, current_events: List[Dict[str, Any]]) -> float:
        """Get baseline event rate from GitHub API data"""
        if not self.github_token or not current_events:
            return 0.5  # Default fallback
        
        # Get unique users and repos from current events
        users = set()
        repos = set()
        
        for event in current_events:
            actor = event.get('actor_login')
            repo = event.get('repo_name')
            if actor:
                users.add(actor)
            if repo:
                repos.add(repo)
        
        # Fetch baseline data for users and repos
        user_baselines = await self._fetch_user_baselines(list(users)[:5])  # Limit to 5 users
        repo_baselines = await self._fetch_repo_baselines(list(repos)[:3])  # Limit to 3 repos
        
        # Calculate combined baseline rate
        all_rates = []
        
        for user_data in user_baselines:
            if user_data:
                all_rates.append(user_data['events_per_minute'])
        
        for repo_data in repo_baselines:
            if repo_data:
                all_rates.append(repo_data['events_per_minute'])
        
        if all_rates:
            # Use median as baseline to reduce impact of outliers
            return float(np.median(all_rates))
        
        return 0.5  # Default if no baseline data available
    
    async def _fetch_user_baselines(self, users: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Fetch baseline activity for users from GitHub API"""
        baselines = []
        
        for user in users:
            baseline = await self._get_cached_user_baseline(user)
            if baseline is None:
                baseline = await self._fetch_user_events_from_api(user)
                if baseline:
                    await self._cache_user_baseline(user, baseline)
            
            baselines.append(baseline)
        
        return baselines
    
    async def _fetch_repo_baselines(self, repos: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Fetch baseline activity for repositories from GitHub API"""
        baselines = []
        
        for repo in repos:
            baseline = await self._get_cached_repo_baseline(repo)
            if baseline is None:
                baseline = await self._fetch_repo_events_from_api(repo)
                if baseline:
                    await self._cache_repo_baseline(repo, baseline)
            
            baselines.append(baseline)
        
        return baselines
    
    async def _fetch_user_events_from_api(self, username: str) -> Optional[Dict[str, Any]]:
        """Fetch user's public events from GitHub API"""
        url = f"https://api.github.com/users/{username}/events/public"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Anomaly-Detector'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        events = await response.json()
                        return self._analyze_baseline_events(events, f"user:{username}")
                    elif response.status == 403:
                        logger.warning(f"Rate limited while fetching user events for {username}")
                    elif response.status == 404:
                        logger.info(f"User {username} not found or has no public events")
                    else:
                        logger.warning(f"Failed to fetch user events for {username}: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching user events for {username}: {e}")
        
        return None
    
    async def _fetch_repo_events_from_api(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Fetch repository events from GitHub API"""
        url = f"https://api.github.com/repos/{repo_name}/events"
        headers = {
            'Authorization': f'token {self.github_token}',
            'Accept': 'application/vnd.github.v3+json',
            'User-Agent': 'GitHub-Anomaly-Detector'
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers) as response:
                    if response.status == 200:
                        events = await response.json()
                        return self._analyze_baseline_events(events, f"repo:{repo_name}")
                    elif response.status == 403:
                        logger.warning(f"Rate limited while fetching repo events for {repo_name}")
                    elif response.status == 404:
                        logger.info(f"Repository {repo_name} not found or private")
                    else:
                        logger.warning(f"Failed to fetch repo events for {repo_name}: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching repo events for {repo_name}: {e}")
        
        return None
    
    def _analyze_baseline_events(self, events: List[Dict[str, Any]], source: str) -> Dict[str, Any]:
        """Analyze baseline events to extract temporal patterns"""
        if not events:
            return {
                'source': source,
                'events_per_minute': 0.0,
                'total_events': 0,
                'time_span_hours': 0,
                'hourly_distribution': np.zeros(24).tolist(),
                'created_at': datetime.utcnow().isoformat()
            }
        
        # Extract timestamps
        timestamps = []
        for event in events:
            created_at = event.get('created_at')
            if created_at:
                try:
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    timestamps.append(dt)
                except (ValueError, AttributeError):
                    continue
        
        if len(timestamps) < 2:
            return {
                'source': source,
                'events_per_minute': 0.0,
                'total_events': len(events),
                'time_span_hours': 0,
                'hourly_distribution': np.zeros(24).tolist(),
                'created_at': datetime.utcnow().isoformat()
            }
        
        timestamps = np.array(sorted(timestamps))
        
        # Calculate baseline metrics
        time_span_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
        time_span_hours = max(time_span_seconds / 3600, 1.0)
        time_span_minutes = max(time_span_seconds / 60, 1.0)
        
        events_per_minute = len(timestamps) / time_span_minutes
        
        # Hour-of-day distribution
        hours = np.array([ts.hour for ts in timestamps])
        hourly_distribution = np.bincount(hours, minlength=24)
        
        return {
            'source': source,
            'events_per_minute': float(events_per_minute),
            'total_events': len(timestamps),
            'time_span_hours': float(time_span_hours),
            'hourly_distribution': hourly_distribution.tolist(),
            'first_event': timestamps[0].isoformat(),
            'last_event': timestamps[-1].isoformat(),
            'created_at': datetime.utcnow().isoformat()
        }
    
    async def _get_cached_user_baseline(self, username: str) -> Optional[Dict[str, Any]]:
        """Get cached user baseline from Redis"""
        if not self.redis_client:
            return None
        
        try:
            cache_key = f"user_baseline_temporal:{username}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached user baseline for {username}: {e}")
        
        return None
    
    async def _cache_user_baseline(self, username: str, baseline: Dict[str, Any]):
        """Cache user baseline in Redis"""
        if not self.redis_client:
            return
        
        try:
            cache_key = f"user_baseline_temporal:{username}"
            await self.redis_client.setex(
                cache_key,
                self.baseline_cache_ttl,
                json.dumps(baseline, default=str)
            )
        except Exception as e:
            logger.warning(f"Failed to cache user baseline for {username}: {e}")
    
    async def _get_cached_repo_baseline(self, repo_name: str) -> Optional[Dict[str, Any]]:
        """Get cached repository baseline from Redis"""
        if not self.redis_client:
            return None
        
        try:
            # Replace '/' with ':' for Redis key safety
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_baseline_temporal:{safe_repo_name}"
            cached_data = await self.redis_client.get(cache_key)
            if cached_data:
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Failed to get cached repo baseline for {repo_name}: {e}")
        
        return None
    
    async def _cache_repo_baseline(self, repo_name: str, baseline: Dict[str, Any]):
        """Cache repository baseline in Redis"""
        if not self.redis_client:
            return
        
        try:
            # Replace '/' with ':' for Redis key safety
            safe_repo_name = repo_name.replace('/', ':')
            cache_key = f"repo_baseline_temporal:{safe_repo_name}"
            await self.redis_client.setex(
                cache_key,
                self.baseline_cache_ttl,
                json.dumps(baseline, default=str)
            )
        except Exception as e:
            logger.warning(f"Failed to cache repo baseline for {repo_name}: {e}")
    
    def _calculate_burst_intensity(self, timestamps: np.ndarray, intervals: np.ndarray) -> float:
        """Calculate burst intensity using sliding window analysis"""
        if len(timestamps) < 3:
            return 0.0
        
        burst_window = timedelta(minutes=self.burst_window_minutes)
        max_burst_intensity = 0.0
        
        # Sliding window analysis
        for i, start_time in enumerate(timestamps[:-1]):
            window_end = start_time + burst_window
            
            # Count events in window
            events_in_window = np.sum((timestamps >= start_time) & (timestamps <= window_end))
            
            if events_in_window >= self.burst_threshold_events:
                # Calculate burst intensity (events per minute in burst)
                window_minutes = self.burst_window_minutes
                burst_rate = events_in_window / window_minutes
                intensity = min(burst_rate / self.burst_threshold_rate, 2.0)  # Cap at 2.0
                max_burst_intensity = max(max_burst_intensity, intensity)
        
        return min(max_burst_intensity, 1.0)
    
    def _calculate_coordination_score(self, timestamps: np.ndarray, actors: np.ndarray) -> float:
        """Calculate coordination score for multi-actor synchronized activity"""
        if len(np.unique(actors)) < 2:
            return 0.0
        
        coordination_window = timedelta(minutes=self.coordination_window_minutes)
        max_coordination = 0.0
        
        # Analyze coordination in sliding windows
        for i, start_time in enumerate(timestamps[:-1]):
            window_end = start_time + coordination_window
            window_mask = (timestamps >= start_time) & (timestamps <= window_end)
            
            if np.sum(window_mask) < 3:  # Need at least 3 events
                continue
            
            window_actors = actors[window_mask]
            unique_actors = np.unique(window_actors)
            
            if len(unique_actors) >= self.coordination_threshold_actors:
                # Calculate coordination intensity
                events_count = np.sum(window_mask)
                actor_count = len(unique_actors)
                
                # Coordination score: more actors + more events in short time = higher score
                coordination = min((actor_count / 10) * (events_count / 20), 1.0)
                max_coordination = max(max_coordination, coordination)
        
        return max_coordination
    
    def _calculate_off_hours_ratio(self, timestamps: np.ndarray) -> float:
        """Calculate ratio of activity during likely off-hours (statistical approach)"""
        if len(timestamps) == 0:
            return 0.0
        
        # Extract GMT hours
        hours = np.array([ts.hour for ts in timestamps])
        
        # Define likely off-hours for major development regions (GMT)
        # Based on statistical analysis of when most developers are likely sleeping
        off_hours_mask = ((hours >= 2) & (hours <= 8)) | ((hours >= 14) & (hours <= 16))
        off_hours_count = np.sum(off_hours_mask)
        
        # Calculate baseline off-hours ratio (should be ~6/24 = 0.25 for random activity)
        baseline_off_hours_ratio = 0.25
        actual_ratio = off_hours_count / len(timestamps)
        
        # Return how much higher than baseline (0 = normal, 1 = all off-hours)
        return min(actual_ratio / baseline_off_hours_ratio, 2.0) - 1.0 if actual_ratio > baseline_off_hours_ratio else 0.0
    
    def _calculate_weekend_ratio(self, timestamps: np.ndarray) -> float:
        """Calculate weekend activity ratio"""
        if len(timestamps) == 0:
            return 0.0
        
        # Get weekdays (0=Monday, 6=Sunday)
        weekdays = np.array([ts.weekday() for ts in timestamps])
        weekend_events = np.sum((weekdays == 5) | (weekdays == 6))  # Saturday or Sunday
        
        # Expected weekend ratio for normal activity (~2/7 = 0.286)
        baseline_weekend_ratio = 2/7
        actual_ratio = weekend_events / len(timestamps)
        
        # Return deviation from baseline
        return max(actual_ratio - baseline_weekend_ratio, 0.0) / baseline_weekend_ratio
    
    def _calculate_time_concentration(self, timestamps: np.ndarray) -> float:
        """Calculate how concentrated events are in time (higher = more concentrated)"""
        if len(timestamps) < 3:
            return 0.0
        
        # Calculate coefficient of variation for inter-event intervals
        intervals = np.diff(timestamps.astype('datetime64[s]')).astype(float)
        
        if len(intervals) < 2:
            return 0.0
        
        mean_interval = np.mean(intervals)
        std_interval = np.std(intervals)
        
        if mean_interval == 0:
            return 1.0  # Perfect concentration
        
        # Coefficient of variation (lower = more concentrated/regular)
        cv = std_interval / mean_interval
        
        # Convert to concentration score (higher = more concentrated)
        concentration = 1.0 / (1.0 + cv)  # Sigmoid-like transformation
        
        return concentration
    
    def _calculate_velocity_acceleration(self, timestamps: np.ndarray) -> float:
        """Calculate if event rate is accelerating over time"""
        if len(timestamps) < 6:  # Need enough points for trend analysis
            return 0.0
        
        # Split timeline into quarters and calculate rates
        n = len(timestamps)
        quarter_size = n // 4
        
        if quarter_size < 2:
            return 0.0
        
        quarters = [
            timestamps[:quarter_size],
            timestamps[quarter_size:2*quarter_size],
            timestamps[2*quarter_size:3*quarter_size],
            timestamps[3*quarter_size:]
        ]
        
        rates = []
        for quarter in quarters:
            if len(quarter) >= 2:
                time_span = (quarter[-1] - quarter[0]).total_seconds() / 60
                rate = len(quarter) / max(time_span, 1.0)
                rates.append(rate)
        
        if len(rates) < 3:
            return 0.0
        
        # Calculate trend using linear regression
        x = np.arange(len(rates))
        y = np.array(rates) 
        
        if np.std(y) == 0:  # No variation
            return 0.0
        
        # Linear regression slope
        slope, _, r_value, _, _ = stats.linregress(x, y)
        
        # Normalize slope by mean rate to get relative acceleration
        mean_rate = np.mean(rates)
        if mean_rate > 0:
            acceleration = (slope / mean_rate) * abs(r_value)  # Weight by correlation
            return min(max(acceleration, 0.0), 1.0)  # Clamp to [0, 1]
        
        return 0.0
    
    def _detect_temporal_patterns(
        self, 
        timestamps: np.ndarray, 
        event_data: Dict[str, np.ndarray]
    ) -> List[Dict[str, Any]]:
        """Detect specific temporal patterns"""
        patterns = []
        
        if len(timestamps) < 2:
            return patterns
        
        # Pattern 1: Activity bursts
        burst_pattern = self._detect_burst_pattern(timestamps)
        if burst_pattern:
            patterns.append(burst_pattern)
        
        # Pattern 2: Coordinated multi-actor activity
        coordination_pattern = self._detect_coordination_pattern(timestamps, event_data['actors'])
        if coordination_pattern:
            patterns.append(coordination_pattern)
        
        # Pattern 3: Unusual timing patterns
        timing_pattern = self._detect_unusual_timing_pattern(timestamps)
        if timing_pattern:
            patterns.append(timing_pattern)
        
        # Pattern 4: Sustained high activity
        sustained_pattern = self._detect_sustained_activity_pattern(timestamps)
        if sustained_pattern:
            patterns.append(sustained_pattern)
        
        return patterns
    
    def _detect_burst_pattern(self, timestamps: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect burst activity patterns"""
        burst_window = timedelta(minutes=self.burst_window_minutes)
        
        for i, start_time in enumerate(timestamps[:-1]):
            window_end = start_time + burst_window
            events_in_window = np.sum((timestamps >= start_time) & (timestamps <= window_end))
            
            if events_in_window >= self.burst_threshold_events:
                rate = events_in_window / self.burst_window_minutes
                return {
                    'type': 'activity_burst',
                    'start_time': start_time.isoformat(),
                    'duration_minutes': self.burst_window_minutes,
                    'event_count': int(events_in_window),
                    'events_per_minute': float(rate),
                    'severity': min(rate / self.burst_threshold_rate, 1.0)
                }
        
        return None
    
    def _detect_coordination_pattern(
        self, 
        timestamps: np.ndarray, 
        actors: np.ndarray
    ) -> Optional[Dict[str, Any]]:
        """Detect coordinated multi-actor activity"""
        coordination_window = timedelta(minutes=self.coordination_window_minutes)
        
        for i, start_time in enumerate(timestamps[:-1]):
            window_end = start_time + coordination_window
            window_mask = (timestamps >= start_time) & (timestamps <= window_end)
            
            if np.sum(window_mask) < 3:
                continue
            
            window_actors = actors[window_mask]
            unique_actors = np.unique(window_actors)
            
            if len(unique_actors) >= self.coordination_threshold_actors:
                return {
                    'type': 'coordinated_activity',
                    'start_time': start_time.isoformat(),
                    'duration_minutes': self.coordination_window_minutes,
                    'actor_count': len(unique_actors),
                    'event_count': int(np.sum(window_mask)),
                    'actors': unique_actors.tolist()[:10],  # Limit for display
                    'severity': min(len(unique_actors) / 10, 1.0)
                }
        
        return None
    
    def _detect_unusual_timing_pattern(self, timestamps: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect unusual timing patterns using statistical analysis"""
        if len(timestamps) < 10:  # Need enough data for statistical analysis
            return None
        
        # Analyze hour-of-day distribution
        hours = np.array([ts.hour for ts in timestamps])
        hour_counts = np.bincount(hours, minlength=24)
        
        # Expected uniform distribution
        expected_per_hour = len(timestamps) / 24
        
        # Chi-square test for uniform distribution
        chi2_stat, p_value = stats.chisquare(hour_counts, expected_per_hour)
        
        # If significantly non-uniform (p < 0.05), it's unusual
        if p_value < 0.05:
            peak_hour = np.argmax(hour_counts)
            peak_count = hour_counts[peak_hour]
            
            return {
                'type': 'unusual_timing_distribution',
                'chi2_statistic': float(chi2_stat),
                'p_value': float(p_value),
                'peak_hour_gmt': int(peak_hour),
                'peak_hour_count': int(peak_count),
                'expected_count': float(expected_per_hour),
                'severity': min(1.0 - p_value, 1.0)  # Lower p-value = higher severity
            }
        
        return None
    
    def _detect_sustained_activity_pattern(self, timestamps: np.ndarray) -> Optional[Dict[str, Any]]:
        """Detect sustained high activity over longer periods"""
        if len(timestamps) < 20:  # Need substantial activity
            return None
        
        # Check for sustained activity over 1-hour windows
        sustained_window = timedelta(hours=1)
        high_activity_threshold = 30  # events per hour
        
        for i, start_time in enumerate(timestamps[:-10]):
            window_end = start_time + sustained_window
            events_in_window = np.sum((timestamps >= start_time) & (timestamps <= window_end))
            
            if events_in_window >= high_activity_threshold:
                return {
                    'type': 'sustained_high_activity',
                    'start_time': start_time.isoformat(),
                    'duration_hours': 1,
                    'event_count': int(events_in_window),
                    'events_per_hour': float(events_in_window),
                    'severity': min(events_in_window / (high_activity_threshold * 2), 1.0)
                }
        
        return None
    
    def _calculate_temporal_score(
        self, 
        temporal_features: np.ndarray, 
        detected_patterns: List[Dict[str, Any]]
    ) -> float:
        """Calculate overall temporal anomaly score"""
        
        # Feature-based score with weights
        feature_weights = np.array([
            0.20,  # events_per_minute_current
            0.25,  # events_per_minute_baseline_ratio  
            0.30,  # burst_intensity_score
            0.10,  # inter_event_regularity_score
            0.25,  # coordination_score
            0.15,  # off_hours_intensity_ratio
            0.10,  # weekend_activity_ratio
            0.15,  # time_concentration_score
            0.20   # velocity_acceleration
        ])
        
        # Normalize features using sigmoid
        sigmoid_features = 1 / (1 + np.exp(-temporal_features * 2))  # Sigmoid with scaling
        
        # Weighted feature score
        feature_score = np.dot(sigmoid_features, feature_weights)
        
        # Pattern-based boost
        pattern_boost = 0.0
        if detected_patterns:
            pattern_severities = [p.get('severity', 0.5) for p in detected_patterns]
            pattern_boost = min(np.mean(pattern_severities) * 0.3, 0.4)
        
        # Final score
        final_score = min(feature_score + pattern_boost, 1.0)
        
        return final_score