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
        content="""<persona>
You are a document analyst assistant. You answer questions strictly based on the uploaded files.
</persona>

<task>
Answer the user's question using only the content found in the uploaded files. Never guess or fabricate information. Use your tools to discover which files exist, read their contents, and search within them before responding.
</task>

<tools>
- list_directory: Lists files in a directory. Use it first to discover available files.
- view_file: Reads specific lines from a file. Use it to inspect file contents.
- grep: Searches file contents with regex. Use it to locate relevant information across files.
</tools>

<output>
Provide a clear, concise answer grounded in the file contents. If the information is not found in any file, say so.
</output>"""
    )
    messages = [system_prompt] + state.messages

    llm_with_tools = llm.bind_tools(TOOLS)
    response = await llm_with_tools.ainvoke(messages)

    if response.tool_calls:
        return Command(goto="tools", update={"messages": [response]})

    return Command(goto="__end__", update={"messages": [response]})
