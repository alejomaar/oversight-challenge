"""
Document operations: upload pipeline (ingest -> transform -> index), listing,
and deletion.

Postgres is the source of truth for document metadata, extracted content, and
chunks; the original file is kept in S3 solely for provenance. A document's
UUID (documents.id) is its only application-level identifier.
"""

import hashlib
import io
import json
import uuid
from datetime import datetime
from pathlib import Path

import boto3
from botocore.config import Config
from fastapi import HTTPException
from sqlalchemy import func, select
from pypdf import PdfReader
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config.settings import settings
from models import Chunk, Document
from infrastructure.db import db_session
from schemas.api.files import (
    FileDeleteResponse,
    FileDownloadResponse,
    FileInfo,
    FileListResponse,
    FileUploadResponse,
)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
# SigV4 explicitly: presigned URLs signed with SigV2 carry no session token, so
# they are rejected when signed with the Lambda role's temporary credentials.
s3 = boto3.client(
    "s3",
    region_name=settings.AWS_REGION,
    config=Config(signature_version="s3v4"),
)

# Short enough to stay well inside the Lambda role's credential session.
DOWNLOAD_URL_TTL = 300


def _embed(text_input: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId=settings.BEDROCK_EMBEDDINGS_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text_input})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


def _content_hash(content: bytes) -> str:
    """Hash of the raw uploaded bytes, independent of how text is later extracted."""
    return hashlib.sha256(content).hexdigest()


def _transform(filename: str, content: bytes) -> str:
    """Extract plain text from the document."""
    file_ext = Path(filename).suffix.lower()

    if file_ext == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)

    if file_ext in (".docx", ".doc"):
        doc = DocxDocument(io.BytesIO(content))
        return "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if file_ext == ".txt":
        return content.decode("utf-8")

    raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")


def _to_file_info(document: Document) -> FileInfo:
    return FileInfo(
        file_id=str(document.id),
        filename=document.file_name,
        file_size=len(document.content.encode("utf-8")),
        file_type=Path(document.file_name).suffix,
        s3_key=document.s3_key,
        uploaded_at=document.created_at,
    )


async def upload_document(filename: str, content: bytes) -> FileUploadResponse:
    """Validate and run the ingest -> transform -> index pipeline for one file."""
    file_ext = Path(filename).suffix.lower()
    allowed = settings.ALLOWED_EXTENSIONS.split(',')
    if file_ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )

    content_hash = _content_hash(content)

    async with db_session() as session:
        existing = await session.execute(
            select(Document.id).where(Document.content_hash == content_hash)
        )
        if existing.first() is not None:
            raise HTTPException(
                status_code=409,
                detail="A document with identical content already exists in the knowledge base"
            )

    text = _transform(filename, content)
    document_id = uuid.uuid4()
    s3_key = f"{settings.RAW_PREFIX}/{document_id}/{filename}"
    s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key, Body=content)

    chunks = text_splitter.split_text(text)

    async with db_session() as session:
        session.add(Document(
            id=document_id,
            file_name=filename,
            s3_key=s3_key,
            content=text,
            content_hash=content_hash,
        ))
        # No ORM relationship() links Document/Chunk, so unit-of-work has no
        # dependency info to order the inserts — flush the document first.
        await session.flush()
        for index, chunk_text in enumerate(chunks):
            session.add(Chunk(
                id=uuid.uuid4(),
                document_id=document_id,
                chunk_index=index,
                content=chunk_text,
                embedding=_embed(chunk_text),
            ))
        await session.commit()

    return FileUploadResponse(
        file_id=str(document_id),
        filename=filename,
        file_size=len(content),
        file_type=file_ext,
        s3_key=s3_key,
        status="success",
        message=f"Document indexed into {len(chunks)} chunks",
        uploaded_at=datetime.now()
    )


async def list_documents(skip: int, limit: int) -> FileListResponse:
    """List all documents with pagination."""
    async with db_session() as session:
        total = (await session.execute(select(func.count()).select_from(Document))).scalar_one()
        result = await session.execute(
            select(Document)
            .order_by(Document.created_at)
            .offset(skip)
            .limit(limit)
        )
        documents = result.scalars().all()

    return FileListResponse(
        files=[_to_file_info(document) for document in documents],
        total=total,
    )


async def get_document(document_id: uuid.UUID) -> FileInfo:
    """Get document information by its UUID."""
    async with db_session() as session:
        document = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()

    if document is None:
        raise HTTPException(status_code=404, detail="File not found")

    return _to_file_info(document)


async def download_document(document_id: uuid.UUID) -> FileDownloadResponse:
    """Presigned GET URL for a document's original file in S3."""
    info = await get_document(document_id)

    url = s3.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.S3_BUCKET_NAME,
            "Key": info.s3_key,
            # Save under the original name rather than the UUID path.
            "ResponseContentDisposition": f'attachment; filename="{info.filename}"',
        },
        ExpiresIn=DOWNLOAD_URL_TTL,
    )

    return FileDownloadResponse(
        **info.model_dump(),
        download_url=url,
        expires_in=DOWNLOAD_URL_TTL,
    )


async def delete_document(document_id: uuid.UUID) -> FileDeleteResponse:
    """Delete a document: its original in S3 and its record (and chunks) in Postgres."""
    async with db_session() as session:
        document = (
            await session.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()

        if document is None:
            raise HTTPException(status_code=404, detail="File not found")

        s3.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=document.s3_key)

        filename = document.file_name
        await session.delete(document)
        await session.commit()

    return FileDeleteResponse(
        file_id=str(document_id),
        filename=filename,
        deleted=True,
        message="Document and its chunks deleted"
    )
