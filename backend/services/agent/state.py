from typing import Annotated

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field




class AgentState(BaseModel):
    """Agent state for tool-using agent."""
    messages: Annotated[list[BaseMessage], add_messages]