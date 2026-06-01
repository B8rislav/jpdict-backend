import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base
from .user import LanguageEnum


class WordStatus(str, enum.Enum):
    new = "new"
    learning = "learning"
    known = "known"


class SavedWord(Base):
    __tablename__ = "saved_words"
    __table_args__ = (
        UniqueConstraint("user_id", "language", "expression", name="uq_user_word"),
        CheckConstraint("jlpt_level BETWEEN 1 AND 5", name="ck_jlpt_level"),
        CheckConstraint("hsk_level BETWEEN 1 AND 6", name="ck_hsk_level"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    language: Mapped[LanguageEnum] = mapped_column(
        Enum(LanguageEnum, name="language_enum", create_type=False), nullable=False
    )
    expression: Mapped[str] = mapped_column(String, nullable=False)
    reading: Mapped[str] = mapped_column(String, nullable=False)
    meaning: Mapped[str] = mapped_column(String, nullable=False)
    jlpt_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    hsk_level: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    status: Mapped[WordStatus] = mapped_column(
        Enum(WordStatus, name="word_status"),
        nullable=False,
        server_default="new",
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
