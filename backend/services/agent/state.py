from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field


def merge_hits(existing: dict[str, dict], new: dict[str, dict]) -> dict[str, dict]:
    """Merge chunk_id -> hit maps, keeping the higher-similarity version on repeat matches."""
    merged = dict(existing)
    for chunk_id, hit in new.items():
        if chunk_id not in merged or hit["similarity"] > merged[chunk_id]["similarity"]:
            merged[chunk_id] = hit
    return merged


class AgentState(BaseModel):
    """Agent state for tool-using agent."""
    messages: Annotated[list[BaseMessage], add_messages]
    hits: Annotated[dict[str, dict], merge_hits] = Field(default_factory=dict)