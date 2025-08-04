import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


def convert_to_github_api_format(event):
    """Convert test event from flat format to GitHub API format"""
    if 'actor' not in event and 'actor_login' in event:
        actor_login = event.pop('actor_login')
        event['actor'] = {
            'id': 12345,
            'login': actor_login,
            'display_login': actor_login,
            'gravatar_id': '',
            'url': f"https://api.github.com/users/{actor_login}",
            'avatar_url': f"https://avatars.githubusercontent.com/u/12345?"
        }
    
    if 'repo' not in event and 'repo_name' in event:
        repo_name = event.pop('repo_name')
        event['repo'] = {
            'id': 67890,
            'name': repo_name,
            'url': f"https://api.github.com/repos/{repo_name}"
        }
    
    return event


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def mock_redis():
    """Mock Redis client for testing"""
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

@pytest.fixture
def sample_events():
    """Sample GitHub events for testing"""
    return [
        {
            'id': '12345',
            'type': 'PushEvent',
            'actor_login': 'test_user',
            'repo_name': 'test_org/test_repo',
            'created_at': '2024-01-01T12:00:00Z',
            'payload': {
                'size': 1,
                'commits': [
                    {
                        'sha': 'abc123',
                        'message': 'Test commit',
                        'url': 'https://github.com/test_org/test_repo/commit/abc123'
                    }
                ]
            }
        }
    ]