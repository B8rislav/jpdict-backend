import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.database import get_session
from app.models.saved_word import SavedWord as SavedWordModel
from app.models.user import User
from app.schemas.vocabulary import SavedWord, SavedWordCreate, SavedWordStatusUpdate

router = APIRouter(prefix="/api/vocabulary", tags=["vocabulary"])


@router.get("", response_model=list[SavedWord])
async def list_vocabulary(
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(SavedWordModel).where(SavedWordModel.user_id == current_user.id)
    )
    return result.scalars().all()


@router.post("", response_model=SavedWord, status_code=status.HTTP_201_CREATED)
async def add_vocabulary(
    body: SavedWordCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    word = SavedWordModel(
        user_id=current_user.id,
        language=body.language,
        expression=body.expression,
        reading=body.reading,
        meaning=body.meaning,
        jlpt_level=body.jlpt_level,
        hsk_level=body.hsk_level,
        status=body.status,
    )
    session.add(word)
    try:
        await session.commit()
        await session.refresh(word)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Word already saved")
    return word


@router.patch("/{word_id}", response_model=SavedWord)
async def update_vocabulary_status(
    word_id: uuid.UUID,
    body: SavedWordStatusUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(SavedWordModel).where(SavedWordModel.id == word_id)
    )
    word = result.scalar_one_or_none()
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    if word.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your word")
    word.status = body.status
    await session.commit()
    await session.refresh(word)
    return word


@router.delete("/{word_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vocabulary(
    word_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(
        select(SavedWordModel).where(SavedWordModel.id == word_id)
    )
    word = result.scalar_one_or_none()
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Word not found")
    if word.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your word")
    await session.delete(word)
    await session.commit()
