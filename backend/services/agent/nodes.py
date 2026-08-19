import logging
from typing import Literal

from core.config import settings
from langchain_aws import ChatBedrockConverse
from langchain_core.messages import SystemMessage
from langgraph.types import Command
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
Answer the user's question using only the content found in the knowledge base. Never guess or fabricate information. Use your tools to discover which documents exist, search them, and read their contents before responding.
</task>

<tools>
- semantic_search: Finds chunks semantically related to a topic or question, with similarity scores. ALWAYS use this first for knowledge-base questions.
- keyword_search: Case-insensitive POSIX regex search over document text. Use it for exact terms, codes, or phrasing that semantic_search may miss.
- list_documents: Lists the documents in the knowledge base with chunk counts. Use it to discover what is available.
- read_document: Reads consecutive chunks of one document in order. Use it to read around a match for fuller context.
</tools>

<output>
When you have enough information, provide a grounded answer with citations and a confidence score.
Do not mention citations in the answer itself. Cite only the exact document_id and chunk_id values actually used to form the answer.
If the information is not found, say so in the answer, provide no citations, and use a low confidence score.
</output>""")
    messages = [system_prompt] + state.messages

    llm_with_tools = llm.bind_tools(TOOLS)
    response = await llm_with_tools.ainvoke(messages)
    logger.info("responder tool_calls=%s", [c["name"] for c in response.tool_calls])

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
