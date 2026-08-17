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
def view_file(path: str, start_line: int, end_line: int) -> str:
    """View file contents within a line range (max 100 lines).

    Args:
        path: File path relative to uploads directory.
        start_line: First line number to display.
        end_line: Last line number to display.
    """
    if end_line - start_line > 100:
        raise ValueError("Range exceeds 100 lines. Use a smaller range.")
    file = uploads_path / path
    result = subprocess.run(
        ["sed", "-n", f"{start_line},{end_line}p", str(file)],
        capture_output=True, text=True
    )
    return result.stdout or result.stderr


@tool
def grep(pattern: str, path: str = "") -> str:
    """Search file contents using grep regex (always lowercase). Returns file path and line number only.

    Args:
        pattern: Regex pattern to search for (lowercase).
        path: Directory to search in, relative to uploads. Defaults to uploads root.
    """
    target = uploads_path / path if path else uploads_path
    result = subprocess.run(
        f'grep -rin "{pattern}" "{target}" | cut -d: -f1,2',
        shell=True, capture_output=True, text=True
    )
    return result.stdout or result.stderr


TOOLS = [list_directory, view_file, grep]
