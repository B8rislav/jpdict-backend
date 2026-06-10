import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
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
        Index("idx_saved_words_due", "user_id", "language", "due_at"),
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

    # SRS (SM-2) scheduling state — 1:1 with the saved word (see TASKS.md 17.1)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    interval_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    ease_factor: Mapped[float] = mapped_column(Float, nullable=False, server_default="2.5")
    repetitions: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    lapses: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # When the card was first ever reviewed; drives the rolling daily new-card cap.
    first_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    suspended: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
