"""
Answering questions over the knowledge base via the ReAct agent, and
knowledge-base-wide chunk counting.
"""

from datetime import datetime

from langchain_core.messages import HumanMessage
from sqlalchemy import func, select

from models import Chunk
from infrastructure.db import db_session
from schemas.api.query import ConfidenceBreakdown, QueryResponse, SourceInfo
from services.agent import agent


def _confidence_breakdown(scores: list[float], keyword_score: float) -> ConfidenceBreakdown:
    if not scores:
        return ConfidenceBreakdown(
            best_similarity=0.0, avg_similarity=0.0, consistency=0.0,
            keyword_match=0.0, final_score=0.0,
        )

    best = max(scores)
    avg = sum(scores) / len(scores)
    consistency = round(1.0 - (best - min(scores)), 3)
    keyword_match = keyword_score
    final_score = round(0.5 * best + 0.3 * avg + 0.1 * consistency + 0.1 * keyword_match, 3)

    return ConfidenceBreakdown(
        best_similarity=round(best, 3),
        avg_similarity=round(avg, 3),
        consistency=consistency,
        keyword_match=keyword_match,
        final_score=final_score,
    )


async def answer_question(question: str, top_k: int, explain_like_10: bool) -> QueryResponse:
    """Run the ReAct agent over the knowledge base and build a grounded, cited answer.

    The agent can use semantic_search, keyword_search, list_documents, and
    read_document to answer questions about the knowledge base.
    """
    result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    content = result["messages"][-1].content

    keyword_matches = result["keyword_matches"]
    keyword_score = max(keyword_matches.values(), default=0.0)

    top_hits = sorted(result["semantic_matches"].values(), key=lambda hit: hit["similarity"], reverse=True)[:top_k]
    similarity_scores = [hit["similarity"] for hit in top_hits]
    breakdown = _confidence_breakdown(similarity_scores, keyword_score)

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
            SourceInfo(
                source=hit["source"],
                chunk_index=hit["chunk_index"],
                file_path=hit["file_path"],
                content_preview=hit["content_preview"],
                similarity_score=hit["similarity"],
            )
            for hit in top_hits
        ],
        confidence_score=breakdown.final_score,
        confidence_breakdown=breakdown,
        similarity_scores=similarity_scores,
        query=question,
        timestamp=datetime.now(),
        explain_mode=explain_like_10,
    )


async def count_chunks() -> int:
    """Count the number of chunks in the knowledge base."""
    async with db_session() as session:
        result = await session.execute(select(func.count()).select_from(Chunk))
        return result.scalar_one()
