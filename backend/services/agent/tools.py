from pathlib import Path
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from core.config import settings

uploads_path = Path(settings.UPLOAD_DIR)


class ListFilesInput(BaseModel):
    prefix: str = Field(default="", description="Subdirectory within uploads to list")


@tool("list_files", args_schema=ListFilesInput)
def list_files(prefix: str = "") -> str:
    """List files in the uploads directory."""
    target = uploads_path / prefix if prefix else uploads_path
    if not target.exists():
        return ""
    return "\n".join(f.name for f in target.iterdir() if f.is_file())


TOOLS = [list_files]
