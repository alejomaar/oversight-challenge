"""Database URL construction for the app's async engine. In AWS the database is
private and its password lives in Secrets Manager, so it is fetched at cold
start rather than baked into the function's environment. Local dev sets
DATABASE_URL directly and skips that lookup entirely.
"""

import json
from urllib.parse import quote_plus

import boto3

from core.config import settings


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
