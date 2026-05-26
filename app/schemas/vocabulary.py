import uuid
from datetime import datetime

from pydantic import BaseModel

from app.models.saved_word import WordStatus
from app.models.user import LanguageEnum


class SavedWordCreate(BaseModel):
    language: LanguageEnum
    expression: str
    reading: str
    meaning: str
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
