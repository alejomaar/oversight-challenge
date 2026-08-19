"""create chunk table with pgvector

Revision ID: 1b475915bb6c
Revises: 
Create Date: 2026-08-18 23:49:57.082873

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '1b475915bb6c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # The vector type must exist before the embedding column that uses it.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Trigram index support so keyword_search regexes are indexed, not scans.
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table('chunk',
    sa.Column('chunk_id', sa.Text(), nullable=False),
    sa.Column('document_id', sa.Text(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
    sa.Column('page_start', sa.Integer(), nullable=True),
    sa.Column('page_end', sa.Integer(), nullable=True),
    sa.Column('char_start', sa.Integer(), nullable=True),
    sa.Column('char_end', sa.Integer(), nullable=True),
    sa.PrimaryKeyConstraint('chunk_id')
    )

    # Index types Alembic cannot autogenerate: HNSW for semantic_search's cosine
    # distance, GIN/trigram for keyword_search, plain btree for lookups by document.
    op.execute(
        "CREATE INDEX chunk_embedding_idx "
        "ON chunk USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX chunk_text_trgm_idx "
        "ON chunk USING gin (text gin_trgm_ops)"
    )
    op.create_index("chunk_document_id_idx", "chunk", ["document_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("chunk_document_id_idx", table_name="chunk")
    op.execute("DROP INDEX IF EXISTS chunk_text_trgm_idx")
    op.execute("DROP INDEX IF EXISTS chunk_embedding_idx")
    op.drop_table('chunk')
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
    op.execute("DROP EXTENSION IF EXISTS vector")
