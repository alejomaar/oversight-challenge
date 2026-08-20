"""Static constants for the Streamlit client: defaults and CSS."""

DEFAULT_API_BASE_URL = "http://localhost:8000"

CSS_STYLE = """
    <style>
    /* Hide Streamlit default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}

    /* Dark theme background */
    .stApp {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    }

    /* Main content background - adjust for sidebar */
    .main .block-container {
        background: transparent;
        padding-top: 2rem;
        max-width: 100% !important;
        padding-left: 1rem;
        padding-right: 1rem;
    }

    [data-testid="stSidebar"] {
        background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
        height: 100vh !important;
        overflow-y: auto !important;
    }

    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    [data-testid="stSidebar"][aria-expanded="true"] {
        min-width: 21rem !important;
        max-width: 50% !important;
    }

    [data-testid="stSidebar"] {
        visibility: visible !important;
    }

    [data-testid="stSidebar"] [data-testid="collapsedControl"] {
        display: none !important;
    }

    section[data-testid="stMain"] {
        margin-left: 0 !important;
    }

    .main .block-container {
        width: auto !important;
    }

    .uploaded-file-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        background: rgba(102, 126, 234, 0.2);
        border-radius: 8px;
        border: 1px solid rgba(102, 126, 234, 0.3);
        color: #ffffff;
        font-size: 0.9rem;
    }

    @keyframes smoothSlide {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    .smooth-slide { animation: smoothSlide 0.4s ease-out; }

    @keyframes smoothFade {
        from { opacity: 0; }
        to { opacity: 1; }
    }

    .smooth-fade { animation: smoothFade 0.3s ease-in; }

    .navbar {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 1.25rem 2rem;
        background: rgba(26, 26, 46, 0.9);
        border-bottom: 2px solid rgba(102, 126, 234, 0.3);
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        border-radius: 12px;
    }

    .navbar-title {
        font-size: 1.75rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        color: #ffffff;
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

    .doc-preview {
        background: rgba(255, 255, 255, 0.05);
        border-radius: 12px;
        padding: 1.5rem;
        height: calc(100vh - 200px);
        overflow-y: auto;
        border: 1px solid rgba(102, 126, 234, 0.3);
        backdrop-filter: blur(10px);
    }

    .doc-preview-header {
        font-size: 1.3rem;
        font-weight: 700;
        margin-bottom: 1.5rem;
        color: #ffffff;
        padding-bottom: 0.75rem;
        border-bottom: 2px solid #667eea;
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

    .stFileUploader > div > div {
        background: rgba(255, 255, 255, 0.05) !important;
        border: 2px dashed #667eea !important;
        border-radius: 12px !important;
        padding: 2rem !important;
        backdrop-filter: blur(10px);
    }

    .stFileUploader label {
        color: #ffffff !important;
    }

    h1, h2, h3, h4, h5, h6, p, span, div {
        color: #ffffff !important;
    }

    /* Declared after the blanket white rule so download links stay visible. */
    a, a:visited {
        color: #667eea !important;
        text-decoration: none;
    }

    a:hover {
        text-decoration: underline;
    }

    [data-testid="stChatMessage"] {
        background: rgba(255, 255, 255, 0.05) !important;
    }

    [data-testid="stChatInput"] {
        background: rgba(255, 255, 255, 0.1) !important;
        border: 1px solid rgba(102, 126, 234, 0.3) !important;
        border-radius: 12px !important;
    }

    [data-testid="stChatInput"] textarea {
        background: rgba(255, 255, 255, 0.1) !important;
        color: #ffffff !important;
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

    .file-item {
        padding: 0.75rem;
        margin: 0.5rem 0;
        background: rgba(102, 126, 234, 0.1);
        border-radius: 8px;
        border: 1px solid rgba(102, 126, 234, 0.3);
        transition: all 0.3s;
    }

    .file-item:hover {
        background: rgba(102, 126, 234, 0.2);
        border-color: rgba(102, 126, 234, 0.5);
    }

    .feature-card {
        padding: 1.5rem;
        background: rgba(102, 126, 234, 0.2);
        border-radius: 12px;
        border: 1px solid rgba(102, 126, 234, 0.3);
        transition: all 0.3s;
        height: 100%;
    }

    .feature-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 20px rgba(102, 126, 234, 0.4);
        border-color: rgba(102, 126, 234, 0.6);
    }
    </style>
"""
