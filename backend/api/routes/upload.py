"""
File upload endpoints.
Pipeline: ingest → transform → index
"""

import uuid
import json
import logging
import tempfile
from pathlib import Path
from datetime import datetime

logging.getLogger("docling").setLevel(logging.ERROR)

import boto3
from fastapi import APIRouter, UploadFile, File, HTTPException
from sqlalchemy import text as sql_text

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker import HybridChunker

from core.config import settings
from models.file import FileUploadResponse
from db.session import engine
from db.models import Base

router = APIRouter()

pipeline_options = PdfPipelineOptions()
pipeline_options.do_ocr = False
pipeline_options.do_table_structure = False

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=pipeline_options,
            backend=PyPdfiumDocumentBackend
        )
    }
)

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)


def ingest(filename: str, content: bytes) -> Path:
    """Store the original document as-is."""
    raw_path = Path(settings.UPLOAD_DIR) / settings.RAW_DIR / filename
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    raw_path.write_bytes(content)
    return raw_path


def transform(filename: str, content: bytes):
    """Convert document to structured markdown and return the docling document."""
    file_ext = Path(filename).suffix.lower()
    document_id = Path(filename).stem

    with tempfile.NamedTemporaryFile(suffix=file_ext, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    result = converter.convert(str(tmp_path))
    doc = result.document
    markdown = doc.export_to_markdown()
    tmp_path.unlink()

    processed_path = Path(settings.UPLOAD_DIR) / settings.PROCESSED_DIR / f"{document_id}.md"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_text(markdown, encoding="utf-8")

    return doc


async def index(document_id: str, doc):
    """Chunk, embed, and store in the knowledge base."""
    chunker = HybridChunker(max_tokens=512, merge_peers=True)
    chunks = list(chunker.chunk(dl_doc=doc))

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        for chunk in chunks:
            chunk_id = str(uuid.uuid4())
            embedding = _embed(chunk.text)

            page_numbers = set()
            if hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
                for item in chunk.meta.doc_items:
                    if item.prov:
                        for prov in item.prov:
                            page_numbers.add(prov.page_no)

            page_start = min(page_numbers) if page_numbers else None
            page_end = max(page_numbers) if page_numbers else None

            await conn.execute(
                sql_text("""
                    INSERT INTO chunk (chunk_id, document_id, text, embedding, page_start, page_end)
                    VALUES (:chunk_id, :document_id, :text, :embedding, :page_start, :page_end)
                """),
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "text": chunk.text,
                    "embedding": str(embedding),
                    "page_start": page_start,
                    "page_end": page_end,
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
    doc = transform(file.filename, content)
    chunks_count = await index(document_id, doc)

    return FileUploadResponse(
        file_id=file_id,
        filename=file.filename,
        file_size=len(content),
        file_type=file_ext,
        s3_key=file.filename,
        status="success",
        message=f"Document indexed: {chunks_count} chunks embedded",
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
