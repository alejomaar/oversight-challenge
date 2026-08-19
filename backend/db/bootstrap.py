from sqlalchemy import text

from db.models import Base
from db.session import engine

# The database sits in private subnets and is not reachable from a developer
# machine, so schema setup runs here on startup instead of from a script.
STATEMENTS = [
    # Vector similarity for semantic_search.
    "CREATE EXTENSION IF NOT EXISTS vector",
    # Trigram index support so keyword_search regexes are indexed, not scans.
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
]

INDEXES = [
    "CREATE INDEX IF NOT EXISTS chunk_embedding_idx "
    "ON chunk USING hnsw (embedding vector_cosine_ops)",

    "CREATE INDEX IF NOT EXISTS chunk_text_trgm_idx "
    "ON chunk USING gin (text gin_trgm_ops)",

    "CREATE INDEX IF NOT EXISTS chunk_document_id_idx ON chunk (document_id)",
]


async def ensure_schema():
    """Create extensions, tables and indexes. Idempotent."""
    async with engine.begin() as conn:
        for statement in STATEMENTS:
            await conn.execute(text(statement))

        await conn.run_sync(Base.metadata.create_all)

        for statement in INDEXES:
            await conn.execute(text(statement))
