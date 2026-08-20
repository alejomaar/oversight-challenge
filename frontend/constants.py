"""Static constants for the Streamlit client: defaults and CSS."""

DEFAULT_API_BASE_URL = "http://localhost:8000"

CSS_STYLE = """
    <style>
    :root {
        --kb-bg: #161a2e;
        --kb-accent: #7c8cf8;
        --kb-line: rgba(124, 140, 248, 0.28);
        --kb-surface: rgba(255, 255, 255, 0.05);
        --kb-text: #e7eaf6;
        --kb-muted: rgba(231, 234, 246, 0.68);
    }

    /* Hide Streamlit chrome, but keep the header so the sidebar toggle stays
       reachable on narrow screens. */
    #MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {
        display: none !important;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    .stApp {
        background: linear-gradient(160deg, #1a1a2e 0%, #16213e 100%) fixed;
        color: var(--kb-text);
    }

    /* Readable measure, centred, with room for the floating chat bar. */
    [data-testid="stMain"] .block-container {
        background: transparent;
        max-width: 58rem;
        margin: 0 auto;
        padding: 1.5rem 1.5rem 8rem;
    }

    /* Bottom chat bar: the default opaque slab is replaced by a fade so the
       conversation scrolls under it instead of being cut off by a black band. */
    [data-testid="stBottom"],
    [data-testid="stBottom"] > div {
        background: transparent !important;
    }

    [data-testid="stBottomBlockContainer"] {
        max-width: 58rem;
        margin: 0 auto;
        padding: 1.5rem 1.5rem 1.25rem;
        background: linear-gradient(to top, var(--kb-bg) 55%, rgba(22, 26, 46, 0));
    }

    [data-testid="stChatInput"] {
        background: rgba(255, 255, 255, 0.07) !important;
        border: 1px solid var(--kb-line) !important;
        border-radius: 14px !important;
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.35);
    }

    [data-testid="stChatInput"]:focus-within {
        border-color: var(--kb-accent) !important;
    }

    [data-testid="stChatInput"] textarea {
        background: transparent !important;
        color: var(--kb-text) !important;
    }

    [data-testid="stChatInput"] textarea::placeholder {
        color: rgba(231, 234, 246, 0.45) !important;
    }

    [data-testid="stSidebar"] {
        background: rgba(18, 20, 38, 0.92);
        border-right: 1px solid var(--kb-line);
    }

    [data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 20rem;
        max-width: 24rem;
    }

    [data-testid="stSidebar"] .block-container,
    [data-testid="stSidebar"] > div {
        padding-top: 1rem;
    }

    /* Sidebar rows stay legible in a narrow column. */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 0.35rem;
        align-items: center;
    }

    [data-testid="stSidebar"] a {
        word-break: break-word;
    }

    [data-testid="stSidebar"] hr {
        margin: 0.75rem 0;
        border-color: var(--kb-line);
    }

    @keyframes smoothFade {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    .smooth-fade { animation: smoothFade 0.3s ease-in; }

    .navbar-title {
        font-size: clamp(1.25rem, 3vw, 1.6rem);
        font-weight: 700;
        line-height: 1.3;
        margin-bottom: 1.25rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--kb-line);
        background: linear-gradient(135deg, #8f9bff 0%, #b98cf0 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    .hero {
        padding: clamp(1.25rem, 4vw, 2.25rem);
        background: var(--kb-surface);
        border: 1px solid var(--kb-line);
        border-radius: 16px;
        margin-bottom: 1.5rem;
        text-align: center;
    }

    .hero h1 {
        font-size: clamp(1.5rem, 4vw, 2.25rem);
        line-height: 1.2;
        margin: 0 0 0.75rem;
        color: var(--kb-text);
    }

    .hero p {
        margin: 0 auto;
        max-width: 38rem;
        font-size: 1rem;
        color: var(--kb-muted);
    }

    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.6rem 1.5rem;
        font-weight: 600;
        box-shadow: 0 2px 8px rgba(102, 126, 234, 0.3);
    }

    .stButton > button[kind="primary"]:hover {
        box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
        transform: translateY(-2px);
    }

    .stButton > button[kind="secondary"] {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
        border: 1px solid rgba(102, 126, 234, 0.3) !important;
    }

    .doc-preview-content {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 8px;
        padding: 1.5rem;
        margin-top: 1rem;
        border: 1px solid rgba(102, 126, 234, 0.3);
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
    }

    .doc-preview-title {
        font-size: 1.1rem;
        font-weight: 600;
        color: #ffffff;
        margin-bottom: 1rem;
        padding-bottom: 0.5rem;
        border-bottom: 1px solid rgba(102, 126, 234, 0.3);
    }

    .stButton > button {
        color: #ffffff !important;
        border-radius: 8px;
        font-weight: 500;
        transition: all 0.3s;
    }

    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }

    .stFileUploader [data-testid="stFileUploaderDropzone"] {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px dashed var(--kb-accent) !important;
        border-radius: 12px !important;
        padding: 1rem !important;
    }

    h1, h2, h3, h4, h5, h6 {
        color: var(--kb-text);
    }

    a, a:visited {
        color: var(--kb-accent);
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.04) !important;
        border: 1px solid rgba(255, 255, 255, 0.06);
        border-radius: 12px;
    }

    .stSuccess {
        background: rgba(40, 167, 69, 0.2);
        border-left: 4px solid #28a745;
        color: #90ee90;
        padding: 1rem;
        border-radius: 6px;
    }

    .stError {
        background: rgba(220, 53, 69, 0.2);
        border-left: 4px solid #dc3545;
        color: #ff6b6b;
        padding: 1rem;
        border-radius: 6px;
    }

    .stInfo {
        background: rgba(33, 150, 243, 0.2);
        border-left: 4px solid #2196F3;
        color: #81d4fa;
    }

    .stWarning {
        background: rgba(255, 193, 7, 0.2);
        border-left: 4px solid #ffc107;
        color: #ffd54f;
    }

    .confidence-score {
        margin-top: 1rem;
        padding: 0.75rem 1rem;
        background: rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        border-left: 4px solid;
        font-size: 0.9rem;
    }

    .feature-card {
        height: 100%;
        padding: 1.25rem;
        background: rgba(124, 140, 248, 0.12);
        border-radius: 12px;
        border: 1px solid var(--kb-line);
        transition: transform 0.2s, border-color 0.2s;
    }

    .feature-card:hover {
        transform: translateY(-3px);
        border-color: rgba(124, 140, 248, 0.6);
    }

    .feature-card h3 {
        font-size: 1rem;
        font-weight: 600;
        margin: 0 0 0.5rem;
    }

    .feature-card p {
        margin: 0;
        font-size: 0.9rem;
        line-height: 1.5;
        color: var(--kb-muted);
    }

    /* Columns are flex rows by default and squeeze into unreadable slivers on
       small viewports — stack them instead. */
    @media (max-width: 900px) {
        [data-testid="stMain"] [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap;
            gap: 0.75rem;
        }

        [data-testid="stMain"] [data-testid="stColumn"] {
            flex: 1 1 100% !important;
            min-width: 100% !important;
        }

        [data-testid="stMain"] .block-container {
            padding: 1rem 1rem 7rem;
        }

        [data-testid="stBottomBlockContainer"] {
            padding: 1rem 1rem 0.75rem;
        }

        [data-testid="stSidebar"][aria-expanded="true"] {
            min-width: 17rem;
        }
    }
    </style>
"""
