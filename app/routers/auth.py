from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.database import get_session
from app.models.user import User
from app.schemas.auth import TokenResponse, UserCreate, UserResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])

_REFRESH_COOKIE = "refresh_token"


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: UserCreate, session: AsyncSession = Depends(get_session)):
    """Create a user account; returns the new UserResponse (201) or 409 if email is taken."""
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        language=body.language,
    )
    session.add(user)
    try:
        await session.commit()
        await session.refresh(user)
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: UserCreate, response: Response, session: AsyncSession = Depends(get_session)):
    """Verify credentials; returns a TokenResponse and sets the refresh cookie (401 on failure)."""
    result = await session.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    subject = str(user.id)
    response.set_cookie(
        key=_REFRESH_COOKIE,
        value=create_refresh_token(subject),
        httponly=True,
        samesite="lax",
        secure=False,  # set True in production behind HTTPS
    )
    return TokenResponse(access_token=create_access_token(subject))


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    session: AsyncSession = Depends(get_session),
    refresh_token: str | None = Cookie(default=None, alias=_REFRESH_COOKIE),
):
    """Mint a new access token from the refresh cookie; returns a TokenResponse (401 if invalid)."""
    if refresh_token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token"
        )

    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    user_id = payload.get("sub")
    result = await session.execute(select(User).where(User.id == user_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    return TokenResponse(access_token=create_access_token(user_id))
