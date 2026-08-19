"""
Entrypoint for the Knowledge Base AI Agent Streamlit client.

This is a thin client: all retrieval, embedding, and generation happen
behind the AWS API (Lambda + Bedrock + Postgres/pgvector). See api_client.py
for the HTTP layer and ui.py for rendering — nothing here touches documents
or a vectorstore directly.
"""

import streamlit as st

from constants import CSS_STYLE
from ui import render_app

st.set_page_config(
    page_title="Knowledge Base AI Agent",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        'Get Help': None,
        'Report a bug': None,
        'About': None
    }
)

st.markdown(CSS_STYLE, unsafe_allow_html=True)


render_app()
