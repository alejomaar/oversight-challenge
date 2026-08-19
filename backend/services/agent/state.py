from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


def merge_semantic_matches(existing: dict[str, dict], new: dict[str, dict]) -> dict[str, dict]:
    """Merge chunk_id -> hit maps, keeping the higher-similarity version on repeat matches."""
    merged = dict(existing)
    for chunk_id, hit in new.items():
        if chunk_id not in merged or hit["similarity"] > merged[chunk_id]["similarity"]:
            merged[chunk_id] = hit
    return merged


def merge_keyword_matches(existing: dict[str, float], new: dict[str, float]) -> dict[str, float]:
    """Merge document_id -> score maps, keeping the higher score on repeat matches."""
    merged = dict(existing)
    for document_id, score in new.items():
        if document_id not in merged or score > merged[document_id]:
            merged[document_id] = score
    return merged


class AgentState(BaseModel):
    """Agent state for tool-using agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    semantic_matches: Annotated[dict[str, dict], merge_semantic_matches] = Field(default_factory=dict)
    keyword_matches: Annotated[dict[str, float], merge_keyword_matches] = Field(default_factory=dict)
