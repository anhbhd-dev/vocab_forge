"""Async SQLAlchemy engine + session factory.

PostgreSQL (asyncpg) là database chính, chạy trong Docker container.
SQLite (aiosqlite) vẫn được hỗ trợ để chạy test nhanh trên máy mà không cần Docker —
mọi query trong app đều viết theo cú pháp chung của hai dialect, phần khác biệt duy
nhất được cô lập trong file này.
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

IS_SQLITE = settings.database_url.startswith("sqlite")

_connect_args: dict[str, Any] = {}
_engine_kwargs: dict[str, Any] = {"echo": False, "future": True}

if IS_SQLITE:
    # check_same_thread=False cần cho SQLite khi dùng nhiều task async.
    _connect_args["check_same_thread"] = False
else:
    # PostgreSQL: pool đủ rộng cho pipeline enrichment chạy song song nhiều agent,
    # mỗi agent mở session riêng (xem services/ingestion_pipeline.py).
    _engine_kwargs.update(
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_pre_ping=True,  # tránh dùng lại connection đã chết sau khi PG restart
        pool_recycle=1800,
    )
    # asyncpg tự cache prepared statement; tắt để tương thích với pgbouncer nếu sau
    # này đặt thêm connection pooler ở giữa.
    _connect_args["statement_cache_size"] = 0

engine: AsyncEngine = create_async_engine(
    settings.database_url, connect_args=_connect_args, **_engine_kwargs
)


if IS_SQLITE:

    @event.listens_for(engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
        """PRAGMA cho mọi connection SQLite mới.

        - foreign_keys: SQLite mặc định TẮT ràng buộc khoá ngoại (PostgreSQL luôn bật).
        - WAL: cho phép đọc song song trong lúc có một writer.
        - busy_timeout: SQLite chỉ cho một writer tại một thời điểm; chờ tối đa 10s
          thay vì ném "database is locked" ngay.
        """
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=10000")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: một session cho mỗi request."""
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """Tạo schema nếu chưa có.

    Đủ dùng ở giai đoạn này (giữ đơn giản theo tinh thần file 04). Khi schema bắt đầu
    thay đổi trên dữ liệu thật thì thay bằng Alembic — models đã sẵn sàng cho autogenerate.
    """
    from app.models.base import Base
    import app.models  # noqa: F401  — import để đăng ký toàn bộ model vào metadata

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def ping() -> bool:
    """Kiểm tra kết nối DB — dùng cho `/health` và healthcheck của container."""
    from sqlalchemy import text

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:  # pragma: no cover - phụ thuộc hạ tầng
        return False
