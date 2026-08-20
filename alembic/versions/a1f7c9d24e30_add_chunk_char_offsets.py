"""add chunk char offsets

Revision ID: a1f7c9d24e30
Revises: 3c2fb165aa68
Create Date: 2026-08-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1f7c9d24e30'
down_revision: Union[str, Sequence[str], None] = '3c2fb165aa68'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chunk', sa.Column('char_start', sa.Integer(), nullable=True))
    op.add_column('chunk', sa.Column('char_end', sa.Integer(), nullable=True))

    # Existing chunks predate offset tracking. Locate each one in its document's
    # text; a chunk whose text repeats verbatim lands on its first occurrence,
    # which is close enough to make read_document usable on old uploads.
    op.execute(
        """
        UPDATE chunk
        SET char_start = GREATEST(position(chunk.content in document.content) - 1, 0),
            char_end = GREATEST(position(chunk.content in document.content) - 1, 0)
                       + length(chunk.content)
        FROM document
        WHERE document.id = chunk.document_id
        """
    )

    op.alter_column('chunk', 'char_start', nullable=False)
    op.alter_column('chunk', 'char_end', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chunk', 'char_end')
    op.drop_column('chunk', 'char_start')
