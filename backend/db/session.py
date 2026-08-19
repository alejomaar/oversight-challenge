import json
from urllib.parse import quote_plus

import boto3
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from core.config import settings


def _database_url() -> str:
    """Build the connection URL.

    Local development sets DATABASE_URL directly. In AWS the database is private
    and its password lives in Secrets Manager, so it is fetched at cold start
    rather than baked into the function's environment.
    """
    return settings.DATABASE_URL



engine = create_async_engine(_database_url(), pool_pre_ping=True)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with async_session() as session:
        yield session
