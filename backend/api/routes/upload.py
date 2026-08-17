"""
File upload endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException
import uuid
from pathlib import Path
from datetime import datetime

from core.config import settings
from models.file import FileUploadResponse

router = APIRouter()


@router.post("/", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a document file.

    Supports: PDF, DOCX, DOC, TXT
    """
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(settings.ALLOWED_EXTENSIONS)}"
        )

    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )

    file_id = str(uuid.uuid4())
    file_path = Path(settings.UPLOAD_DIR) / file.filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_bytes(file_content)

    return FileUploadResponse(
        file_id=file_id,
        filename=file.filename,
        file_size=len(file_content),
        file_type=file_ext,
        s3_key=file.filename,
        status="success",
        message="File uploaded successfully",
        uploaded_at=datetime.now()
    )


@router.post("/batch")
async def upload_files(files: list[UploadFile] = File(...)):
    """
    Upload multiple files at once.
    """
    results = []
    errors = []

    for file in files:
        try:
            result = await upload_file(file)
            results.append(result.model_dump())
        except HTTPException as e:
            errors.append({
                "filename": file.filename,
                "error": e.detail
            })

    return {
        "successful": results,
        "failed": errors,
        "total": len(files),
        "success_count": len(results),
        "error_count": len(errors)
    }

