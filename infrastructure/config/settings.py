"""Deployment settings: every environment variable the stack reads, the
constants shared across constructs, and the resource naming convention.

    regional:  <project>-<environment>-<resource>
    global:    <project>-<environment>-<resource>-<account-id>

S3 bucket names share one namespace across all of AWS, so they carry the
account id. Everything else is already scoped to an account and region.
"""

import os
from pathlib import Path

from aws_cdk import Stack

PROJECT = "rag-chat"

# Same default as backend/config/settings.py, so a deploy without an env file
# targets the same names as one with .env.prod.
ENVIRONMENT = os.environ.get("ENVIRONMENT", "prod")

# Set by the CDK CLI from the active AWS profile.
AWS_ACCOUNT = os.getenv("CDK_DEFAULT_ACCOUNT")
AWS_REGION = os.getenv("CDK_DEFAULT_REGION")

# The only address allowed to reach the database from outside the VPC.
DEV_ACCESS_IP = os.environ["DEV_ACCESS_IP"]

# Bedrock models. The Lambda's IAM policy is scoped to exactly these ids.
EMBEDDINGS_MODEL_ID = "amazon.titan-embed-text-v2:0"
LLM_MODEL_ID = "openai.gpt-oss-20b-1:0"

# Postgres database inside the RDS instance - created by RDS, then passed to
# the Lambda so both ends agree on the name.
DB_NAME = "rag_db"

# The backend/ application directory, built into the Lambda's Docker image.
PROJECT_ROOT = str(Path(__file__).resolve().parents[2] / "backend")


def resource_name(resource: str) -> str:
    return f"{PROJECT}-{ENVIRONMENT}-{resource}"


def global_resource_name(stack: Stack, resource: str) -> str:
    return f"{resource_name(resource)}-{stack.account}"
