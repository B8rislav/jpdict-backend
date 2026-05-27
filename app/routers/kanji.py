from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_session
from app.schemas.kanji import KanjiCard
from app.services import jmdict
from app.services import cache as cache_svc

router = APIRouter(prefix="/api", tags=["kanji"])


def _is_cjk(char: str) -> bool:
    cp = ord(char)
    return (
        0x4E00 <= cp <= 0x9FFF    # CJK Unified Ideographs
        or 0x3400 <= cp <= 0x4DBF  # Extension A
        or 0x20000 <= cp <= 0x2A6DF  # Extension B
    )


@router.get("/kanji/search")
async def kanji_search(
    value: str = Query(..., max_length=50),
    session: AsyncSession = Depends(get_session),
):
    # Extract individual CJK / kana characters (hiragana, katakana, kanji)
    cjk_chars = [c for c in value if "぀" <= c <= "鿿"]

    if cjk_chars:
        # Direct lookup: return a row for each distinct kanji char in the query.
        # Also check on/kun readings in case the full value is a single kana reading.
        rows = (
            await session.execute(
                text(
                    """
                    SELECT character, meanings_en, jlpt_level
                    FROM kanjidic_entries
                    WHERE character = ANY(:chars)
                       OR :single = ANY(on_readings)
                       OR :single = ANY(kun_readings)
                    ORDER BY jlpt_level ASC NULLS LAST
                    LIMIT 20
                    """
                ),
                {"chars": cjk_chars, "single": value},
            )
        ).mappings().all()
    else:
        # English / romaji prefix search.
        # unnest(meanings_en) yields each meaning as a string (left side of LIKE),
        # so val || '%' is the pattern — avoids treating stored meanings as patterns.
        rows = (
            await session.execute(
                text(
                    """
                    SELECT DISTINCT ON (character) character, meanings_en, jlpt_level
                    FROM kanjidic_entries, unnest(meanings_en) AS m
                    WHERE lower(m) LIKE lower(:val) || '%'
                    ORDER BY character, jlpt_level ASC NULLS LAST
                    LIMIT 20
                    """
                ),
                {"val": value},
            )
        ).mappings().all()

    kanjis = [
        {
            "id": r["character"],
            "kanji": r["character"],
            "definition": ", ".join((r["meanings_en"] or [])[:3]),
        }
        for r in rows
    ]

    return {"result_count": len(kanjis), "kanjis": kanjis}


@router.get("/kanji/{char}", response_model=KanjiCard)
async def kanji_detail(
    char: str,
    session: AsyncSession = Depends(get_session),
):
    if len(char) != 1 or not _is_cjk(char):
        raise HTTPException(status_code=400, detail="Single CJK character required")

    result = await cache_svc.get_kanji_cached(char, session)
    if result is not None:
        return result

    result = await jmdict.get_kanji_detail(char, session)
    if result is None:
        raise HTTPException(status_code=404, detail="Kanji not found")

    await cache_svc.set_kanji_cache(char, result, session)
    return result
