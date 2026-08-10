"""Cấu hình test.

Biến môi trường phải được set TRƯỚC khi import `app.core.config` (settings được cache
bằng lru_cache), nên khối os.environ nằm ngay đầu file.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="vocabforge-test-"))
# Mặc định chạy trên SQLite tạm để `pytest` hoạt động ngay, không cần Docker.
# Đặt TEST_DATABASE_URL để chạy đúng trên PostgreSQL (CI và trước khi release):
#   docker compose exec -e TEST_DATABASE_URL=postgresql+asyncpg://... backend pytest
os.environ["DATABASE_URL"] = os.environ.get(
    "TEST_DATABASE_URL", f"sqlite+aiosqlite:///{_TMP / 'test.db'}"
)
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-for-hs256-abc"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["DEBUG"] = "false"
os.environ["LLM_FALLBACK_PROVIDER"] = ""
os.environ["FSRS_ENABLE_FUZZING"] = "false"
os.environ["CLUSTER_MIN_NEW_SENSES"] = "2"

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.agents.factory import set_provider_override  # noqa: E402
from app.agents.providers.mock import MockProvider  # noqa: E402
from app.core.db import AsyncSessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.models.base import Base  # noqa: E402


@pytest.fixture(scope="session")
def anyio_backend() -> str:
    return "asyncio"


@pytest_asyncio.fixture
async def db_ready():
    await init_db()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    # BẮT BUỘC với PostgreSQL: pytest-asyncio tạo event loop mới cho mỗi test, trong
    # khi `engine` là global và pool của nó giữ connection asyncpg gắn với loop cũ.
    # Dùng lại ở test sau sẽ ném "attached to a different loop". SQLite/aiosqlite bỏ
    # qua được chuyện này nên lỗi chỉ lộ ra khi chạy trên Postgres.
    await engine.dispose()


@pytest.fixture
def mock_provider() -> MockProvider:
    provider = MockProvider()
    set_provider_override(provider)
    yield provider
    set_provider_override(None)


@pytest_asyncio.fixture
async def client(db_ready, mock_provider):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def session(db_ready):
    async with AsyncSessionLocal() as s:
        yield s


@pytest_asyncio.fixture
async def auth_client(client):
    """Client đã đăng ký + gắn sẵn Bearer token."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "learner@example.com", "password": "secret123"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return client
