from typing import Literal
from langchain_core.messages import SystemMessage
from langgraph.types import Command
from langchain_aws import ChatBedrockConverse
from core.config import settings
from .state import AgentState
from .tools import TOOLS


llm = ChatBedrockConverse(
    model_id=settings.BEDROCK_LLM_MODEL_ID,
    region_name=settings.AWS_REGION,
    max_tokens=settings.MAX_TOKENS,
    temperature=settings.TEMPERATURE,
)


async def responder(state: AgentState) -> Command[Literal["tools", "__end__"]]:
    """Responder node that decides whether to use tools or end."""
    system_prompt = SystemMessage(
        content="You are a helpful assistant. Always use the list_files tool to answer questions about files. Never guess or reason about files without calling the tool first."
    )
    messages = [system_prompt] + state.messages

    llm_with_tools = llm.bind_tools(TOOLS)
    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        return Command(goto="tools", update={"messages": [response]})

    return Command(goto="__end__", update={"messages": [response]})
