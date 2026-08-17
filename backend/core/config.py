"""
Configuration settings for the Knowledge Base RAG system.
Loads from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import List
from pathlib import Path
import os


class Settings(BaseSettings):
    """Application settings."""

    # Environment
    ENVIRONMENT: str = "production"
    DEBUG: bool = False

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8000"
    ]
    ALLOWED_HOSTS: List[str] = ["*"]

    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "testing-alejo"

    # Bedrock Models
    BEDROCK_EMBEDDINGS_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    BEDROCK_LLM_MODEL_ID: str = "openai.gpt-oss-20b-1:0"

    # Vector Store Configuration
    VECTOR_STORE_PATH: str = "/tmp/vectorstore"

    # RAG Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_CHUNKS: int = 5
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 1000
    RETRIEVER_EXPAND_K_MULTIPLIER: int = 3
    RETRIEVER_MAX_K: int = 20
    CONFIDENCE_SCORE_WEIGHTS: str = "0.5:0.3:0.1:0.1"
    CONFIDENCE_SCORE_POWER: float = 0.9

    # File Upload Configuration
    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    UPLOAD_DIR: str = "/mnt/s3"

    ALLOWED_EXTENSIONS: str = ".pdf,.docx,.doc,.txt"
    SUPPORTED_FILE_EXTENSIONS: str = ".pdf,.docx,.doc,.txt"

    # Security
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Logging
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Create settings instance
settings = Settings()

# Create necessary directories
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.VECTOR_STORE_PATH).mkdir(parents=True, exist_ok=True)

