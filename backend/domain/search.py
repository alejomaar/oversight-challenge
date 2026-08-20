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


# A retrieval signal at or below this is noise, not evidence.
SCORE_THRESHOLD = 0.2


def _fuse_matches(
    semantic_matches: dict[str, dict],
    keyword_matches: dict[str, dict],
    top_k: int,
) -> list[dict]:
    """Rank chunks by the combined retrieval score, keyed by chunk_id.

    Both signals are treated as independent evidence that a chunk is relevant:
    `1 - (1 - keyword)(1 - semantic)`. A chunk found by both scores higher than
    it would under either alone, and a chunk found by only one keeps that one's
    score. A signal at or below SCORE_THRESHOLD is too weak to count as
    evidence, and a chunk left with no evidence at all is dropped.
    """
    fused = []
    for chunk_id in semantic_matches.keys() | keyword_matches.keys():
        semantic = semantic_matches.get(chunk_id)
        keyword = keyword_matches.get(chunk_id)
        hit = semantic or keyword

        similarity = semantic["similarity"] if semantic else 0.0
        keyword_score = keyword["keyword_score"] if keyword else 0.0

        if similarity <= SCORE_THRESHOLD:
            similarity = 0.0
        if keyword_score <= SCORE_THRESHOLD:
            keyword_score = 0.0
        if not similarity and not keyword_score:
            continue

        fused.append({
            "source": hit["source"],
            "chunk_index": hit["chunk_index"],
            "file_path": hit["file_path"],
            "content_preview": hit["content_preview"],
            "keyword_score": keyword_score,
            "similarity": round(1 - (1 - keyword_score) * (1 - similarity), 3),
        })

    fused.sort(key=lambda hit: hit["similarity"], reverse=True)
    return fused[:top_k]


def _confidence_breakdown(scores: list[float], keyword_score: float) -> ConfidenceBreakdown:
    if not scores:
        return ConfidenceBreakdown(
            best_similarity=0.0, avg_similarity=0.0, consistency=0.0,
            keyword_match=0.0, final_score=0.0,
        )

    best = max(scores)
    avg = sum(scores) / len(scores)
    consistency = round(1.0 - (best - min(scores)), 3)

    return ConfidenceBreakdown(
        best_similarity=round(best, 3),
        avg_similarity=round(avg, 3),
        consistency=consistency,
        keyword_match=keyword_score,
        # The combined score already carries both signals, so confidence is just
        # its average over the top-k chunks.
        final_score=round(avg, 3),
    )


async def answer_question(question: str, top_k: int, explain_like_10: bool) -> QueryResponse:
    """Run the ReAct agent over the knowledge base and build a grounded, cited answer.

    The agent can use semantic_search, keyword_search, list_documents, and
    read_document to answer questions about the knowledge base.
    """
    result = await agent.ainvoke({"messages": [HumanMessage(content=question)]})
    content = result["messages"][-1].content

    top_hits = _fuse_matches(result["semantic_matches"], result["keyword_matches"], top_k)
    similarity_scores = [hit["similarity"] for hit in top_hits]
    keyword_score = max((hit["keyword_score"] for hit in top_hits), default=0.0)
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
