from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.session import get_db
from db.models import Chunk

router = APIRouter()


@router.get("/")
async def list_chunks(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Chunk))
    chunks = result.scalars().all()
    return [
        {
            "chunk_id": c.chunk_id,
            "document_id": c.document_id,
            "text": c.text,
            "page_start": c.page_start,
            "page_end": c.page_end,
            "char_start": c.char_start,
            "char_end": c.char_end,
        }
        for c in chunks
    ]
