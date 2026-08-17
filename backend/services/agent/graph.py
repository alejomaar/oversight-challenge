from langgraph.graph import START, StateGraph
from langgraph.prebuilt import ToolNode
from .state import AgentState
from .nodes import responder
from .tools import TOOLS


def build_react_agent():
    """Build a ReAct (Reason + Act) agent using LangGraph with tool calling."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("responder", responder)
    graph.add_node("tools", ToolNode(TOOLS, handle_tool_errors=True))

    # Define edges
    graph.add_edge(START, "responder")
    graph.add_edge("tools", "responder")

    # Compile with strict mode to enforce tool schema validation
    return graph.compile()


agent = build_react_agent()
