from __future__ import annotations

from typing import TypedDict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.pinyin import convert_pinyin


class DictEntry(TypedDict):
    id: int
    traditional: str
    simplified: str
    pinyin: str
    definitions: list[str]
    hsk_level: int | None


async def search_cedict(
    query: str,
    lang: str,
    session: AsyncSession,
    *,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[DictEntry], int]:
    """
    Search cedict_entries by simplified or traditional script.

    lang="cn_traditional" → match against traditional column
    any other value        → match against simplified column

    definitions JSONB has {"en": [...], "ru": [...]} keys.
    Returns "ru" when non-empty, otherwise falls back to "en".

    Exact matches are ranked first, then prefix, then trigram similarity.
    """
    col = "traditional" if lang == "cn_traditional" else "simplified"
    params = {
        "exact": query,
        "prefix": f"{query}%",
        "query": query,
        "limit": limit,
        "offset": offset,
    }
    count_params = {"exact": query, "prefix": f"{query}%", "query": query}
    where = (
        f"{col} = :exact OR {col} ILIKE :prefix OR similarity({col}, :query) > 0.3"
    )

    rows = await session.execute(
        text(
            f"""
            SELECT id, traditional, simplified, pinyin, definitions, hsk_level
              FROM cedict_entries
             WHERE {where}
             ORDER BY
                ({col} = :exact) DESC,
                ({col} ILIKE :prefix) DESC,
                similarity({col}, :query) DESC
             LIMIT :limit OFFSET :offset
            """
        ),
        params,
    )
    total: int = (
        await session.execute(
            text(f"SELECT COUNT(*) FROM cedict_entries WHERE {where}"),
            count_params,
        )
    ).scalar_one()

    results: list[DictEntry] = []
    for row in rows:
        defs: dict = row.definitions or {}
        defs_ru: list[str] = defs.get("ru") or []
        defs_en: list[str] = defs.get("en") or []
        results.append(
            DictEntry(
                id=row.id,
                traditional=row.traditional,
                simplified=row.simplified,
                pinyin=convert_pinyin(row.pinyin),
                definitions=defs_ru if defs_ru else defs_en,
                hsk_level=row.hsk_level,
            )
        )
    return results, total
