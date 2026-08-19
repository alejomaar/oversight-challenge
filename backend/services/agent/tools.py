"""
Agent tools. Every tool reads the knowledge base out of Postgres.

Document text and embeddings are persisted in the `chunk` table, so the tools
need no filesystem and no shell. Original uploads stay in S3 for provenance.
"""

import json
import logging

import boto3
from core.config import settings
from db.session import engine
from langchain_core.tools import tool
from sqlalchemy import text

logger = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)

# Guards a pathological regex from holding a connection open.
SEARCH_TIMEOUT_MS = 5000


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
async def semantic_search(concept: str, top_k: int = 4) -> str:
    """Search the knowledge base for chunks semantically related to a topic, concept, or question. Returns the most similar chunks with their similarity scores.

    Args:
        concept: The topic, concept, or question to search for.
        top_k: How many chunks to return (max 20).
    """
    embedding = _embed_query(concept)

    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT chunk_id, document_id, text,
                       1 - (embedding <=> cast(:embedding as vector)) AS similarity
                FROM chunk
                ORDER BY embedding <=> cast(:embedding as vector)
                LIMIT :limit
            """),
            {"embedding": str(embedding), "limit": min(top_k, 20)},
        )
        rows = result.fetchall()

    if not rows:
        return "No relevant chunks found in the knowledge base."

    return json.dumps([
        {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "similarity": round(row.similarity, 3),
            "text": row.text,
        }
        for row in rows
    ])


@tool
async def keyword_search(pattern: str, document_id: str = "") -> str:
    """Search document text with a case-insensitive POSIX regular expression. Use it for exact terms, codes, or phrasing that semantic search may miss.

    Args:
        pattern: POSIX regex, for example "refund|reimburse" or "SLA of [0-9]+%".
        document_id: Restrict the search to one document. Empty searches all documents.
    """
    async with engine.begin() as conn:
        await conn.execute(text(f"SET LOCAL statement_timeout = {SEARCH_TIMEOUT_MS}"))
        result = await conn.execute(
            text("""
                SELECT chunk_id, document_id, text
                FROM chunk
                WHERE text ~* :pattern
                  AND (:document_id = '' OR document_id = :document_id)
                ORDER BY document_id, char_start
                LIMIT 10
            """),
            {"pattern": pattern, "document_id": document_id},
        )
        rows = result.fetchall()

    if not rows:
        return f"No matches for pattern {pattern!r}."

    return json.dumps([
        {
            "chunk_id": row.chunk_id,
            "document_id": row.document_id,
            "text": row.text,
        }
        for row in rows
    ])


@tool
async def list_documents() -> str:
    """List every document in the knowledge base with its chunk count. Use it to discover what is available before searching."""
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT document_id, COUNT(*) AS chunks
                FROM chunk
                GROUP BY document_id
                ORDER BY document_id
            """)
        )
        rows = result.fetchall()

    if not rows:
        return "The knowledge base is empty."

    return json.dumps([
        {"document_id": row.document_id, "chunks": row.chunks}
        for row in rows
    ])


@tool
async def read_document(document_id: str, start_chunk: int = 0, limit: int = 5) -> str:
    """Read consecutive chunks of one document in their original order. Use it to read around a match or to understand a document's structure.

    Args:
        document_id: Identifier returned by list_documents or a search tool.
        start_chunk: Zero-based index of the first chunk to read.
        limit: How many chunks to return (max 10).
    """
    async with engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT chunk_id, text
                FROM chunk
                WHERE document_id = :document_id
                ORDER BY char_start
                OFFSET :offset
                LIMIT :limit
            """),
            {
                "document_id": document_id,
                "offset": max(start_chunk, 0),
                "limit": min(limit, 10),
            },
        )
        rows = result.fetchall()

    if not rows:
        return f"No chunks found for document {document_id!r}."

    return json.dumps([
        {"chunk_id": row.chunk_id, "text": row.text}
        for row in rows
    ])


TOOLS = [semantic_search, keyword_search, list_documents, read_document]
