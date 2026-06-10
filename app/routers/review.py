import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.database import get_session
from app.models.saved_word import SavedWord as SavedWordModel
from app.models.user import LanguageEnum, User
from app.schemas.review import ReviewCard, ReviewGrade, ReviewResult, ReviewStats
from app.services import srs

router = APIRouter(prefix="/api/review", tags=["review"])

# Cap on never-reviewed cards mixed into a single queue, so a large backlog of
# new words doesn't bury the cards actually due for review.
MAX_NEW_PER_QUEUE = 20


@router.get("/queue", response_model=list[ReviewCard])
async def review_queue(
    language: LanguageEnum = Query(..., description="Card language to study"),
    limit: int = Query(20, ge=1, le=100, description="Max cards to return"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return the next cards to study (due reviews first, then new cards); list[ReviewCard]."""
    now = datetime.now(UTC)
    base = and_(
        SavedWordModel.user_id == current_user.id,
        SavedWordModel.language == language,
        SavedWordModel.suspended.is_(False),
    )

    # Already-seen cards that have come due, oldest-due first.
    due_stmt = (
        select(SavedWordModel)
        .where(
            base,
            SavedWordModel.last_reviewed_at.isnot(None),
            SavedWordModel.due_at <= now,
        )
        .order_by(SavedWordModel.due_at.asc())
        .limit(limit)
    )
    due_cards = list((await session.execute(due_stmt)).scalars().all())

    # Fill any remaining room with never-reviewed cards, capped per queue.
    remaining = min(limit - len(due_cards), MAX_NEW_PER_QUEUE)
    new_cards: list[SavedWordModel] = []
    if remaining > 0:
        new_stmt = (
            select(SavedWordModel)
            .where(base, SavedWordModel.last_reviewed_at.is_(None))
            .order_by(SavedWordModel.added_at.asc())
            .limit(remaining)
        )
        new_cards = list((await session.execute(new_stmt)).scalars().all())

    return due_cards + new_cards


@router.post("/{saved_word_id}", response_model=ReviewResult)
async def grade_card(
    saved_word_id: uuid.UUID,
    body: ReviewGrade,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Grade a card, persist its new SM-2 state, and return the next ReviewResult."""
    word = await _get_owned_word(saved_word_id, current_user, session)

    now = datetime.now(UTC)
    scheduling = srs.schedule(
        srs.SrsState(
            repetitions=word.repetitions,
            interval_days=word.interval_days,
            ease_factor=word.ease_factor,
            lapses=word.lapses,
        ),
        body.grade,
        now=now,
    )

    word.repetitions = scheduling.repetitions
    word.interval_days = scheduling.interval_days
    word.ease_factor = scheduling.ease_factor
    word.lapses = scheduling.lapses
    word.due_at = scheduling.due_at
    word.last_reviewed_at = now
    await session.commit()

    return ReviewResult(
        due_at=scheduling.due_at,
        interval_days=scheduling.interval_days,
        repetitions=scheduling.repetitions,
        ease_factor=scheduling.ease_factor,
    )


@router.get("/stats", response_model=ReviewStats)
async def review_stats(
    language: LanguageEnum = Query(..., description="Card language to summarise"),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return due / new / learned / suspended counts for the study dashboard."""
    now = datetime.now(UTC)
    active = SavedWordModel.suspended.is_(False)
    seen = SavedWordModel.last_reviewed_at.isnot(None)

    stmt = select(
        func.count().filter(and_(active, SavedWordModel.last_reviewed_at.is_(None))).label("new"),
        func.count().filter(and_(active, seen, SavedWordModel.due_at <= now)).label("due"),
        func.count()
        .filter(
            and_(
                active,
                seen,
                or_(SavedWordModel.due_at.is_(None), SavedWordModel.due_at > now),
            )
        )
        .label("learned"),
        func.count().filter(SavedWordModel.suspended.is_(True)).label("suspended"),
    ).where(
        SavedWordModel.user_id == current_user.id,
        SavedWordModel.language == language,
    )

    row = (await session.execute(stmt)).mappings().one()
    return ReviewStats(
        new=row["new"], due=row["due"], learned=row["learned"], suspended=row["suspended"]
    )


@router.post("/{saved_word_id}/suspend", response_model=ReviewCard)
async def suspend_card(
    saved_word_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Suspend a card so it drops out of the review queue; returns the ReviewCard."""
    return await _set_suspended(saved_word_id, True, current_user, session)


@router.post("/{saved_word_id}/unsuspend", response_model=ReviewCard)
async def unsuspend_card(
    saved_word_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Return a suspended card to rotation; returns the ReviewCard."""
    return await _set_suspended(saved_word_id, False, current_user, session)


async def _get_owned_word(
    saved_word_id: uuid.UUID, current_user: User, session: AsyncSession
) -> SavedWordModel:
    """Fetch a saved word, enforcing ownership (404 if missing, 403 if not owner)."""
    result = await session.execute(select(SavedWordModel).where(SavedWordModel.id == saved_word_id))
    word = result.scalar_one_or_none()
    if word is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Card not found")
    if word.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your card")
    return word


async def _set_suspended(
    saved_word_id: uuid.UUID, value: bool, current_user: User, session: AsyncSession
) -> SavedWordModel:
    """Toggle a card's suspended flag and persist it."""
    word = await _get_owned_word(saved_word_id, current_user, session)
    word.suspended = value
    await session.commit()
    await session.refresh(word)
    return word
