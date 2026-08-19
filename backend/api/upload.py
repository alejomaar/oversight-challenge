"""
File upload endpoints.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException

from domain.document import upload_document
from schemas.api.files import FileUploadResponse

router = APIRouter()


@router.post("/", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a document file.
    Pipeline: ingest → transform → index
    """
    content = await file.read()
    return await upload_document(file.filename, content)


@router.post("/batch")
async def upload_files(files: list[UploadFile] = File(...)):
    """
    Upload multiple files at once.
    """
    results = []
    errors = []

    for file in files:
        try:
            content = await file.read()
            result = await upload_document(file.filename, content)
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
