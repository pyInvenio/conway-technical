from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://conway_technical:password@localhost/conway_technical"
    redis_url: str = "redis://localhost:6379"
    github_token: str = "your-github-token-change-in-production"
    
    # Optional AI
    openai_api_key: Optional[str] = None
    
    # Polling settings
    poll_interval: int = 30  # seconds - increased for better rate limit management
    rate_limit_window: int = 3600  # 1 hour
    rate_limit_requests: int = 4500  # Leave buffer from 5000
    rate_limit_safety_margin: int = 500  # Keep this many requests in reserve
    max_concurrent_pollers: int = 3  # Maximum concurrent API requests across all pollers
    max_pages_per_cycle: int = 3  # Reduced from default to conserve rate limit
    
    # Security
    jwt_secret: str = "your-secret-key-change-in-production"
    
    class Config:
        env_file = ".env"

settings = Settings()