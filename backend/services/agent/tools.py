import asyncio
import functools
import json
import logging
import subprocess
from pathlib import Path

import boto3
from core.config import settings
from db.session import engine
from langchain_core.tools import tool
from sqlalchemy import text

logger = logging.getLogger(__name__)

uploads_path = Path(settings.UPLOAD_DIR)
bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def log_errors(func):
    """Log an exception raised by a tool before letting it propagate."""
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception:
                logger.exception("Tool %s failed", func.__name__)
                raise

        return async_wrapper

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("Tool %s failed", func.__name__)
            raise

    return sync_wrapper


def _embed_query(query: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId=settings.BEDROCK_EMBEDDINGS_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": query}),
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


@tool
@log_errors
def list_directory(path: str = "") -> str:
    """List files in a directory. Defaults to the uploads directory."""
    target = uploads_path / path if path else uploads_path
    result = subprocess.run(["ls", str(target)], capture_output=True, text=True)
    return result.stdout or result.stderr


@tool
@log_errors
def view_file(path: str, start_line: int, end_line: int) -> str:
    """View file contents within a line range (max 50 lines).

    Args:
        path: File path relative to uploads directory.
        start_line: First line number to display.
        end_line: Last line number to display.
    """
    if end_line - start_line > 50:
        raise ValueError("Range exceeds 50 lines. Use a smaller range.")
    file = uploads_path / path
    result = subprocess.run(
        ["sed", "-n", f"{start_line},{end_line}p", str(file)],
        capture_output=True,
        text=True,
    )
    return result.stdout or result.stderr


@tool
@log_errors
def keyword_search(pattern: str, path: str = "") -> str:
    """Search documents for specific keywords using a grep-like regex query. Returns matching file paths and line numbers.

    Args:
        pattern: Grep-style regex pattern to search for (case-insensitive).
        path: Directory to search in, relative to uploads. Defaults to uploads root.
    """
    target = uploads_path / path if path else uploads_path
    result = subprocess.run(
        f'grep -rin "{pattern}" "{target}" | cut -d: -f1,2',
        shell=True,
        capture_output=True,
        text=True,
    )
    return result.stdout or result.stderr


@tool
@log_errors
async def semantic_search(concept: str) -> str:
    """Search the knowledge base for documents relevant to a high-level topic, concept, or question. Returns the most semantically similar document chunks.

    Args:
        concept: The topic, concept, or question to search for.
    """
    embedding = _embed_query(concept)

    async with engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT text, document_id, 1 - (embedding <=> cast(:embedding as vector)) AS similarity
                FROM chunk
                ORDER BY embedding <=> cast(:embedding as vector)
                LIMIT 4
            """),
            {"embedding": str(embedding)},
        )
        rows = result.fetchall()

    if not rows:
        return "No relevant chunks found in the knowledge base."

    answer = json.dumps(
        [
            {
                "document_id": row.document_id,
                "similarity": round(row.similarity * 100),
                "text": row.text,
            }
            for row in rows
        ]
    )
    print("== RAG Start==")
    print(answer)
    print("== RAG End==")

    return answer


TOOLS = [list_directory, view_file, keyword_search, semantic_search]
# TOOLS = [ semantic_search]
