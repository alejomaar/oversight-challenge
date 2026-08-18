"""
File upload endpoints.
Pipeline: ingest → transform → index
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
from db.models import Base

router = APIRouter()

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def ingest(filename: str, content: bytes) -> Path:
    """Store the original document as-is."""
    raw_path = Path(settings.UPLOAD_DIR) / settings.RAW_DIR / filename
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)
    return raw_path


def transform(filename: str, content: bytes) -> str:
    """Extract text from document and save processed version."""
    file_ext = Path(filename).suffix.lower()
    document_id = Path(filename).stem

    if file_ext == ".pdf":
        reader = PdfReader(io.BytesIO(content))
        text = "\n\n".join(page.extract_text() or "" for page in reader.pages)
    elif file_ext in (".docx", ".doc"):
        doc = DocxDocument(io.BytesIO(content))
        text = "\n\n".join(p.text for p in doc.paragraphs if p.text.strip())
    elif file_ext == ".txt":
        text = content.decode("utf-8")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file_ext}")

    processed_path = Path(settings.UPLOAD_DIR) / settings.PROCESSED_DIR / f"{document_id}.md"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_text(text, encoding="utf-8")

    return text


async def index(document_id: str, text: str):
    """Chunk, embed, and store in the knowledge base."""
    chunks = text_splitter.split_text(text)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            embedding = _embed(chunk_text)

            await conn.execute(
                sql_text("""
                    INSERT INTO chunk (chunk_id, document_id, text, embedding, char_start, char_end)
                    VALUES (:chunk_id, :document_id, :text, :embedding, :char_start, :char_end)
                """),
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "text": chunk_text,
                    "embedding": str(embedding),
                    "char_start": text.find(chunk_text),
                    "char_end": text.find(chunk_text) + len(chunk_text),
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

    raw_path = Path(settings.UPLOAD_DIR) / settings.RAW_DIR / file.filename
    if raw_path.exists():
        raise HTTPException(
            status_code=409,
            detail=f"File '{file.filename}' already exists"
        )

    content = await file.read()
    if len(content) > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE / (1024*1024):.1f}MB"
        )

    file_id = str(uuid.uuid4())
    document_id = Path(file.filename).stem

    ingest(file.filename, content)
    text = transform(file.filename, content)
    chunks_count = await index(document_id, text)

    return FileUploadResponse(
        file_id=file_id,
        filename=file.filename,
        file_size=len(content),
        file_type=file_ext,
        s3_key=file.filename,
        status="success",
        message=f"Document indexed",
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
