"""
Query endpoints for RAG system.
"""

from fastapi import APIRouter

from domain.search import answer_question, count_chunks
from schemas.api.query import QueryRequest, QueryResponse

router = APIRouter()


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """
    Query using the ReAct agent with tool access.
    """
    return await answer_question(request.question, request.top_k, request.explain_like_10)


@router.get("/count")
async def count_chunks_route():
    """Count the number of chunks in the knowledge base."""
    return {"count": await count_chunks()}
