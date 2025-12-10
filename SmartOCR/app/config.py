from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseSettings


load_dotenv()


class Settings(BaseSettings):
    API_KEY: Optional[str] = os.getenv("SMARTOCR_API_KEY")
    POPPLER_PATH: Optional[str] = os.getenv("POPPLER_PATH")
    TESSERACT_CMD: Optional[str] = os.getenv("TESSERACT_CMD")
    WEBHOOK_TIMEOUT_SECONDS: float = float(os.getenv("WEBHOOK_TIMEOUT_SECONDS", "3.0"))

    # RabbitMQ settings
    USE_RABBITMQ: bool = os.getenv("USE_RABBITMQ", "false").lower() == "true"
    AMQP_URL: str = os.getenv("AMQP_URL", "amqp://guest:guest@localhost/")

    # Worker settings
    RUN_WORKER: bool = os.getenv("RUN_WORKER", "true").lower() == "true"

    # Database settings
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/smartocr")
    USE_POSTGRES: bool = os.getenv("USE_POSTGRES", "false").lower() == "true"

    # MinIO settings
    MINIO_ENDPOINT: str = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    MINIO_ACCESS_KEY: str = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
    MINIO_SECRET_KEY: str = os.getenv("MINIO_SECRET_KEY", "minioadmin")
    MINIO_BUCKET: str = os.getenv("MINIO_BUCKET", "smartocr")
    MINIO_SECURE: bool = os.getenv("MINIO_SECURE", "false").lower() == "true"
    
    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
