"""
AWS Lambda handler for FastAPI application using Mangum ASGI adapter.
"""

from mangum import Mangum
from app import app

handler = Mangum(app, lifespan="auto")
