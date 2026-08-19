"""
Configuration settings for the Knowledge Base RAG system.
Loads from environment variables with sensible defaults.
"""

from pydantic_settings import BaseSettings
from typing import List


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

    # Document storage - original files are kept in S3, extracted text in Postgres
    S3_BUCKET_NAME: str 
    RAW_PREFIX: str = "raw"

    # Bedrock Models
    BEDROCK_EMBEDDINGS_MODEL_ID: str = "amazon.titan-embed-text-v2:0"
    BEDROCK_LLM_MODEL_ID: str = "openai.gpt-oss-20b-1:0"

    # RAG Configuration
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 200
    TOP_K_CHUNKS: int = 5
    TEMPERATURE: float = 0.7
    MAX_TOKENS: int = 1000

    # Database - local dev sets DATABASE_URL directly; in AWS it's left blank
    # and built at cold start from DB_HOST/DB_PORT/DB_NAME plus the password
    # read from the Secrets Manager secret named by DB_SECRET_ARN.
    DATABASE_URL: str = ""
    DB_SECRET_ARN: str = ""
    DB_HOST: str = ""
    DB_PORT: str = "5432"
    DB_NAME: str = "rag_db"


    # File Upload Configuration
    MAX_FILE_SIZE: int = 50 * 1024 * 1024
    ALLOWED_EXTENSIONS: str = ".pdf,.docx,.doc,.txt"

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"


settings = Settings()
