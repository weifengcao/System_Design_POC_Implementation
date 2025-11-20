from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    APP_NAME: str = "LLM Memory Layer"
    VERSION: str = "0.1.0"
    
    # Storage Paths
    # Database
    POSTGRES_USER: str = "user"
    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "aimemory"
    DB_SSL_MODE: str = "prefer"
    
    @property
    def DB_URL(self) -> str:
        # Construct Async DB URL
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    # Redis
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0
    REDIS_PASSWORD: str = "change-me-in-prod"
    
    @property
    def REDIS_URL(self) -> str:
        return f"redis://:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"
    
    # Model Configuration
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"

    # Security
    ENABLE_PII_REDACTION: bool = True
    AIMEMORY_API_KEY: str = "change-me-in-prod"

    class Config:
        env_file = ".env"
        secrets_dir = "/run/secrets"

@lru_cache()
def get_settings():
    return Settings()
