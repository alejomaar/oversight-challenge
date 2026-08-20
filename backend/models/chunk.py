import uuid

from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class Chunk(Base):
    """One embedded slice of a document's text, as produced by the text splitter.

    `embedding` (Titan, 1024 dims) backs `semantic_search`'s cosine similarity
    search. `chunk_index` preserves the slice's original order within its
    document. `char_start`/`char_end` locate the slice inside
    `document.content`, so a search hit can be expanded with `read_document`.
    """

    __tablename__ = "chunk"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("document.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Half-open [char_start, char_end) offsets into document.content.
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding = mapped_column(Vector(1024))
