"""add document table and rework chunk

Revision ID: 3c2fb165aa68
Revises: 1b475915bb6c
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '3c2fb165aa68'
down_revision: Union[str, Sequence[str], None] = '1b475915bb6c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'document',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('file_name', sa.Text(), nullable=False),
        sa.Column('s3_key', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('content_hash'),
    )

    # The old chunk table has no stable link to a document beyond a free-text
    # id (the filename stem), so it is dropped and recreated rather than
    # migrated in place.
    op.drop_index("chunk_document_id_idx", table_name="chunk")
    op.execute("DROP INDEX IF EXISTS chunk_text_trgm_idx")
    op.execute("DROP INDEX IF EXISTS chunk_embedding_idx")
    op.drop_table('chunk')

    op.create_table(
        'chunk',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('document_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['document_id'], ['document.id'], ondelete='CASCADE'),
    )

    op.execute(
        "CREATE INDEX chunk_embedding_idx "
        "ON chunk USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX chunk_content_trgm_idx "
        "ON chunk USING gin (content gin_trgm_ops)"
    )
    op.create_index("chunk_document_id_idx", "chunk", ["document_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("chunk_document_id_idx", table_name="chunk")
    op.execute("DROP INDEX IF EXISTS chunk_content_trgm_idx")
    op.execute("DROP INDEX IF EXISTS chunk_embedding_idx")
    op.drop_table('chunk')
    op.drop_table('document')

    op.create_table(
        'chunk',
        sa.Column('chunk_id', sa.Text(), nullable=False),
        sa.Column('document_id', sa.Text(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1024), nullable=True),
        sa.Column('page_start', sa.Integer(), nullable=True),
        sa.Column('page_end', sa.Integer(), nullable=True),
        sa.Column('char_start', sa.Integer(), nullable=True),
        sa.Column('char_end', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('chunk_id'),
    )
    op.execute(
        "CREATE INDEX chunk_embedding_idx "
        "ON chunk USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX chunk_text_trgm_idx "
        "ON chunk USING gin (text gin_trgm_ops)"
    )
    op.create_index("chunk_document_id_idx", "chunk", ["document_id"])
