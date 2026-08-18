"""
Standalone script to process a raw document:
1. Extract text with pypdf
2. Save processed text to mnt/processed/
3. Chunk with RecursiveCharacterTextSplitter
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
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent))
from core.config import settings
from db.session import engine
from db.models import Base

bedrock = boto3.client("bedrock-runtime", region_name=settings.AWS_REGION)

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=settings.CHUNK_SIZE,
    chunk_overlap=settings.CHUNK_OVERLAP,
)


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

    # 1. Extract text
    print("  Extracting text...")
    reader = PdfReader(str(raw_path))
    full_text = "\n\n".join(page.extract_text() or "" for page in reader.pages)

    # 2. Save processed text
    processed_path = Path(settings.UPLOAD_DIR) / settings.PROCESSED_DIR / f"{document_id}.md"
    processed_path.parent.mkdir(parents=True, exist_ok=True)
    processed_path.write_text(full_text, encoding="utf-8")
    print(f"  Saved: {processed_path}")

    # 3. Chunk
    print("  Chunking...")
    chunks = text_splitter.split_text(full_text)
    print(f"  Generated {len(chunks)} chunks")

    # 4. Embed and save to database
    print("  Embedding and saving to database...")
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

        for i, chunk_text in enumerate(chunks):
            chunk_id = str(uuid.uuid4())
            embedding = embed_text(chunk_text)

            await conn.execute(
                text("""
                    INSERT INTO chunk (chunk_id, document_id, text, embedding, char_start, char_end)
                    VALUES (:chunk_id, :document_id, :text, :embedding, :char_start, :char_end)
                """),
                {
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "text": chunk_text,
                    "embedding": str(embedding),
                    "char_start": full_text.find(chunk_text),
                    "char_end": full_text.find(chunk_text) + len(chunk_text),
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
