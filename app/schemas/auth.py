import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr

from app.models.user import LanguageEnum


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    language: LanguageEnum


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    language: LanguageEnum
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
