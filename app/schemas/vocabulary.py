import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.saved_word import WordStatus
from app.models.user import LanguageEnum
from app.schemas.validators import SafeStr


class SavedWordCreate(BaseModel):
    language: LanguageEnum
    expression: SafeStr = Field(..., max_length=100)
    reading: SafeStr = Field(..., max_length=200)
    meaning: SafeStr = Field(..., max_length=500)
    jlpt_level: int | None = None
    hsk_level: int | None = None
    status: WordStatus = WordStatus.new


class SavedWordStatusUpdate(BaseModel):
    status: WordStatus


class SavedWord(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    language: LanguageEnum
    expression: str
    reading: str
    meaning: str
    jlpt_level: int | None
    hsk_level: int | None
    status: WordStatus
    added_at: datetime

    model_config = {"from_attributes": True}
