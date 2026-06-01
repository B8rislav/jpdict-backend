from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.reibun import Reibun, ReibunSearchResponse
from app.services.cache import get_reibun_cached, set_reibun_cache


async def search_reibun(
    word_id: int,
    session: AsyncSession,
    page: int,
    per_page: int,
    lang: str = "ru",
) -> ReibunSearchResponse:
    """Find cached example sentences for word_id's headword; returns a ReibunSearchResponse."""
    # Look up the canonical expression for word_id from jmdict_entries
    expr_row = (
        (
            await session.execute(
                text("SELECT kanji_forms, reading_forms FROM jmdict_entries WHERE entry_id = :id"),
                {"id": word_id},
            )
        )
        .mappings()
        .first()
    )

    if expr_row is None:
        return ReibunSearchResponse(result_count=0, pg=page, perPage=per_page, reibuns=[])

    kanji_forms = expr_row["kanji_forms"] or []
    reading_forms = expr_row["reading_forms"] or []
    expression = kanji_forms[0] if kanji_forms else (reading_forms[0] if reading_forms else None)

    if not expression:
        return ReibunSearchResponse(result_count=0, pg=page, perPage=per_page, reibuns=[])

    cached = get_reibun_cached(expression, page, per_page, lang)
    if cached is not None:
        return cached

    offset = (page - 1) * per_page

    rows = (
        (
            await session.execute(
                text(
                    """
                SELECT id, sentence_jp, reading_jp, translation_ru, translation_en
                FROM reibun_entries
                WHERE sentence_jp ILIKE '%' || :expr || '%'
                ORDER BY length(sentence_jp) ASC
                LIMIT :lim OFFSET :off
                """
                ),
                {"expr": expression, "lim": per_page, "off": offset},
            )
        )
        .mappings()
        .all()
    )

    total: int = (
        await session.execute(
            text("SELECT COUNT(*) FROM reibun_entries WHERE sentence_jp ILIKE '%' || :expr || '%'"),
            {"expr": expression},
        )
    ).scalar_one()

    reibuns: list[Reibun] = []
    for row in rows:
        if lang == "en":
            translation = row["translation_en"] or row["translation_ru"] or ""
            translation_lang = "en" if row["translation_en"] else "ru"
        else:
            translation = row["translation_ru"] or row["translation_en"] or ""
            translation_lang = "ru" if row["translation_ru"] else "en"
        reibuns.append(
            Reibun(
                id=row["id"],
                sentence_jp=row["sentence_jp"],
                reading_jp=row["reading_jp"],
                translation=translation,
                translation_lang=translation_lang,
            )
        )

    response = ReibunSearchResponse(
        result_count=total,
        pg=page,
        perPage=per_page,
        reibuns=reibuns,
    )
    set_reibun_cache(expression, page, per_page, response, lang)
    return response
