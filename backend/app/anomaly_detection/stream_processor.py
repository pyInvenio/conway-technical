from typing import Dict, Any, List, Optional, Tuple
import asyncio
import logging
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict
import json

from .models.anomaly_score import AnomalyScore, SeverityLevel
from .scoring.severity_engine import SeverityEngine
from .detectors.behavioral import BehavioralAnomalyDetector
from .detectors.content import ContentAnomalyDetector
from .detectors.temporal import TemporalAnomalyDetector
from .detectors.contextual import RepositoryContextScorer
from .profiles.user_profile import UserProfileManager
from .profiles.repo_profile import RepositoryProfileManager
from .optimization.ai_summarizer import TieredAISummarizer
from .optimization.context_filter import SmartContextFilter

logger = logging.getLogger(__name__)

class AnomalyStreamProcessor:
    """Enhanced stream processor for real-time anomaly detection with multi-factor scoring"""
    
    def __init__(
        self,
        redis_client=None,
        websocket_manager=None,
        github_token: Optional[str] = None,
        openai_api_key: Optional[str] = None
    ):
        self.redis_client = redis_client
        self.websocket_manager = websocket_manager
        
        # Initialize all detection components
        self.severity_engine = SeverityEngine()
        self.behavioral_detector = BehavioralAnomalyDetector(redis_client)
        self.content_detector = ContentAnomalyDetector(github_token)
        self.temporal_detector = TemporalAnomalyDetector(redis_client, github_token)
        self.context_scorer = RepositoryContextScorer(redis_client, github_token)
        
        # Initialize profiling managers
        self.user_profile_manager = UserProfileManager(redis_client)
        self.repo_profile_manager = RepositoryProfileManager(redis_client)
        
        # Initialize optimization components
        self.ai_summarizer = TieredAISummarizer(redis_client)
        self.context_filter = SmartContextFilter()
        
        # Processing configuration
        self.batch_size = 50  # Process events in batches
        self.max_processing_time = 2.0  # Maximum 2 seconds per batch
        
        # Detection weights (can be made configurable)
        self.detection_weights = {
            'behavioral': 0.30,
            'content': 0.35,
            'temporal': 0.25,
            'repository': 0.10
        }
        
        # Performance metrics
        self.processing_stats = {
            'events_processed': 0,
            'anomalies_detected': 0,
            'avg_processing_time': 0.0,
            'last_reset': datetime.utcnow()
        }
    
    async def process_event_stream(
        self, 
        events: List[Dict[str, Any]], 
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Process a stream of events and detect anomalies"""
        
        start_time = datetime.utcnow()
        processed_results = []
        print(f"Processing {len(events)} events...")
        
        try:
            # Group events for efficient processing
            event_groups = self._group_events_for_processing(events)
            # print(f"Grouped into {event_groups} groups for processing")
            
            # Process all groups in parallel
            group_tasks = []
            for group_name, group_events in event_groups.items():
                if group_events:
                    group_tasks.append(self._process_event_group(group_events, context_data))
            # print(f"Created {len(group_tasks)} group processing tasks")
            
            # Execute all group processing in parallel
            if group_tasks:
                group_results = await asyncio.gather(*group_tasks, return_exceptions=True)
                # print(group_results)
                # Flatten results and handle exceptions
                for result in group_results:
                    # print(f"Processing group result: {result}")
                    if isinstance(result, Exception):
                        logger.error(f"Group processing failed: {result}")
                    elif isinstance(result, list):
                        processed_results.extend(result)
                        # print(f"Extended processed results with {len(result)} items")
            
            # Update processing statistics
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            await self._update_processing_stats(len(events), processing_time)
            # print(processed_results)
            logger.info(f"Processed {len(events)} events in {processing_time:.2f}s")
            
            return processed_results
            
        except Exception as e:
            logger.error(f"Error processing event stream: {e}")
            return []
    
    async def _process_event_group(
        self, 
        events: List[Dict[str, Any]], 
        context_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Process a group of related events"""
        
        group_results = []
        
        # Extract common information
        user_logins = list(set(e.get('actor', {}).get('login') for e in events if e.get('actor', {}).get('login')))
        repo_names = list(set(e.get('repo', {}).get('name') for e in events if e.get('repo', {}).get('name')))
        
        # Run all detections in parallel
        detection_tasks = [
            self.behavioral_detector.analyze_behavioral_anomalies(events, context_data),
            self.content_detector.analyze_content_anomalies(events, context_data),
            self.temporal_detector.analyze_temporal_anomalies(events, context_data),
            self._analyze_repository_contexts(repo_names, events)
        ]
        
        detection_results = await asyncio.gather(*detection_tasks, return_exceptions=True)
        # print(f"Detection results: {detection_results}")
        # Handle any exceptions in detection results
        behavioral_result, content_result, temporal_result, repo_contexts = self._handle_detection_results(detection_results)
        
        # Update profiles in background (fire and forget)
        asyncio.create_task(self._update_profiles_background(user_logins, repo_names, events, context_data))
        
        # Process each event with the detection results in parallel
        event_tasks = []
        for event in events:
            event_tasks.append(self._process_single_event(
                event, behavioral_result, content_result, temporal_result, repo_contexts
            ))
        
        # print(f"Created {len(event_tasks)} event processing tasks")
        
        # Execute all event processing in parallel
        if event_tasks:
            event_results = await asyncio.gather(*event_tasks, return_exceptions=True)
            
            for result in event_results:
                if isinstance(result, Exception):
                    logger.error(f"Event processing failed: {result}")
                else:
                    group_results.append(result)
        # print(f"Processed {len(group_results)} events in group")
        
        return group_results
    
    async def _update_profiles_background(
        self,
        user_logins: List[str],
        repo_names: List[str],
        events: List[Dict[str, Any]],
        context_data: Optional[Dict[str, Any]] = None
    ):
        """Update user and repository profiles in background"""
        try:
            profile_tasks = []
            
            # Update user profiles
            for user_login in user_logins:
                user_events = [e for e in events if e.get('actor', {}).get('login') == user_login]
                if user_events:
                    # Extract behavioral features for this user
                    try:
                        behavioral_result = await self.behavioral_detector.analyze_user_behavior(user_login, user_events, context_data)
                        if behavioral_result.get('current_features') is not None:
                            features = np.array(behavioral_result['current_features'])
                            profile_tasks.append(
                                self.user_profile_manager.update_user_profile(user_login, features, user_events)
                            )
                    except Exception as e:
                        logger.warning(f"Failed to update profile for user {user_login}: {e}")
            
            # Update repository profiles
            for repo_name in repo_names:
                repo_events = [e for e in events if e.get('repo', {}).get('name') == repo_name]
                if repo_events:
                    profile_tasks.append(
                        self.repo_profile_manager.update_repo_profile(repo_name, repo_events, context_data)
                    )
            
            # Execute all profile updates in parallel
            if profile_tasks:
                await asyncio.gather(*profile_tasks, return_exceptions=True)
            
        except Exception as e:
            logger.error(f"Background profile update failed: {e}")
    
    async def _process_single_event(
        self,
        event: Dict[str, Any],
        behavioral_result: Dict[str, Any],
        content_result: Dict[str, Any],
        temporal_result: Dict[str, Any],
        repo_contexts: Dict[str, Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Process a single event with all detection results"""
        print("Processing single event:", event.get('id', 'unknown'))
        event_id = event.get('id', 'unknown')
        user_login = event.get('actor', {}).get('login', 'unknown')
        repo_name = event.get('repo', {}).get('name', 'unknown')
        
        # Get repository context for this event
        repo_context = repo_contexts.get(repo_name, {})
        repo_criticality = repo_context.get('repository_criticality_score', 0.5)
        
        # Create anomaly score object
        anomaly_score = AnomalyScore()
        
        # Set detection scores
        anomaly_score.behavioral_anomaly = behavioral_result.get('behavioral_anomaly_score', 0.0)
        anomaly_score.content_risk = content_result.get('content_risk_score', 0.0)
        anomaly_score.temporal_anomaly = temporal_result.get('temporal_anomaly_score', 0.0)
        anomaly_score.repository_criticality = repo_criticality
        
        # Calculate final score using severity engine
        severity_result = self.severity_engine.calculate_severity(
            behavioral_score=anomaly_score.behavioral_anomaly,
            content_score=anomaly_score.content_risk,
            temporal_score=anomaly_score.temporal_anomaly,
            repository_score=anomaly_score.repository_criticality,
            context_data=repo_context,
            incident_type=event.get('type', 'unknown')
        )
        anomaly_score = severity_result
        final_score = severity_result.final_score
        
        # Determine severity level
        severity_level = SeverityLevel.from_score(final_score)
        
        # Generate AI summary in background for high severity events
        ai_summary_task = None
        if severity_level in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
            ai_summary_task = asyncio.create_task(self._generate_ai_summary_background(
                event, behavioral_result, content_result, temporal_result, repo_context, severity_level.name
            ))
        
        # Create comprehensive result
        result = {
            'event_id': event_id,
            'timestamp': datetime.utcnow().isoformat(),
            'user_login': user_login,
            'repository_name': repo_name,
            'event_type': event.get('type'),
            
            # Scores
            'final_anomaly_score': final_score,
            'severity_level': severity_level.name,
            'severity_description': severity_level.level_name,
            
            # Component scores
            'detection_scores': {
                'behavioral': anomaly_score.behavioral_anomaly,
                'content': anomaly_score.content_risk,
                'temporal': anomaly_score.temporal_anomaly,
                'repository_criticality': anomaly_score.repository_criticality
            },
            
            # Detailed analysis
            'behavioral_analysis': behavioral_result,
            'content_analysis': content_result,
            'temporal_analysis': temporal_result,
            'repository_context': repo_context,
            
            # Processing metadata
            'detection_weights': self.detection_weights,
            'processing_timestamp': datetime.utcnow().isoformat()
        }
        
        # Send to WebSocket channels in background
        if self.websocket_manager and severity_level != SeverityLevel.INFO:
            asyncio.create_task(self._send_to_websocket_channels(result, severity_level))
        
        # Wait for AI summary if it was requested
        if ai_summary_task:
            try:
                ai_summary = await ai_summary_task
                result['ai_summary'] = ai_summary
            except Exception as e:
                logger.warning(f"AI summary generation failed: {e}")
                result['ai_summary'] = None
        
        return result
    
    async def _generate_ai_summary_background(
        self,
        event: Dict[str, Any],
        behavioral_result: Dict[str, Any],
        content_result: Dict[str, Any],
        temporal_result: Dict[str, Any],
        repo_context: Dict[str, Any],
        severity_level: str
    ) -> Optional[str]:
        """Generate AI summary in background"""
        try:
            # Filter context to reduce token usage
            filtered_context = self.context_filter.filter_and_compress(
                {
                    'event': event,
                    'behavioral_result': behavioral_result,
                    'content_result': content_result,
                    'temporal_result': temporal_result,
                    'repo_context': repo_context
                },
                incident_type='anomaly',  # Use generic type for anomalies
                compression_level='medium'
            )
            
            # Create a temporary anomaly score for AI summarizer
            temp_score = AnomalyScore()
            temp_score.severity_level = SeverityLevel[severity_level.upper()]
            temp_score.incident_type = event.get('type', 'anomaly')
            
            return await self.ai_summarizer.generate_summary(
                [event],  # Pass event as list
                temp_score,
                filtered_context
            )
        except Exception as e:
            logger.error(f"AI summary generation failed: {e}")
            return None
    
    async def _analyze_repository_contexts(
        self, 
        repo_names: List[str], 
        events: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """Analyze repository contexts for all repositories in parallel"""
        
        # Create tasks for each repository
        repo_tasks = []
        for repo_name in repo_names:
            repo_events = [e for e in events if e.get('repo_name') == repo_name]
            repo_tasks.append(self._analyze_single_repo_context(repo_name, repo_events))
        
        # Execute all repository analyses in parallel
        if repo_tasks:
            repo_results = await asyncio.gather(*repo_tasks, return_exceptions=True)
            
            repo_contexts = {}
            for i, result in enumerate(repo_results):
                repo_name = repo_names[i]
                if isinstance(result, Exception):
                    logger.warning(f"Failed to analyze context for repo {repo_name}: {result}")
                    repo_contexts[repo_name] = {
                        'repository_criticality_score': 0.5,
                        'analysis_type': 'fallback_scoring',
                        'error': str(result)
                    }
                else:
                    repo_contexts[repo_name] = result
            
            return repo_contexts
        
        return {}
    
    async def _analyze_single_repo_context(
        self, 
        repo_name: str, 
        repo_events: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze context for a single repository"""
        try:
            return await self.context_scorer.analyze_repository_context(repo_name, repo_events)
        except Exception as e:
            logger.warning(f"Repository context analysis failed for {repo_name}: {e}")
            return {
                'repository_criticality_score': 0.5,
                'analysis_type': 'fallback_scoring',
                'error': str(e)
            }
    
    def _group_events_for_processing(self, events: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Group events for efficient batch processing"""
        groups = defaultdict(list)
        
        for event in events:
            # Group by user and repository for better analysis
            user = event.get('actor', {}).get('login', 'unknown')
            repo = event.get('repo', {}).get('name', 'unknown')
            group_key = f"{user}:{repo}"
            groups[group_key].append(event)
        
        return dict(groups)
    
    def _handle_detection_results(self, results: List[Any]) -> Tuple[Dict, Dict, Dict, Dict]:
        """Handle detection results, including exceptions"""
        behavioral_result = {}
        content_result = {}
        temporal_result = {}
        repo_contexts = {}
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Detection {i} failed: {result}")
                continue
            
            if i == 0:  # Behavioral
                behavioral_result = result or {}
            elif i == 1:  # Content
                content_result = result or {}
            elif i == 2:  # Temporal
                temporal_result = result or {}
            elif i == 3:  # Repository contexts
                repo_contexts = result or {}
        
        return behavioral_result, content_result, temporal_result, repo_contexts
    
    async def _send_to_websocket_channels(
        self, 
        result: Dict[str, Any], 
        severity_level: SeverityLevel
    ):
        """Send results to appropriate WebSocket channels"""
        try:
            # Prepare WebSocket tasks for parallel execution
            websocket_tasks = []
            
            # Send to general anomaly channel
            websocket_tasks.append(
                self.websocket_manager.broadcast_to_channel(
                    'anomalies', 
                    {
                        'type': 'anomaly_detected',
                        'data': result
                    }
                )
            )
            
            # Send to severity-specific channel
            severity_channel = f"anomalies_{severity_level.name.lower()}"
            websocket_tasks.append(
                self.websocket_manager.broadcast_to_channel(
                    severity_channel,
                    {
                        'type': 'severity_anomaly',
                        'severity': severity_level.name,
                        'data': result
                    }
                )
            )
            
            # Send to user-specific channel if needed
            user_login = result.get('user_login')
            if user_login and severity_level in [SeverityLevel.CRITICAL, SeverityLevel.HIGH]:
                websocket_tasks.append(
                    self.websocket_manager.broadcast_to_channel(
                        f"user_{user_login}",
                        {
                            'type': 'user_anomaly',
                            'data': result
                        }
                    )
                )
            
            # Execute all WebSocket sends in parallel
            await asyncio.gather(*websocket_tasks, return_exceptions=True)
        
        except Exception as e:
            logger.error(f"Failed to send WebSocket notification: {e}")
    
    async def _update_processing_stats(self, event_count: int, processing_time: float):
        """Update processing performance statistics"""
        self.processing_stats['events_processed'] += event_count
        self.processing_stats['avg_processing_time'] = (
            (self.processing_stats['avg_processing_time'] + processing_time) / 2
        )
        
        # Reset stats daily
        now = datetime.utcnow()
        if (now - self.processing_stats['last_reset']).days >= 1:
            self.processing_stats = {
                'events_processed': event_count,
                'anomalies_detected': 0,
                'avg_processing_time': processing_time,
                'last_reset': now
            }
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        return {
            **self.processing_stats,
            'uptime_hours': (datetime.utcnow() - self.processing_stats['last_reset']).total_seconds() / 3600,
            'events_per_second': (
                self.processing_stats['events_processed'] / 
                max((datetime.utcnow() - self.processing_stats['last_reset']).total_seconds(), 1)
            )
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all components"""
        health_status = {
            'status': 'healthy',
            'timestamp': datetime.utcnow().isoformat(),
            'components': {}
        }
        
        # Check each component in parallel
        component_checks = {
            'severity_engine': self._check_component_health(self.severity_engine),
            'behavioral_detector': self._check_component_health(self.behavioral_detector),
            'content_detector': self._check_component_health(self.content_detector),
            'temporal_detector': self._check_component_health(self.temporal_detector),
            'context_scorer': self._check_component_health(self.context_scorer),
            'user_profile_manager': self._check_component_health(self.user_profile_manager),
            'repo_profile_manager': self._check_component_health(self.repo_profile_manager),
            'ai_summarizer': self._check_component_health(self.ai_summarizer),
            'context_filter': self._check_component_health(self.context_filter)
        }
        
        # Add Redis check
        if self.redis_client:
            component_checks['redis'] = self._check_redis_health()
        
        # Execute all health checks in parallel
        check_results = await asyncio.gather(*component_checks.values(), return_exceptions=True)
        
        # Process results
        for i, (component_name, _) in enumerate(component_checks.items()):
            result = check_results[i]
            if isinstance(result, Exception):
                health_status['components'][component_name] = f'error: {str(result)}'
                health_status['status'] = 'degraded'
            else:
                health_status['components'][component_name] = result
                if result != 'healthy':
                    health_status['status'] = 'degraded'
        
        return health_status
    
    async def _check_component_health(self, component) -> str:
        """Check health of a single component"""
        try:
            if hasattr(component, '__dict__'):
                return 'healthy'
            else:
                return 'degraded'
        except Exception as e:
            return f'error: {str(e)}'
    
    async def _check_redis_health(self) -> str:
        """Check Redis connection health"""
        try:
            await self.redis_client.ping()
            return 'healthy'
        except Exception as e:
            return f'error: {str(e)}'
    
    def update_detection_weights(self, new_weights: Dict[str, float]):
        """Update detection component weights"""
        # Validate weights sum to 1.0
        total_weight = sum(new_weights.values())
        if abs(total_weight - 1.0) > 0.01:
            raise ValueError(f"Detection weights must sum to 1.0, got {total_weight}")
        
        self.detection_weights.update(new_weights)
        logger.info(f"Updated detection weights: {self.detection_weights}")
    
    async def process_single_event_detailed(
        self, 
        event: Dict[str, Any], 
        context_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Process a single event with detailed analysis - useful for testing"""
        results = await self.process_event_stream([event], context_data)
        return results[0] if results else {}