from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import RetryPolicy
from .state import AgentState
from .nodes import responder
from .tools import TOOLS

# Retry any node that fails - throttling, timeouts, dropped connections.
RETRY = RetryPolicy(max_attempts=3)


def build_react_agent():
    """Build a ReAct (Reason + Act) agent using LangGraph with tool calling."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("responder", responder, retry_policy=RETRY)
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True), retry_policy=RETRY)

    # Define edges
    graph.add_edge(START, "responder")
    graph.add_edge("tools", "responder")

    # Compile with strict mode to enforce tool schema validation
    return graph.compile()


agent = build_react_agent()
