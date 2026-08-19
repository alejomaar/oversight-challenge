"""Database engine/session, and URL construction for the app's async engine.

In AWS the database is private and its password lives in Secrets Manager, so
it is fetched at cold start rather than baked into the function's
environment. Local dev sets DATABASE_URL directly and skips that lookup
entirely.
"""

import json
from contextlib import asynccontextmanager
from urllib.parse import quote_plus

import boto3
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from config.settings import settings


def _credentials() -> tuple[str, str]:
    client = boto3.client("secretsmanager", region_name=settings.AWS_REGION)
    secret = json.loads(client.get_secret_value(SecretId=settings.DB_SECRET_ARN)["SecretString"])
    return secret["username"], secret["password"]


def async_database_url() -> str:
    """asyncpg URL used by the application at runtime."""
    if settings.DATABASE_URL:
        return settings.DATABASE_URL
    username, password = _credentials()
    return (
        f"postgresql+asyncpg://{username}:{quote_plus(password)}"
        f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


engine = create_async_engine(async_database_url(), pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@asynccontextmanager
async def db_session():
    """Session wrapper for code outside FastAPI's dependency injection (e.g. agent tools)."""
    async with async_session() as session:
        yield session
