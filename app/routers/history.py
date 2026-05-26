import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.database import get_session
from app.models.search_history import SearchHistory
from app.models.user import LanguageEnum, User

router = APIRouter(prefix="/api/history", tags=["history"])


class HistoryEntry(BaseModel):
    id: uuid.UUID
    language: LanguageEnum
    query: str
    query_type: str
    searched_at: datetime

    model_config = {"from_attributes": True}


class HistoryCreate(BaseModel):
    language: LanguageEnum
    query: str
    query_type: str


@router.post("", status_code=status.HTTP_201_CREATED, response_model=HistoryEntry)
async def record_history(
    body: HistoryCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = SearchHistory(
        user_id=current_user.id,
        language=body.language,
        query=body.query,
        query_type=body.query_type,
    )
    session.add(entry)
    await session.commit()
    await session.refresh(entry)
    return entry


@router.get("", response_model=list[HistoryEntry])
async def get_history(
    lang: LanguageEnum | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    stmt = select(SearchHistory).where(SearchHistory.user_id == current_user.id)
    if lang is not None:
        stmt = stmt.where(SearchHistory.language == lang)
    stmt = stmt.order_by(SearchHistory.searched_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_history_entry(
    entry_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    entry = await session.get(SearchHistory, entry_id)
    if entry and entry.user_id == current_user.id:
        await session.delete(entry)
        await session.commit()


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    await session.execute(
        delete(SearchHistory).where(SearchHistory.user_id == current_user.id)
    )
    await session.commit()
