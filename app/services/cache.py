from datetime import datetime, timedelta, timezone

from cachetools import TTLCache
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.kanji import KanjiCard
from app.schemas.reibun import ReibunSearchResponse

_mem_cache: TTLCache = TTLCache(maxsize=512, ttl=600)

# (expression, page, per_page) → ReibunSearchResponse; 10-minute TTL, 1024 slots
_reibun_cache: TTLCache = TTLCache(maxsize=1024, ttl=600)


def get_reibun_cached(expression: str, page: int, per_page: int) -> ReibunSearchResponse | None:
    return _reibun_cache.get((expression, page, per_page))


def set_reibun_cache(
    expression: str, page: int, per_page: int, response: ReibunSearchResponse
) -> None:
    _reibun_cache[(expression, page, per_page)] = response


async def get_kanji_cached(char: str, session: AsyncSession) -> KanjiCard | None:
    cached = _mem_cache.get(char)
    if cached is not None:
        return cached

    row = (
        await session.execute(
            text(
                "SELECT data FROM kanji_cache WHERE character = :c AND expires_at > NOW()"
            ),
            {"c": char},
        )
    ).mappings().first()

    if row is None:
        return None

    card = KanjiCard(**row["data"])
    _mem_cache[char] = card
    return card


async def set_kanji_cache(char: str, card: KanjiCard, session: AsyncSession) -> None:
    _mem_cache[char] = card

    expires_at = datetime.now(timezone.utc) + timedelta(days=30)
    await session.execute(
        text(
            """
            INSERT INTO kanji_cache (id, character, data, cached_at, expires_at)
            VALUES (gen_random_uuid(), :c, cast(:data AS jsonb), NOW(), :exp)
            ON CONFLICT (character) DO UPDATE
                SET data = EXCLUDED.data,
                    cached_at = NOW(),
                    expires_at = EXCLUDED.expires_at
            """
        ),
        {"c": char, "data": card.model_dump_json(), "exp": expires_at},
    )
    await session.commit()
