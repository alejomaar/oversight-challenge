"""
Standalone script to process a raw document:
1. Convert to markdown with Docling (lightweight, no OCR)
2. Save processed markdown to mnt/processed/
3. Chunk with HybridChunker
4. Embed each chunk with Bedrock Titan
5. Save chunks to PostgreSQL (pgvector)

Usage:
    python process_document.py backend/mnt/raw/transformers.pdf
"""

import sys
import uuid
import json
import asyncio
from pathlib import Path

import boto3
from sqlalchemy import text

from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.transforms.chunker import HybridChunker

sys.path.insert(0, str(Path(__file__).parent))
from core.config import settings
from db.session import engine
from db.models import Chunk, Base


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


def embed_text(text_input: str) -> list[float]:
    response = bedrock.invoke_model(
        modelId=settings.BEDROCK_EMBEDDINGS_MODEL_ID,
        contentType="application/json",
        accept="application/json",
        body=json.dumps({"inputText": text_input})
    )
    result = json.loads(response["body"].read())
    return result["embedding"]


async def process(file_path: str):
    raw_path = Path(file_path)
    if not raw_path.exists():
        print(f"File not found: {raw_path}")
        sys.exit(1)

    document_id = raw_path.stem
    print(f"Processing: {raw_path.name}")

    # 1. Convert document to markdown
    print("  Converting to markdown...")
    result = converter.convert(str(raw_path))
    doc = result.document
    markdown = doc.export_to_markdown()

    # 2. Save processed markdown
    processed_path = Path(settings.UPLOAD_DIR) / settings.PROCESSED_DIR / f"{document_id}.md"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_text(markdown, encoding="utf-8")
    print(f"  Saved: {processed_path}")

    # 3. Chunk with HybridChunker
    print("  Chunking...")
    chunker = HybridChunker(max_tokens=512, merge_peers=True)
    chunks = list(chunker.chunk(dl_doc=doc))
    print(f"  Generated {len(chunks)} chunks")

    # 4. Embed and save to database
    print("  Embedding and saving to database...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        for i, chunk in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            embedding = embed_text(chunk.text)

            page_numbers = set()
            if hasattr(chunk.meta, "doc_items") and chunk.meta.doc_items:
                for item in chunk.meta.doc_items:
                    if item.prov:
                        for prov in item.prov:
                            page_numbers.add(prov.page_no)

            page_start = min(page_numbers) if page_numbers else None
            page_end = max(page_numbers) if page_numbers else None

            await conn.execute(
                text("""
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

            if (i + 1) % 10 == 0:
                print(f"    {i + 1}/{len(chunks)} chunks saved")

    print(f"  Done! {len(chunks)} chunks saved to database.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python process_document.py <path-to-raw-file>")
        sys.exit(1)

    asyncio.run(process(sys.argv[1]))
