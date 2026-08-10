"""VocabForge Pro — FastAPI entrypoint."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agents.base import AgentSchemaError, LLMError
from app.api import analytics, auth, clusters, decks, ingestion, production, review
from app.core.config import settings
from app.core.db import init_db, ping
from app.srs.engine import FSRS_SUPPORTS_FRACTIONAL_INTERVAL, FSRS_VARIANT

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Trong Docker, container backend có thể khởi động trước khi PostgreSQL sẵn sàng
    # nhận kết nối (healthcheck của compose đã chặn phần lớn trường hợp, nhưng vẫn còn
    # khoảng trống khi Postgres restart). Thử lại vài lần thay vì crash ngay.
    last_error: Exception | None = None
    for attempt in range(1, 11):
        try:
            await init_db()
            last_error = None
            break
        except Exception as exc:  # pragma: no cover - phụ thuộc hạ tầng
            last_error = exc
            logger.warning(
                "Chưa kết nối được database (lần %d/10): %s", attempt, exc
            )
            await asyncio.sleep(min(2 * attempt, 10))
    if last_error is not None:  # pragma: no cover
        raise last_error

    logger.info(
        "SRS engine: %s (fractional interval: %s), LLM provider: %s, DB: %s",
        FSRS_VARIANT,
        FSRS_SUPPORTS_FRACTIONAL_INTERVAL,
        settings.llm_provider,
        settings.database_url.split("@")[-1],  # không log credential
    )
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "Backend cho VocabForge Pro — SRS (FSRS) + lớp AI agent cho từ vựng IELTS. "
        "Vòng review là fast path thuần thuật toán; mọi lời gọi LLM nằm ở vòng agent "
        "chạy nền (ngoại lệ: production grading, cũng chạy nền + poll)."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for module in (auth, decks, ingestion, review, production, clusters, analytics):
    app.include_router(module.router)


@app.exception_handler(LLMError)
async def _llm_error_handler(_request, exc: LLMError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": f"Lỗi LLM: {exc}"})


@app.exception_handler(AgentSchemaError)
async def _agent_schema_error_handler(_request, exc: AgentSchemaError):
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.get("/health", tags=["meta"])
async def health() -> dict:
    """Healthcheck cho container: 'ok' chỉ khi database thật sự trả lời được."""
    db_ok = await ping()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "up" if db_ok else "down",
        "srs_engine": FSRS_VARIANT,
        "fractional_interval": FSRS_SUPPORTS_FRACTIONAL_INTERVAL,
        "llm_provider": settings.llm_provider,
    }
