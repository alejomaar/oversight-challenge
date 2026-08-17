import subprocess
from pathlib import Path
from langchain_core.tools import tool
from core.config import settings

uploads_path = Path(settings.UPLOAD_DIR)


@tool
def list_directory(path: str = "") -> str:
    """List files in a directory. Defaults to the uploads directory."""
    target = uploads_path / path if path else uploads_path
    result = subprocess.run(["ls", str(target)], capture_output=True, text=True)
    return result.stdout or result.stderr


@tool
def view_file(path: str, view_range: list[int]) -> str:
    """View file contents within a line range.

    Args:
        path: File path relative to uploads directory.
        view_range: Array with start and end line numbers, e.g. [1, 20].
    """
    file = uploads_path / path
    start, end = view_range[0], view_range[1]
    result = subprocess.run(
        ["sed", "-n", f"{start},{end}p", str(file)],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr


@tool
def grep(pattern: str, path: str = "") -> str:
    """Search file contents using grep regex (always lowercase). Returns full file path and matching line.

    Args:
        pattern: Regex pattern to search for (lowercase).
        path: Directory to search in, relative to uploads. Defaults to uploads root.
    """
    target = uploads_path / path if path else uploads_path
    result = subprocess.run(
        ["grep", "-rinH", str(pattern), str(target)],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr


TOOLS = [list_directory, view_file, grep]
