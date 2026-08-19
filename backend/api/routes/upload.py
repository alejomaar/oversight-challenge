"""
File upload endpoints.
Pipeline: ingest → transform → index

The original file is kept in S3 for provenance. Extracted text, chunks and
embeddings live in Postgres, which is what the agent's tools read.
"""

import uuid
import json
import io
from pathlib import Path
from datetime import datetime

import boto3
from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy import text as sql_text
from pypdf import PdfReader
from docx import Document as DocxDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from core.config import settings
from models.file import FileUploadResponse
from db.session import engine

router = APIRouter()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)
s3 = boto3.client("s3", region_name=settings.AWS_REGION)


def ingest(filename: str, content: bytes) -> str:
    """Store the original document in S3 and return its key."""
    key = f"{settings.RAW_PREFIX}/{filename}"
    s3.put_object(Bucket=settings.S3_BUCKET_NAME, Key=key, Body=content)
    return key


def transform(filename: str, content: bytes) -> str:
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


async def index(document_id: str, text: str) -> int:
    """Chunk, embed, and store in the knowledge base."""
    chunks = text_splitter.split_text(text)

    async with engine.begin() as conn:
        for chunk_text in chunks:
            char_start = text.find(chunk_text)

            await conn.execute(
                sql_text("""
                    INSERT INTO chunk (chunk_id, document_id, text, embedding, char_start, char_end)
                    VALUES (:chunk_id, :document_id, :text, :embedding, :char_start, :char_end)
                """),
                {
                    "chunk_id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "text": chunk_text,
                    "embedding": str(_embed(chunk_text)),
                    "char_start": char_start,
                    "char_end": char_start + len(chunk_text),
                }
            )

    return len(chunks)


def _embed(text_input: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId=settings.BEDROCK_EMBEDDINGS_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text_input})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


async def _already_indexed(document_id: str) -> bool:
    async with engine.connect() as conn:
        result = await conn.execute(
            sql_text("SELECT 1 FROM chunk WHERE document_id = :document_id LIMIT 1"),
            {"document_id": document_id},
        )
        return result.first() is not None


@router.post("/", response_model=FileUploadResponse)
async def upload_file(file: UploadFile = File(...)):
    """
    Upload a document file.
    Pipeline: ingest → transform → index
    """
    file_ext = Path(file.filename).suffix.lower()
    allowed = settings.ALLOWED_EXTENSIONS.split(',')
    if file_ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {settings.ALLOWED_EXTENSIONS}"
        )

    document_id = Path(file.filename).stem
    if await _already_indexed(document_id):
        raise HTTPException(
            status_code=409,
            detail=f"Document '{document_id}' is already in the knowledge base"
        )

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )

    s3_key = ingest(file.filename, content)
    text = transform(file.filename, content)
    chunks_count = await index(document_id, text)

    return FileUploadResponse(
        file_id=document_id,
        filename=file.filename,
        file_size=len(content),
        file_type=file_ext,
        s3_key=s3_key,
        status="success",
        message=f"Document indexed into {chunks_count} chunks",
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
