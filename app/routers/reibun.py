from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import rate_limit
from app.db.database import get_session
from app.schemas.reibun import ReibunSearchResponse
from app.services.reibun import search_reibun

router = APIRouter(prefix="/api", tags=["reibun"], dependencies=[Depends(rate_limit)])


@router.get("/reibun/search/{word_id}", response_model=ReibunSearchResponse)
async def reibun_search(
    word_id: int,
    pg: int = Query(1, ge=1, description="Page number"),
    perPage: int = Query(10, ge=1, le=100, description="Items per page"),
    session: AsyncSession = Depends(get_session),
) -> ReibunSearchResponse:
    return await search_reibun(word_id, session, page=pg, per_page=perPage)
