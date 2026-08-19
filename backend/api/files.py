"""
File management endpoints.
"""

import uuid

from fastapi import APIRouter

from domain.document import delete_document, get_document, list_documents
from schemas.api.files import FileDeleteResponse, FileInfo, FileListResponse

router = APIRouter()


@router.get("/", response_model=FileListResponse)
async def list_files(skip: int = 0, limit: int = 100):
    """
    List all uploaded files with pagination.
    """
    return await list_documents(skip, limit)


@router.get("/{file_id}", response_model=FileInfo)
async def get_file(file_id: uuid.UUID):
    """
    Get file information by document id.
    """
    return await get_document(file_id)


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(file_id: uuid.UUID):
    """
    Delete a document: its original in S3 and its chunks in the knowledge base.
    """
    return await delete_document(file_id)
