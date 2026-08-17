"""
Query endpoints for RAG system.
"""

from fastapi import APIRouter
import logging
from datetime import datetime
from langchain_core.messages import HumanMessage

from models.query import QueryRequest, QueryResponse
from services.agent import agent

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """
    Query using the ReAct agent with tool access.

    The agent can use the list_files tool to answer questions about uploaded documents.
    """
    result = await agent.ainvoke({"messages": [HumanMessage(content=request.question)]})
    final_message = result["messages"][-1].content[-1]["text"]

    return QueryResponse(
        answer=final_message,
        sources=[],
        confidence_score=1.0,
        similarity_scores=[],
        query=request.question,
        timestamp=datetime.now(),
        explain_mode=request.explain_like_10
    )


