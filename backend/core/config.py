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
    CORS_ORIGINS: List[str] = ["*"]
    ALLOWED_HOSTS: List[str] = ["*"]

    # AWS Configuration
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = ""

    # Bedrock Models
    BEDROCK_EMBEDDINGS_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    BEDROCK_LLM_MODEL_ID: str = "openai.gpt-oss-20b-1:0"

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

    # Database
    DATABASE_URL: str

    # File Upload Configuration
    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    UPLOAD_DIR: str = os.getenv("UPLOAD_DIR", "./mnt")
    RAW_DIR: str = "raw"
    PROCESSED_DIR: str = "processed"
    ALLOWED_EXTENSIONS: str = ".pdf,.docx,.doc,.txt"
    SUPPORTED_FILE_EXTENSIONS: str = ".pdf,.docx,.doc,.txt"
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


# Create settings instance
settings = Settings()

# Create necessary directories
Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
(Path(settings.UPLOAD_DIR) / settings.RAW_DIR).mkdir(parents=True, exist_ok=True)
(Path(settings.UPLOAD_DIR) / settings.PROCESSED_DIR).mkdir(parents=True, exist_ok=True)
