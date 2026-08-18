import logging
from typing import Literal

from core.config import settings
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langgraph.types import Command
import pprint
from .state import AgentState
from .tools import TOOLS

logger = logging.getLogger(__name__)


llm = ChatBedrockConverse(
    model_id=settings.BEDROCK_LLM_MODEL_ID,
    region_name=settings.AWS_REGION,
    max_tokens=settings.MAX_TOKENS,
    temperature=settings.TEMPERATURE,
)


async def responder(state: AgentState) -> Command[Literal["tools", "__end__"]]:
    """Responder node that decides whether to use tools or end."""
    system_prompt = SystemMessage(content="""<persona>
You are a document analyst assistant. You answer questions strictly based on the uploaded files.
</persona>

<task>
Answer the user's question using only the content found in the uploaded files. Never guess or fabricate information. Use your tools to discover which files exist, read their contents, and search within them before responding.
</task>

<tools>
- semantic_search: Searches the knowledge base for relevant information. ALWAYS use this tool first for knowledge-base questions. Prefer it over all other tools. Use the other tools only when semantic_search does not provide enough information or when exact file-level inspection is required.
- list_directory: Lists files in a directory. Use it first to discover available files.
- view_file: Reads specific lines from a file. Use it to inspect file contents.
- grep: Searches file contents with regex. Use it to locate relevant information across files.
</tools>

<output>
When you have enough information, provide a grounded answer with citations and a confidence score.
Do not mention citations in the answer itself. Include only the exact S3 object keys actually used to form the answer.
If the information is not found, say so in the answer, provide no citations, and use a low confidence score.
</output>""")
    messages = [system_prompt] + state.messages

    llm_with_tools = llm.bind_tools(TOOLS)
    response = await llm_with_tools.ainvoke(messages)
    pprint.pprint(response)
    if response.tool_calls:
        return Command(
            goto="tools",
            update={"messages": [response]},
        )

    return Command(
        goto="__end__",
        update={
            "messages": [response],
        },
    )
