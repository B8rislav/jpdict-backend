from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from redis.asyncio import ConnectionPool, Redis

from app.core.config import settings
from app.core.security import decode_token

_pool: ConnectionPool | None = None

ANON_LIMIT = 60
AUTH_LIMIT = 120
WINDOW_SECONDS = 60

_optional_bearer = HTTPBearer(auto_error=False)


def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        _pool = ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)
    return _pool


async def get_redis() -> AsyncGenerator[Redis, None]:
    redis = Redis(connection_pool=_get_pool())
    try:
        yield redis
    finally:
        await redis.aclose()


async def rate_limit(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_optional_bearer),
    redis: Redis = Depends(get_redis),
) -> None:
    if credentials:
        try:
            payload = decode_token(credentials.credentials)
            key = f"rl:user:{payload.get('sub')}"
            limit = AUTH_LIMIT
        except JWTError:
            key = f"rl:ip:{request.client.host}"
            limit = ANON_LIMIT
    else:
        key = f"rl:ip:{request.client.host}"
        limit = ANON_LIMIT

    try:
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, WINDOW_SECONDS)
    except Exception:
        return  # fail open if Redis is unavailable

    if count > limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(WINDOW_SECONDS)},
        )
