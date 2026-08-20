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


def get_doc_download(file_id: str) -> dict | None:
    """Name, details, and a fresh presigned URL for one document.

    Resolved on every render rather than cached — the URL is short-lived, and a
    freshly minted one can never be stale.
    """
    ok, _, data = api_get(f"/api/files/{file_id}/download")
    return data if ok else None


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

    # One bordered row per file: name on its own line so long filenames don't
    # squeeze the action buttons into slivers.
    for f in files:
        with st.container(border=True):
            download = get_doc_download(f["file_id"])
            if download:
                st.markdown(f"[📄 {f['filename']}]({download['download_url']})")
            else:
                st.markdown(f"📄 {f['filename']}")
                st.caption("Original file unavailable for download.")
            st.caption(format_file_size(f.get("file_size", 0)))

            col1, col2 = st.columns(2)
            with col1:
                if st.button("ℹ️ Details", key=f"info_{f['file_id']}", use_container_width=True):
                    st.session_state.selected_doc = f
                    st.rerun()
            with col2:
                if st.button("🗑️ Delete", key=f"delete_{f['file_id']}", use_container_width=True):
                    ok, status, result = api_delete(f"/api/files/{f['file_id']}")
                    if ok:
                        st.success(f"Deleted {f['filename']}")
                        if st.session_state.selected_doc and st.session_state.selected_doc.get("file_id") == f["file_id"]:
                            st.session_state.selected_doc = None
                        st.rerun()
                    else:
                        st.error(f"Delete failed: {result}")

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

    download = get_doc_download(doc["file_id"])
    if download:
        st.markdown(f"[⬇️ Download original]({download['download_url']})")
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
        f'(Based on retrieval similarity from uploaded documents)</div>',
        unsafe_allow_html=True,
    )


def render_sources(sources: list):
    st.markdown("---")
    st.markdown("### 📚 Source Information")
    if not sources:
        st.info("No sources returned by the API for this answer.")
        return

    # Each source is one chunk; the expander header names the files they came from.
    file_names = dict.fromkeys(source["source"] for source in sources)

    with st.expander(f"📄 Sources: {', '.join(file_names)}", expanded=False):
        for source in sources:
            st.markdown(f"**From {source['source']}:** {source['content_preview']}")
            st.caption(f"chunk {source['chunk_index']} · similarity {source['similarity_score']:.2f}")
            st.markdown("---")
        st.markdown(f"**Total Sources Used:** {len(sources)}")


def render_assistant_turn(message: dict):
    """Render one assistant turn in full — answer, confidence, and sources.

    Used both for a fresh response and when replaying history, so a turn looks
    the same after a rerun as it did when it arrived.
    """
    with st.chat_message("assistant"):
        response = message.get("response")
        if response is None:
            st.markdown(message["content"])
            return

        st.markdown(f'<div class="smooth-fade">{message["content"]}</div>', unsafe_allow_html=True)
        render_confidence(response.get("confidence_score", 0.0))
        render_sources(response.get("sources", []))
        with st.expander("Raw response JSON", expanded=False):
            st.json(response)


def ask_and_render(question: str):
    display_chat_message("user", question)
    st.session_state.chat_history.append({"role": "user", "content": question})

    with st.spinner("🤔 Asking the knowledge base agent..."):
        ok, status, data = api_post("/api/query/", {
            "question": question,
            "top_k": st.session_state.top_k,
        })

    if ok:
        message = {"role": "assistant", "content": data.get("answer", ""), "response": data}
    else:
        message = {"role": "assistant", "content": f"⚠️ Request failed (status: {status}): {data}"}

    st.session_state.chat_history.append(message)
    render_assistant_turn(message)


def render_chat_interface():
    for message in st.session_state.chat_history:
        if message["role"] == "assistant":
            render_assistant_turn(message)
        else:
            display_chat_message(message["role"], message["content"])

    user_question = st.chat_input("Ask a question about the knowledge base...")
    if user_question:
        ask_and_render(user_question)
        st.rerun()


def render_welcome_page():
    st.markdown("""
    <div class="hero">
        <h1>Ask your documents anything</h1>
        <p>
            The AWS-hosted API retrieves context from the knowledge base
            and generates a grounded answer.
        </p>
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3, gap="medium")
    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3>🚫 No Hallucination</h3>
            <p>Answers are grounded in the retrieved knowledge base context.</p>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3>🔌 Thin Client</h3>
            <p>This app only calls the AWS API — retrieval and generation run entirely server-side.</p>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown("""
        <div class="feature-card">
            <h3>✅ Confidence</h3>
            <p>Every answer includes the confidence score returned by the API.</p>
        </div>
        """, unsafe_allow_html=True)


def render_app():
    initialize_session_state()
    render_navbar()
    render_sidebar()

    if not st.session_state.chat_history:
        render_welcome_page()
    render_chat_interface()
