"""
File management endpoints.
"""

from fastapi import APIRouter, HTTPException, File, UploadFile
from pathlib import Path
from datetime import datetime
from uuid import uuid4

from models.file import FileListResponse, FileInfo, FileDeleteResponse, FileUploadResponse
from core.config import settings

router = APIRouter()
UPLOADS_DIR = Path(settings.UPLOAD_DIR)


@router.get("/", response_model=FileListResponse)
async def list_files(skip: int = 0, limit: int = 100):
    """
    List all uploaded files with pagination.
    """
    files = list(UPLOADS_DIR.iterdir())
    paginated_files = files[skip : skip + limit]

    file_infos = []
    for file_path in paginated_files:
        if file_path.is_file():
            stat = file_path.stat()
            file_infos.append(FileInfo(
                file_id=file_path.stem,
                filename=file_path.name,
                file_size=stat.st_size,
                file_type=file_path.suffix,
                s3_key=file_path.name,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime),
                processed=False,
                chunk_count=None
            ))

    return FileListResponse(files=file_infos, total=len(files))


@router.get("/{file_id}", response_model=FileInfo)
async def get_file(file_id: str):
    """
    Get file information by ID.
    """
    uploads_dir = UPLOADS_DIR.resolve()
    file_path = (uploads_dir / file_id).resolve()

    if not file_path.is_relative_to(uploads_dir) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    stat = file_path.stat()
    return FileInfo(
        file_id=file_id,
        filename=file_path.name,
        file_size=stat.st_size,
        file_type=file_path.suffix,
        s3_key=file_id,
        uploaded_at=datetime.fromtimestamp(stat.st_mtime),
        processed=False,
        chunk_count=None
    )




@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(file_id: str):
    """
    Delete a file from the filesystem.
    """
    uploads_dir = UPLOADS_DIR.resolve()
    file_path = (uploads_dir / file_id).resolve()

    if not file_path.is_relative_to(uploads_dir) or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    file_path.unlink()
    return FileDeleteResponse(
        file_id=file_id,
        filename=file_path.name,
        deleted=True,
        message="File deleted successfully"
    )
