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
    for file_path in UPLOADS_DIR.iterdir():
        if file_path.is_file() and file_path.stem == file_id:
            stat = file_path.stat()
            return FileInfo(
                file_id=file_path.stem,
                filename=file_path.name,
                file_size=stat.st_size,
                file_type=file_path.suffix,
                s3_key=file_path.name,
                uploaded_at=datetime.fromtimestamp(stat.st_mtime),
                processed=False,
                chunk_count=None
            )

    raise HTTPException(status_code=404, detail="File not found")


@router.post("/", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a file to the filesystem.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    content = await file.read()
    size = len(content)

    if size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large (max {settings.MAX_FILE_SIZE / 1024 / 1024}MB)"
        )

    file_extension = Path(file.filename).suffix.lower()
    allowed = settings.ALLOWED_EXTENSIONS.split(',')
    if file_extension not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    file_id = str(uuid4())
    file_path = UPLOADS_DIR / file.filename
    file_path.write_bytes(content)

    return FileUploadResponse(
        file_id=file_id,
        filename=file.filename,
        file_size=size,
        file_type=file_extension,
        s3_key=file.filename,
        status="uploaded",
        message=f"File {file.filename} uploaded successfully",
        uploaded_at=datetime.now()
    )


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(file_id: str):
    """
    Delete a file from the filesystem.
    """
    for file_path in UPLOADS_DIR.iterdir():
        if file_path.is_file() and file_path.stem == file_id:
            file_path.unlink()
            return FileDeleteResponse(
                file_id=file_id,
                filename=file_path.name,
                deleted=True,
                message="File deleted successfully"
            )

    raise HTTPException(status_code=404, detail="File not found")

