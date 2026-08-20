"""
Agent tools. Every tool reads the knowledge base out of Postgres.

Document text and embeddings are persisted in the `chunk` table, so the tools
need no filesystem and no shell. Original uploads stay in S3 for provenance.
"""

import json
import logging
import uuid
from typing import Annotated

import boto3
from config.settings import settings
from models import Chunk, Document
from infrastructure.db import db_session
from langchain_core.messages import ToolMessage
from langchain_core.tools import InjectedToolCallId, tool
from langgraph.types import Command
from sqlalchemy import func, select, text

logger = logging.getLogger(__name__)

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)

# Guards a pathological regex from holding a connection open.
SEARCH_TIMEOUT_MS = 5000

# Caps how much document text one read_document call can put in the context.
MAX_READ_CHARS = 8000


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
async def semantic_search(
    concept: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Look things up by meaning. Start here for any question about the documents.

    Returns a JSON list of the best pieces of text, best first, each with: `text`
    (read it and answer from it), `file_name` (the document it came from),
    `similarity` (0..1, how good a match it is), and `document_id` plus
    `char_start`/`char_end` (give these to read_document to see more around it).

    Args:
        concept: The topic, concept, or question to search for.
    """
    embedding = _embed_query(concept)
    distance = Chunk.embedding.cosine_distance(embedding)

    async with db_session() as session:
        result = await session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.chunk_index,
                Chunk.content,
                Chunk.char_start,
                Chunk.char_end,
                Document.file_name,
                Document.s3_key,
                (1 - distance).label("similarity"),
            )
            .join(Document, Document.id == Chunk.document_id)
            .order_by(distance)
            .limit(settings.TOP_K_CHUNKS)
        )
        rows = result.fetchall()

    if not rows:
        return Command(update={
            "messages": [ToolMessage(
                content="No relevant chunks found in the knowledge base.",
                tool_call_id=tool_call_id,
            )],
        })

    # State keeps only an excerpt per chunk (for the response's sources list);
    # the model gets the full text so it can actually answer from it.
    hits = {
        str(row.id): {
            "source": row.file_name,
            "chunk_index": row.chunk_index,
            "file_path": row.s3_key,
            "similarity": round(row.similarity, 3),
            "content_preview": row.content[:280],
        }
        for row in rows
    }
    model_view = [
        {
            "chunk_id": str(row.id),
            "document_id": str(row.document_id),
            "file_name": row.file_name,
            "similarity": round(row.similarity, 3),
            "char_start": row.char_start,
            "char_end": row.char_end,
            "text": row.content,
        }
        for row in rows
    ]

    return Command(update={
        "semantic_matches": hits,
        "messages": [ToolMessage(content=json.dumps(model_view), tool_call_id=tool_call_id)],
    })


@tool
async def keyword_search(
    pattern: str,
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command:
    """Look for an exact word or phrase, spelled just that way — a name, a code, a number.

    Returns a JSON list saying where it was found, but not the text itself:
    `file_name` and `document_id` (which document it is in), `char_start`/
    `char_end` (what spot in it — give these to read_document to actually read
    it), and `keyword_score` (0..1, higher means the word is rare, so the match
    matters more).

    Args:
        pattern: POSIX regex, for example "refund|reimburse" or "SLA of [0-9]+%".
    """
    matches = Chunk.content.op("~*")(pattern)

    async with db_session() as session:
        await session.execute(text(f"SET LOCAL statement_timeout = {SEARCH_TIMEOUT_MS}"))
        result = await session.execute(
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.chunk_index,
                Chunk.content,
                Chunk.char_start,
                Chunk.char_end,
                Document.file_name,
                Document.s3_key,
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(matches)
            .order_by(Chunk.document_id, Chunk.chunk_index)
            .limit(10)
        )
        rows = result.fetchall()

        if not rows:
            return Command(update={
                "messages": [ToolMessage(
                    content=f"No matches for pattern {pattern!r}.",
                    tool_call_id=tool_call_id,
                )],
            })

        # Counted against full document text, not chunk text, so a term split
        # across a chunk boundary still counts toward its document.
        docs_matched = (await session.execute(
            select(func.count()).select_from(Document).where(Document.content.op("~*")(pattern))
        )).scalar_one()
        total_docs = (await session.execute(
            select(func.count()).select_from(Document)
        )).scalar_one()

    # A term matched in nearly every document is a weak signal; a rare, specific
    # match is a strong one. Every matched chunk carries that document-level
    # rarity as its keyword score, so it can be fused with cosine similarity.
    # The +1 keeps a term present in every document from scoring 0 — it is still
    # evidence, just the weakest kind, and a one-document knowledge base would
    # otherwise score every match at 0.
    score = round(1 - (docs_matched / (total_docs + 1)), 3) if total_docs else 0.0

    # Same shape as semantic_search's hits, minus `similarity`, so the two can be
    # merged on chunk_id when the response's sources are built.
    keyword_matches = {
        str(row.id): {
            "source": row.file_name,
            "chunk_index": row.chunk_index,
            "file_path": row.s3_key,
            "keyword_score": score,
            "content_preview": row.content[:280],
        }
        for row in rows
    }

    # Locations only: the span of each matching chunk, for read_document to
    # expand. Returning the text here would duplicate what that call fetches.
    model_view = [
        {
            "chunk_id": str(row.id),
            "document_id": str(row.document_id),
            "file_name": row.file_name,
            "keyword_score": score,
            "char_start": row.char_start,
            "char_end": row.char_end,
        }
        for row in rows
    ]

    return Command(update={
        "keyword_matches": keyword_matches,
        "messages": [ToolMessage(content=json.dumps(model_view), tool_call_id=tool_call_id)],
    })


@tool
async def list_documents(offset: int = 0, limit: int = 20) -> str:
    """See what documents are here. Just their names, none of what is inside them.

    Returns JSON: `documents`, a list of {document_id, file_name, chunks} where
    `chunks` is how many pieces the document was cut into (bigger means longer),
    plus `has_more` — if true there are more, so call again with offset += limit.

    Args:
        offset: Zero-based index of the first document to return.
        limit: Maximum number of documents to return (max 200).
    """
    capped_limit = min(limit, 200)
    async with db_session() as session:
        result = await session.execute(
            select(Document.id, Document.file_name, func.count(Chunk.id).label("chunks"))
            .outerjoin(Chunk, Chunk.document_id == Document.id)
            .group_by(Document.id)
            .order_by(Document.id)
            .offset(max(offset, 0))
            .limit(capped_limit + 1)
        )
        rows = result.fetchall()

    if not rows:
        return "No documents found." if offset else "The knowledge base is empty."

    has_more = len(rows) > capped_limit
    rows = rows[:capped_limit]

    return json.dumps({
        "documents": [
            {"document_id": str(row.id), "file_name": row.file_name, "chunks": row.chunks}
            for row in rows
        ],
        "has_more": has_more,
    })


@tool
async def read_document(document_id: str, char_start: int = 0, char_end: int = MAX_READ_CHARS) -> str:
    """Read part of one document. Use it to see more around a search hit.

    Returns JSON: `text`, what you asked for; `char_start`/`char_end`, the part
    you actually got; and `document_length`, the document's total size — if
    char_end is smaller, call again from there to read the rest.

    Args:
        document_id: Which document, from list_documents or a search.
        char_start: Where to start reading.
        char_end: Where to stop. Keep char_end - char_start under 8000.
    """
    async with db_session() as session:
        content = (await session.execute(
            select(Document.content).where(Document.id == uuid.UUID(document_id))
        )).scalar_one_or_none()

    if content is None:
        return f"No document found for {document_id!r}."

    start = max(char_start, 0)
    end = min(max(char_end, start), start + MAX_READ_CHARS, len(content))

    return json.dumps({
        "document_id": document_id,
        "char_start": start,
        "char_end": end,
        "document_length": len(content),
        "text": content[start:end],
    })


TOOLS = [semantic_search, keyword_search, list_documents, read_document]
