"""
Query endpoints for RAG system.
"""

from fastapi import APIRouter

from domain.search import answer_question, count_chunks
from schemas.api.query import QueryRequest, QueryResponse

router = APIRouter()

# Bedrock throttles the agent's model calls under load; a retry usually lands.
QUERY_ATTEMPTS = 3


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """
    Query using the ReAct agent with tool access.
    """
    for attempt in range(QUERY_ATTEMPTS):
        try:
            return await answer_question(
                request.question, request.top_k, request.explain_like_10
            )
        except Exception:
            # The last failure is the one worth seeing - re-raise it as is.
            if attempt == QUERY_ATTEMPTS - 1:
                raise


@router.get("/count")
async def count_chunks_route():
    """Count the number of chunks in the knowledge base."""
    return {"count": await count_chunks()}
