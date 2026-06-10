import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field

from app.models.saved_word import WordStatus
from app.models.user import LanguageEnum
from app.services import srs
from app.services.srs import Grade


class ReviewCard(BaseModel):
    """The full card payload the client renders during a review session."""

    id: uuid.UUID
    language: LanguageEnum
    expression: str
    reading: str
    meaning: str
    jlpt_level: int | None
    hsk_level: int | None
    status: WordStatus
    due_at: datetime | None
    interval_days: int
    ease_factor: float
    repetitions: int
    lapses: int
    last_reviewed_at: datetime | None
    suspended: bool

    model_config = {"from_attributes": True}

    @computed_field
    @property
    def projected_intervals(self) -> dict[Grade, int]:
        """Seconds-until-due per grade, so the client can label each grade button."""
        state = srs.SrsState(
            repetitions=self.repetitions,
            interval_days=self.interval_days,
            ease_factor=self.ease_factor,
            lapses=self.lapses,
        )
        return srs.project_intervals(state)


class ReviewGrade(BaseModel):
    """Request body for grading a card."""

    grade: Grade


class ReviewResult(BaseModel):
    """Returned after grading: the card's next scheduling."""

    due_at: datetime
    interval_days: int
    repetitions: int
    ease_factor: float


class ReviewStats(BaseModel):
    """Counts for the study dashboard, scoped to one language."""

    new: int
    due: int
    learned: int
    suspended: int
