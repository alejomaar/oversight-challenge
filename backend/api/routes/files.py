"""
File management endpoints.

Originals are listed from S3; chunk counts come from Postgres.
"""

from pathlib import Path

import boto3
from fastapi import APIRouter, HTTPException
from sqlalchemy import text as sql_text

from models.file import FileListResponse, FileInfo, FileDeleteResponse
from core.config import settings
from db.session import engine

router = APIRouter()

s3 = boto3.client("s3", region_name=settings.AWS_REGION)


async def _chunk_counts() -> dict[str, int]:
    async with engine.connect() as conn:
        result = await conn.execute(
            sql_text("SELECT document_id, COUNT(*) AS chunks FROM chunk GROUP BY document_id")
        )
        return {row.document_id: row.chunks for row in result.fetchall()}


def _list_objects() -> list[dict]:
    paginator = s3.get_paginator("list_objects_v2")
    pages = paginator.paginate(
        Bucket=settings.S3_BUCKET_NAME,
        Prefix=f"{settings.RAW_PREFIX}/",
    )
    return [obj for page in pages for obj in page.get("Contents", [])]


def _to_file_info(obj: dict, chunk_count: int | None) -> FileInfo:
    filename = Path(obj["Key"]).name
    document_id = Path(filename).stem

    return FileInfo(
        file_id=document_id,
        filename=filename,
        file_size=obj["Size"],
        file_type=Path(filename).suffix,
        s3_key=obj["Key"],
        uploaded_at=obj["LastModified"],
        processed=chunk_count is not None,
        chunk_count=chunk_count,
    )


@router.get("/", response_model=FileListResponse)
async def list_files(skip: int = 0, limit: int = 100):
    """
    List all uploaded files with pagination.
    """
    objects = _list_objects()
    counts = await _chunk_counts()

    file_infos = [
        _to_file_info(obj, counts.get(Path(obj["Key"]).stem))
        for obj in objects[skip: skip + limit]
    ]

    return FileListResponse(files=file_infos, total=len(objects))


@router.get("/{file_id}", response_model=FileInfo)
async def get_file(file_id: str):
    """
    Get file information by document id.
    """
    objects = [obj for obj in _list_objects() if Path(obj["Key"]).stem == file_id]
    if not objects:
        raise HTTPException(status_code=404, detail="File not found")

    counts = await _chunk_counts()
    return _to_file_info(objects[0], counts.get(file_id))


@router.delete("/{file_id}", response_model=FileDeleteResponse)
async def delete_file(file_id: str):
    """
    Delete a document: its original in S3 and its chunks in the knowledge base.
    """
    objects = [obj for obj in _list_objects() if Path(obj["Key"]).stem == file_id]
    if not objects:
        raise HTTPException(status_code=404, detail="File not found")

    key = objects[0]["Key"]
    s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=key)

    async with engine.begin() as conn:
        await conn.execute(
            sql_text("DELETE FROM chunk WHERE document_id = :document_id"),
            {"document_id": file_id},
        )

    return FileDeleteResponse(
        file_id=file_id,
        filename=Path(key).name,
        deleted=True,
        message="Document and its chunks deleted"
    )
