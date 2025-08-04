import pytest
import pytest_asyncio
import random
import asyncio
import time
import statistics
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from ..stream_processor import AnomalyStreamProcessor
from ..scoring.severity_engine import SeverityEngine
from ..models.anomaly_score import AnomalyScore

from ..queue.priority_queue import AnomalyPriorityQueue
from ..models.anomaly_score import SeverityLevel
import psutil
import os


class TestAnomalyDetectionPerformance:
    """Performance tests for the anomaly detection system"""
    
    @pytest_asyncio.fixture
    async def mock_redis_client(self):
        """Fast mock Redis client for performance testing"""
        redis_mock = AsyncMock()
        redis_mock.ping.return_value = True
        redis_mock.get.return_value = None
        redis_mock.setex.return_value = True
        redis_mock.hgetall.return_value = {}
        redis_mock.hincrby.return_value = 1
        redis_mock.hset.return_value = True
        redis_mock.expire.return_value = True
        redis_mock.zcard.return_value = 0
        redis_mock.zadd.return_value = 1
        redis_mock.zrevrange.return_value = []
        redis_mock.zrem.return_value = 1
        return redis_mock
    
    @pytest_asyncio.fixture
    def performance_events(self, count=100):
        """Generate events for performance testing"""
        events = []
        base_time = datetime.now()
        
        for i in range(count):
            event = {
                'id': f'perf_event_{i}',
                'type': 'PushEvent',
                'actor_login': f'user_{i % 10}',  # 10 different users
                'repo_name': f'org/repo_{i % 5}',  # 5 different repos
                'created_at': (base_time + timedelta(seconds=i)).isoformat() + 'Z',
                'payload': {
                    'size': i % 10 + 1,
                    'commits': [
                        {
                            'sha': f'commit_{i}',
                            'message': f'Commit number {i} with some content'
                        }
                    ]
                }
            }
            events.append(event)
        
        return events
    
    @pytest_asyncio.fixture
    async def stream_processor(self, mock_redis_client):
        """Create optimized stream processor for performance testing"""
        with patch('aiohttp.ClientSession') as mock_session:
            # Mock fast GitHub API responses
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {
                'name': 'test_repo',
                'stargazers_count': 100,
                'forks_count': 20,
                'language': 'Python'
            }
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Mock OpenAI for AI summarization
            with patch('openai.ChatCompletion.acreate') as mock_openai:
                mock_openai.return_value = {
                    'choices': [{'message': {'content': 'Test summary'}}]
                }
                
                processor = AnomalyStreamProcessor(
                    redis_client=mock_redis_client,
                    websocket_manager=None,  # Disable WebSocket for performance
                    github_token='test_token',
                    openai_api_key='test_key'
                )
                return processor
    
    @pytest.mark.asyncio
    async def test_single_event_processing_time(self, stream_processor):
        """Test processing time for a single event"""
        
        single_event = [{
            'id': 'timing_test',
            'type': 'PushEvent',
            'actor_login': 'test_user',
            'repo_name': 'test_org/test_repo',
            'created_at': '2024-01-01T12:00:00Z',
            'payload': {
                'size': 1,
                'commits': [{'sha': 'abc123', 'message': 'Test commit'}]
            }
        }]
        
        # Warm up
        await stream_processor.process_event_stream(single_event)
        
        # Time multiple runs
        times = []
        for _ in range(10):
            start_time = time.time()
            await stream_processor.process_event_stream(single_event)
            end_time = time.time()
            times.append((end_time - start_time) * 1000)  # Convert to milliseconds
        
        avg_time = statistics.mean(times)
        max_time = max(times)
        
        print(f"Single event processing - Avg: {avg_time:.2f}ms, Max: {max_time:.2f}ms")
        
        # Should process single event within 2 seconds
        assert avg_time < 2000
        assert max_time < 5000
    
    @pytest.mark.asyncio
    async def test_batch_processing_performance(self, stream_processor, performance_events):
        """Test batch processing performance"""
        
        batch_sizes = [10, 50, 100]
        
        for batch_size in batch_sizes:
            events = performance_events[:batch_size]
            
            # Warm up
            await stream_processor.process_event_stream(events[:5])
            
            # Time batch processing
            start_time = time.time()
            results = await stream_processor.process_event_stream(events)
            end_time = time.time()
            
            processing_time = (end_time - start_time) * 1000  # milliseconds
            events_per_second = len(events) / (processing_time / 1000)
            time_per_event = processing_time / len(events)
            
            print(f"Batch size {batch_size}: {processing_time:.2f}ms total, "
                  f"{time_per_event:.2f}ms per event, {events_per_second:.1f} events/sec")
            
            # Verify all events were processed
            assert len(results) == batch_size
            
            # Performance expectations
            assert time_per_event < 500  # Less than 500ms per event
            assert events_per_second > 2  # At least 2 events per second
    
    @pytest.mark.asyncio
    async def test_parallel_vs_sequential_processing(self, mock_redis_client):
        """Compare parallel vs sequential processing performance"""
        
        events = [
            {
                'id': f'parallel_test_{i}',
                'type': 'PushEvent',
                'actor_login': f'user_{i}',
                'repo_name': f'org/repo_{i}',
                'created_at': '2024-01-01T12:00:00Z',
                'payload': {'size': 1, 'commits': [{'sha': f'commit_{i}', 'message': f'Message {i}'}]}
            }
            for i in range(20)
        ]
        
        with patch('aiohttp.ClientSession') as mock_session:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = {'name': 'test', 'stargazers_count': 100}
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value = mock_response
            
            # Test parallel processing (default)
            processor_parallel = AnomalyStreamProcessor(
                redis_client=mock_redis_client,
                websocket_manager=None,
                github_token='test_token',
                openai_api_key='test_key'
            )
            
            start_time = time.time()
            results_parallel = await processor_parallel.process_event_stream(events)
            parallel_time = time.time() - start_time
        
        print(f"Parallel processing: {parallel_time:.2f}s for {len(events)} events")
        print(f"Parallel rate: {len(events)/parallel_time:.1f} events/sec")
        
        # Verify results
        assert len(results_parallel) == len(events)
        
        # Parallel processing should be reasonably fast
        assert parallel_time < 30  # Should complete within 30 seconds
        assert len(events)/parallel_time > 0.5  # At least 0.5 events per second
    
    @pytest.mark.asyncio
    async def test_memory_usage_stability(self, stream_processor):
        """Test memory usage doesn't grow excessively during processing"""
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Process multiple batches
        for batch in range(5):
            events = [
                {
                    'id': f'memory_test_{batch}_{i}',
                    'type': 'PushEvent',
                    'actor_login': f'user_{i}',
                    'repo_name': f'org/repo_{i}',
                    'created_at': '2024-01-01T12:00:00Z',
                    'payload': {'size': 1, 'commits': [{'sha': f'commit_{i}', 'message': f'Message {i}'}]}
                }
                for i in range(50)
            ]
            
            await stream_processor.process_event_stream(events)
            
            # Force garbage collection
            import gc
            gc.collect()
            
            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_growth = current_memory - initial_memory
            
            print(f"Batch {batch}: Memory usage {current_memory:.1f}MB (growth: {memory_growth:.1f}MB)")
            
            # Memory growth should be reasonable (less than 100MB per batch)
            assert memory_growth < 100
    
    @pytest.mark.asyncio
    async def test_high_volume_secret_detection(self, stream_processor):
        """Test performance with high volume of secret-containing events"""
        
        secret_patterns = [
            'AKIA1234567890123456',  # AWS key
            'ghp_1234567890123456789012345678901234567890',  # GitHub token
            'sk_live_1234567890123456789012345',  # Stripe key
            'xoxb-123456789012-123456789012-1234567890123456789012',  # Slack token
        ]
        
        events = []
        for i in range(100):
            secret = secret_patterns[i % len(secret_patterns)]
            event = {
                'id': f'secret_perf_{i}',
                'type': 'PushEvent',
                'actor_login': f'user_{i % 10}',
                'repo_name': f'org/repo_{i % 5}',
                'created_at': '2024-01-01T12:00:00Z',
                'payload': {
                    'commits': [
                        {
                            'sha': f'commit_{i}',
                            'message': f'Update config with {secret} for authentication'
                        }
                    ]
                }
            }
            events.append(event)
        
        start_time = time.time()
        results = await stream_processor.process_event_stream(events)
        end_time = time.time()
        
        processing_time = end_time - start_time
        
        print(f"High-volume secret detection: {processing_time:.2f}s for {len(events)} events")
        print(f"Rate: {len(events)/processing_time:.1f} events/sec")
        
        # Verify all events were processed and secrets detected
        assert len(results) == len(events)
        
        # Check that secrets were detected
        total_secrets = sum(
            len(r['content_analysis'].get('secret_detections', []))
            for r in results
        )
        assert total_secrets >= len(events)  # At least one secret per event
        
        # Performance should still be reasonable even with secret detection
        assert processing_time < 60  # Within 1 minute
        assert len(events)/processing_time > 1  # At least 1 event per second
    
    @pytest.mark.asyncio
    async def test_concurrent_processing_load(self, stream_processor):
        """Test system under concurrent processing load"""
        
        async def process_batch(batch_id, event_count=20):
            events = [
                {
                    'id': f'concurrent_{batch_id}_{i}',
                    'type': 'PushEvent',
                    'actor_login': f'user_{i}',
                    'repo_name': f'org/repo_{i}',
                    'created_at': '2024-01-01T12:00:00Z',
                    'payload': {'size': 1, 'commits': [{'sha': f'commit_{i}', 'message': f'Message {i}'}]}
                }
                for i in range(event_count)
            ]
            
            start_time = time.time()
            results = await stream_processor.process_event_stream(events)
            end_time = time.time()
            
            return {
                'batch_id': batch_id,
                'event_count': len(events),
                'result_count': len(results),
                'processing_time': end_time - start_time
            }
        
        # Run multiple batches concurrently
        concurrent_batches = 5
        start_time = time.time()
        
        tasks = [process_batch(i) for i in range(concurrent_batches)]
        batch_results = await asyncio.gather(*tasks)
        
        total_time = time.time() - start_time
        
        # Analyze results
        total_events = sum(r['event_count'] for r in batch_results)
        total_results = sum(r['result_count'] for r in batch_results)
        avg_batch_time = statistics.mean(r['processing_time'] for r in batch_results)
        max_batch_time = max(r['processing_time'] for r in batch_results)
        
        print(f"Concurrent processing: {concurrent_batches} batches, {total_events} total events")
        print(f"Total time: {total_time:.2f}s, Avg batch time: {avg_batch_time:.2f}s, Max batch time: {max_batch_time:.2f}s")
        print(f"Overall rate: {total_events/total_time:.1f} events/sec")
        
        # Verify all events were processed
        assert total_results == total_events
        
        # Concurrent processing should be efficient
        assert total_time < max_batch_time * concurrent_batches  # Should be faster than sequential
        assert total_events/total_time > 2  # At least 2 events per second overall
    
    @pytest.mark.asyncio
    async def test_queue_performance(self, mock_redis_client):
        """Test priority queue performance"""
        
        queue = AnomalyPriorityQueue(mock_redis_client)
        
        # Mock Redis operations for performance testing
        mock_redis_client.zcard.return_value = 0
        mock_redis_client.zadd.return_value = 1
        mock_redis_client.expire.return_value = True
        
        # Test enqueue performance
        anomalies = [
            {
                'event_id': f'queue_perf_{i}',
                'final_anomaly_score': 0.5,
                'user_login': f'user_{i}',
                'repository_name': 'test_repo',
                'detection_scores': {'repository_criticality': 0.3}
            }
            for i in range(100)
        ]
        
        start_time = time.time()
        
        enqueue_tasks = []
        for i, anomaly in enumerate(anomalies):
            severity = list(SeverityLevel)[i % len(SeverityLevel)]
            task = queue.enqueue_anomaly(anomaly, severity)
            enqueue_tasks.append(task)
        
        # Execute all enqueue operations
        enqueue_results = await asyncio.gather(*enqueue_tasks)
        
        enqueue_time = time.time() - start_time
        
        print(f"Queue enqueue performance: {len(anomalies)} items in {enqueue_time:.2f}s")
        print(f"Rate: {len(anomalies)/enqueue_time:.1f} enqueues/sec")
        
        # All enqueues should succeed
        assert all(enqueue_results)
        
        # Should be able to enqueue at least 50 items per second
        assert len(anomalies)/enqueue_time > 50
    
    def test_severity_calculation_performance(self):
        """Test performance of severity calculation"""
        engine = SeverityEngine()
        
        # Create sample anomaly scores
        anomaly_scores = []
        for i in range(1000):
            score = AnomalyScore(
                behavioral_anomaly=random.uniform(0.0, 1.0),
                content_risk=random.uniform(0.0, 1.0),
                temporal_anomaly=random.uniform(0.0, 1.0),
                repository_criticality=random.uniform(0.0, 1.0)
            )
            score.calculate_final_score()
            anomaly_scores.append(score)
        
        # Sample event and context
        sample_event = {'type': 'PushEvent', 'actor_login': 'test_user'}
        sample_context = {'repository_criticality_score': 0.5}
        
        # Time severity calculations
        start_time = time.time()
        
        for score in anomaly_scores:
            result = engine.calculate_severity(
                behavioral_score=score.behavioral_anomaly,
                content_score=score.content_risk,
                temporal_score=score.temporal_anomaly,
                repository_score=score.repository_criticality,
                context_data=sample_context,
                incident_type=sample_event.get('type', 'unknown')
            )
            assert 0.0 <= result.final_score <= 1.0
        
        end_time = time.time()
        calculation_time = end_time - start_time
        
        print(f"Severity calculation performance: {len(anomaly_scores)} calculations in {calculation_time:.3f}s")
        print(f"Rate: {len(anomaly_scores)/calculation_time:.1f} calculations/sec")
        
        # Should be able to calculate at least 1000 severities per second
        assert len(anomaly_scores)/calculation_time > 1000