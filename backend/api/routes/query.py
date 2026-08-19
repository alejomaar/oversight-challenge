"""
Query endpoints for RAG system.
"""

import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter
from langchain_core.messages import AIMessage, HumanMessage
from sqlalchemy import text as sql_text

from core.config import settings
from db.session import engine
from models.query import ConfidenceBreakdown, QueryMetadata, QueryRequest, QueryResponse, SourceHit
from services.agent import agent

router = APIRouter()
logger = logging.getLogger(__name__)


def _confidence_breakdown(scores: list[float], used_keyword_search: bool) -> ConfidenceBreakdown:
    if not scores:
        return ConfidenceBreakdown(
            best_similarity=0.0, avg_similarity=0.0, consistency=0.0,
            keyword_match=0.0, final_score=0.0,
        )

    best = max(scores)
    avg = sum(scores) / len(scores)
    consistency = round(1.0 - (best - min(scores)), 3)
    keyword_match = 1.0 if used_keyword_search else 0.0
    final_score = round(0.5 * best + 0.3 * avg + 0.1 * consistency + 0.1 * keyword_match, 3)

    return ConfidenceBreakdown(
        best_similarity=round(best, 3),
        avg_similarity=round(avg, 3),
        consistency=consistency,
        keyword_match=keyword_match,
        final_score=final_score,
    )


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """
    Query using the ReAct agent with tool access.

    The agent can use semantic_search, keyword_search, list_documents, and
    read_document to answer questions about the knowledge base.
    """
    request_id = str(uuid.uuid4())
    started = time.perf_counter()

    result = await agent.ainvoke({"messages": [HumanMessage(content=request.question)]})
    content = result["messages"][-1].content

    used_keyword_search = any(
        isinstance(message, AIMessage)
        and any(call["name"] == "keyword_search" for call in message.tool_calls)
        for message in result["messages"]
    )

    top_hits = sorted(result["hits"].values(), key=lambda hit: hit["similarity"], reverse=True)[:request.top_k]
    similarity_scores = [hit["similarity"] for hit in top_hits]
    breakdown = _confidence_breakdown(similarity_scores, used_keyword_search)

    if isinstance(content, str):
        final_message = content
    elif isinstance(content, list):
        final_message = "".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and "text" in block
        )
    else:
        final_message = str(content)

    return QueryResponse(
        answer=final_message,
        sources=[
            SourceHit(
                document_id=hit["document_id"],
                chunk_id=hit["chunk_id"],
                score=hit["similarity"],
                excerpt=hit["excerpt"],
            )
            for hit in top_hits
        ],
        confidence_score=breakdown.final_score,
        confidence_breakdown=breakdown,
        similarity_scores=similarity_scores,
        query=request.question,
        timestamp=datetime.now(),
        explain_mode=request.explain_like_10,
        metadata=QueryMetadata(
            model=settings.BEDROCK_LLM_MODEL_ID,
            retrieval_strategy="semantic_search+keyword_search" if used_keyword_search else "semantic_search",
            request_id=request_id,
            latency_ms=int((time.perf_counter() - started) * 1000),
        ),
    )


@router.get("/count")
async def count_chunks():
    """Count the number of chunks in the knowledge base."""
    async with engine.connect() as conn:
        result = await conn.execute(sql_text("SELECT COUNT(*) FROM chunk"))
        return {"count": result.scalar_one()}
