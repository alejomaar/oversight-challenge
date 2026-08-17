from typing import Annotated
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class AgentState(BaseModel):
    """Agent state for tool-using agent."""
    messages: Annotated[list[BaseMessage], add_messages]
