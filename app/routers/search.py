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
from app.services.nlp.classifier import QueryType, classify
from app.services.search.normalize import normalize_reverse_query

router = APIRouter(prefix="/api", tags=["search"], dependencies=[Depends(rate_limit)])


@router.get("/search", response_model=Page[DictEntry])
async def search(
    q: Annotated[SafeStr, Query(min_length=1, max_length=100)],
    lang: str = Query(..., pattern="^(jp|cn|cn_traditional)$"),
    pagination: Paginator = Depends(paginate),
    session: AsyncSession = Depends(get_session),
) -> Page[DictEntry]:
    if lang == "jp":
        if classify(q, lang) == QueryType.REVERSE:
            normalized = normalize_reverse_query(q)
            items, total = await jmdict.search_jmdict_reverse(
                normalized, session, limit=pagination.per_page, offset=pagination.offset
            )
        else:
            items, total = await jmdict.search_jmdict(
                q, session, limit=pagination.per_page, offset=pagination.offset
            )
        return Page.build(items, total, pagination.page, pagination.per_page)

    if classify(q, lang) == QueryType.REVERSE:
        normalized = normalize_reverse_query(q)
        raw, total = await cedict.search_cedict_reverse(
            normalized, lang, session, limit=pagination.per_page, offset=pagination.offset
        )
    else:
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
