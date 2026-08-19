"""Streamlit UI rendering: session state, layout, and widgets.

Pulls data through api_client — contains no retrieval/generation logic
itself, only presentation and the session-state plumbing Streamlit needs.
"""

import streamlit as st

from api_client import API_BASE_URL, API_TOKEN, api_get, api_post, api_delete, api_upload_file


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def initialize_session_state():
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    if 'top_k' not in st.session_state:
        st.session_state.top_k = 5
    if 'selected_doc' not in st.session_state:
        st.session_state.selected_doc = None


def render_navbar():
    st.markdown('<div class="navbar-title">Welcome to Your Knowledgebase Agent</div>', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------


def render_connection_section():
    st.markdown("### 🔌 Connection")
    st.caption(f"API: `{API_BASE_URL}`")
    if API_TOKEN:
        st.caption(f"Token: configured (…{API_TOKEN[-4:]})")
    else:
        st.caption("Token: not set")
    st.caption(
        "Token auth is enforced at API Gateway (API key + usage plan) in AWS. "
        "Running against a local `uvicorn` backend bypasses it entirely — "
        "there is no gateway in front to check the key."
    )

    if st.button("Check connection", use_container_width=True):
        ok, status, data = api_get("/api/health/")
        if ok:
            st.success(f"✅ Reachable — {data.get('status', 'unknown')}")
        else:
            st.error(f"⚠️ {data} (status: {status})")


def render_upload_widget():
    st.markdown("### ⬆️ Upload")
    uploaded_files = st.file_uploader(
        "Upload Documents",
        type=['pdf', 'docx', 'doc', 'txt'],
        accept_multiple_files=True,
        label_visibility="visible",
    )
    if uploaded_files and st.button("Ingest", use_container_width=True):
        any_ok = False
        for f in uploaded_files:
            with st.spinner(f"Ingesting {f.name}..."):
                ok, status, data = api_upload_file(
                    "/api/upload/", f.name, f.getvalue(), f.type or "application/octet-stream"
                )
            if ok:
                any_ok = True
                st.success(f"✅ {f.name}: {data.get('message', 'indexed')}")
            else:
                detail = data.get("detail", data) if isinstance(data, dict) else data
                st.error(f"⚠️ {f.name} (status {status}): {detail}")
        if any_ok:
            st.rerun()


def render_kb_file_list():
    st.markdown("### 📚 Knowledge Base Files")

    ok, status, data = api_get("/api/files/")
    if not ok:
        st.warning(f"Could not load file list: {data}")
        return []

    files = data.get("files", [])
    if not files:
        st.info("No files in the knowledge base yet.")
        return []

    for idx, f in enumerate(files):
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button(f"📄 {f['filename']}", key=f"doc_{f['file_id']}", use_container_width=True):
                st.session_state.selected_doc = f
                st.rerun()
            st.caption(format_file_size(f.get("file_size", 0)))
        with col2:
            if st.button("🗑️", key=f"delete_{idx}", help=f"Delete {f['filename']}"):
                ok, status, result = api_delete(f"/api/files/{f['file_id']}")
                if ok:
                    st.success(f"Deleted {f['filename']}")
                    if st.session_state.selected_doc and st.session_state.selected_doc.get("file_id") == f["file_id"]:
                        st.session_state.selected_doc = None
                    st.rerun()
                else:
                    st.error(f"Delete failed: {result}")
        st.markdown("---")

    return files


def render_doc_preview():
    doc = st.session_state.selected_doc
    if not doc:
        return

    st.markdown('<div class="doc-preview-content">', unsafe_allow_html=True)
    st.markdown(f'<div class="doc-preview-title">📄 {doc["filename"]}</div>', unsafe_allow_html=True)
    st.caption(
        "The API doesn't expose a document-content endpoint, so this shows metadata only, "
        "not the extracted text."
    )
    st.markdown(f"- **Type:** {doc.get('file_type', '—')}")
    st.markdown(f"- **Size:** {format_file_size(doc.get('file_size', 0))}")
    st.markdown(f"- **Uploaded:** {doc.get('uploaded_at', '—')}")
    st.markdown(f"- **Processed:** {'Yes' if doc.get('processed') else 'No'}")
    if doc.get("chunk_count") is not None:
        st.markdown(f"- **Chunks:** {doc['chunk_count']}")
    st.markdown("</div>", unsafe_allow_html=True)


def render_sidebar():
    with st.sidebar:
        render_connection_section()
        st.markdown("---")
        render_upload_widget()
        st.markdown("---")
        files = render_kb_file_list()
        render_doc_preview()
        st.markdown("---")

        st.markdown("### ⚙️ Settings")
        st.session_state.top_k = st.slider(
            "Chunks to retrieve (top_k)",
            min_value=1, max_value=20, value=st.session_state.top_k,
        )

        st.markdown("---")
        st.markdown("### 📊 Status")
        st.metric("📄 Documents", len(files))
        st.metric("💬 Messages", len(st.session_state.chat_history))


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


def display_chat_message(role: str, content: str):
    with st.chat_message(role):
        st.markdown(content)


def render_confidence(confidence_score: float):
    confidence_percent = int(confidence_score * 100)
    color = "#28a745" if confidence_score > 0.7 else "#ffc107" if confidence_score > 0.4 else "#dc3545"
    st.markdown(
        f'<div class="confidence-score" style="border-left-color: {color};">'
        f'<strong>Confidence Score:</strong> <span style="color: {color};">{confidence_percent}%</span> '
        f'(from the API response)</div>',
        unsafe_allow_html=True,
    )


def render_sources(sources: list):
    st.markdown("---")
    st.markdown("### 📚 Sources")
    if not sources:
        st.info("No sources returned by the API for this answer.")
        return
    for source in sources:
        st.markdown(f"**{source['document_id']}** · `{source['chunk_id']}` · score {source['score']:.2f}")
        st.caption(source["excerpt"])


def render_metadata(metadata: dict):
    if not metadata:
        return
    st.caption(
        f"model: `{metadata.get('model', '—')}` · "
        f"retrieval: `{metadata.get('retrieval_strategy', '—')}` · "
        f"latency: {metadata.get('latency_ms', '—')} ms · "
        f"request_id: `{metadata.get('request_id', '—')}`"
    )


def ask_and_render(question: str):
    display_chat_message("user", question)
    st.session_state.chat_history.append({"role": "user", "content": question})

    with st.spinner("🤔 Asking the knowledge base agent..."):
        ok, status, data = api_post("/api/query/", {
            "question": question,
            "top_k": st.session_state.top_k,
        })

    with st.chat_message("assistant"):
        if not ok:
            st.error(f"Request failed (status: {status}): {data}")
            answer_text = f"⚠️ Request failed: {data}"
        else:
            answer_text = data.get("answer", "")
            st.markdown(f'<div class="smooth-fade">{answer_text}</div>', unsafe_allow_html=True)
            render_confidence(data.get("confidence_score", 0.0))
            render_sources(data.get("sources", []))
            render_metadata(data.get("metadata", {}))
            with st.expander("Raw response JSON", expanded=False):
                st.json(data)

    st.session_state.chat_history.append({"role": "assistant", "content": answer_text})


def render_chat_interface():
    for message in st.session_state.chat_history:
        display_chat_message(message["role"], message["content"])

    user_question = st.chat_input("Ask a question about the knowledge base...")
    if user_question:
        ask_and_render(user_question)
        st.rerun()


def render_welcome_page():
    st.markdown("""
    <div style="padding: 2rem; background: rgba(255, 255, 255, 0.05); border-radius: 16px; border: 1px solid rgba(102, 126, 234, 0.3); margin-bottom: 2rem;">
        <h1 style="text-align: center; color: #ffffff; margin-bottom: 1rem;">Welcome to Your Knowledgebase Agent</h1>
        <p style="text-align: center; color: rgba(255, 255, 255, 0.8); font-size: 1.1rem; margin-bottom: 2rem;">
            Ask a question below — the AWS-hosted API retrieves context from the knowledge base
            and generates a grounded answer.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color: #ffffff;">🚫 No Hallucination</h3>
            <p style="color: rgba(255, 255, 255, 0.8);">Answers are grounded in the retrieved knowledge base context.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color: #ffffff;">🔌 Thin Client</h3>
            <p style="color: rgba(255, 255, 255, 0.8);">This app only calls the AWS API — retrieval and generation run entirely server-side.</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="feature-card">
            <h3 style="color: #ffffff;">✅ Confidence</h3>
            <p style="color: rgba(255, 255, 255, 0.8);">Every answer includes the confidence score returned by the API.</p>
        </div>
        """, unsafe_allow_html=True)


def render_app():
    initialize_session_state()
    render_navbar()
    render_sidebar()

    if not st.session_state.chat_history:
        render_welcome_page()
    render_chat_interface()
