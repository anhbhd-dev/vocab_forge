"""Auth & User — file 01 mục 2, phần "Auth & User".

    POST   /api/auth/register
    POST   /api/auth/login
    GET    /api/users/me
    PATCH  /api/users/me/settings
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import CurrentUser, SessionDep
from app.core.security import create_access_token, hash_password, verify_password
from app.models.user import User
from app.schemas.api import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserSettingsUpdate,
)

router = APIRouter(tags=["auth"])


@router.post("/api/auth/register", response_model=TokenResponse, status_code=201)
async def register(payload: RegisterRequest, session: SessionDep) -> TokenResponse:
    email = payload.email.strip().lower()
    existing = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email đã được đăng ký"
        )

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        daily_new_word_goal=payload.daily_new_word_goal,
        timezone=payload.timezone,
    )
    session.add(user)
    await session.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/api/auth/login", response_model=TokenResponse)
async def login(payload: LoginRequest, session: SessionDep) -> TokenResponse:
    email = payload.email.strip().lower()
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email hoặc mật khẩu không đúng",
        )
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/api/users/me", response_model=UserOut, tags=["users"])
async def read_me(user: CurrentUser) -> User:
    return user


@router.patch("/api/users/me/settings", response_model=UserOut, tags=["users"])
async def update_settings(
    payload: UserSettingsUpdate, user: CurrentUser, session: SessionDep
) -> User:
    if payload.daily_new_min is not None:
        user.daily_new_min = payload.daily_new_min
    if payload.daily_new_max is not None:
        user.daily_new_max = payload.daily_new_max
    if user.daily_new_min > user.daily_new_max:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Số từ tối thiểu không được lớn hơn số từ tối đa",
        )

    if payload.daily_new_word_goal is not None:
        user.daily_new_word_goal = payload.daily_new_word_goal
    if payload.timezone is not None:
        user.timezone = payload.timezone

    # Kéo mục tiêu hiện tại vào trong khoảng vừa đặt. Thiếu bước này thì người học đặt
    # "20–30 từ/ngày" xong vẫn chỉ nhận 10 từ mới mỗi ngày cho tới khi ramp-up bò lên
    # từng nấc 5 — bấm lưu mà không thấy gì đổi thì đúng là tính năng hỏng.
    user.daily_new_word_goal = min(
        user.daily_new_max, max(user.daily_new_min, user.daily_new_word_goal)
    )

    await session.commit()
    await session.refresh(user)
    return user
