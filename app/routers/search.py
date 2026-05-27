from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import Paginator, paginate
from app.core.rate_limit import rate_limit
from app.db.database import get_session
from app.schemas.page import Page
from app.schemas.search import DictEntry
from app.schemas.validators import SafeStr
from app.services import cedict, jmdict

router = APIRouter(prefix="/api", tags=["search"], dependencies=[Depends(rate_limit)])


@router.get("/search", response_model=Page[DictEntry])
async def search(
    q: Annotated[SafeStr, Query(min_length=1, max_length=100)],
    lang: str = Query(..., pattern="^(jp|cn|cn_traditional)$"),
    pagination: Paginator = Depends(paginate),
    session: AsyncSession = Depends(get_session),
) -> Page[DictEntry]:
    if lang == "jp":
        items, total = await jmdict.search_jmdict(
            q, session, limit=pagination.per_page, offset=pagination.offset
        )
        return Page.build(items, total, pagination.page, pagination.per_page)

    raw, total = await cedict.search_cedict(
        q, lang, session, limit=pagination.per_page, offset=pagination.offset
    )
    items = [
        DictEntry(
            id=str(entry["id"]),
            lang=lang,
            headword=entry["simplified"],
            reading=entry["pinyin"],
            traditional=entry["traditional"],
            simplified=entry["simplified"],
            pinyin=entry["pinyin"],
            definitions=entry["definitions"],
            hsk_level=entry["hsk_level"],
        )
        for entry in raw
    ]
    return Page.build(items, total, pagination.page, pagination.per_page)
