"""agent_cache lookup/store.

File 03 mục 0: "Mọi response phải qua `agent_cache` TRƯỚC khi gọi LLM thật".
File 04 yêu cầu #4: cache key = sha256(agent_name + normalized_input + target_band).

Chuẩn hoá input (`normalize_input`) rất quan trọng để cache thực sự hit: cùng một từ
academic do 2 user khác nhau gửi lên chỉ khác khoảng trắng/hoa-thường vẫn phải trúng
cùng một key (file 01 mục 3: từ vựng IELTS trùng lặp rất cao giữa người dùng).
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jobs import AgentCache

_WHITESPACE = re.compile(r"\s+")


def normalize_input(value: Any) -> str:
    """Chuẩn hoá input về chuỗi ổn định, không phụ thuộc thứ tự khoá dict."""
    if isinstance(value, str):
        text = value
    else:
        if hasattr(value, "model_dump"):
            value = value.model_dump()
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return _WHITESPACE.sub(" ", text.strip()).lower()


def make_cache_key(
    agent_name: str, payload: Any, target_band: float | None = None
) -> str:
    raw = f"{agent_name}|{normalize_input(payload)}|{target_band if target_band is not None else ''}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


async def get_cached(session: AsyncSession, cache_key: str) -> dict[str, Any] | None:
    row = await session.get(AgentCache, cache_key)
    if row is None:
        return None
    await session.execute(
        update(AgentCache)
        .where(AgentCache.cache_key == cache_key)
        .values(hit_count=AgentCache.hit_count + 1)
    )
    try:
        return json.loads(row.response_json)
    except json.JSONDecodeError:
        # Cache hỏng thì coi như miss, để lần gọi sau ghi đè bằng dữ liệu sạch.
        return None


async def store_cached(
    session: AsyncSession, cache_key: str, agent_name: str, payload: Any
) -> None:
    if hasattr(payload, "model_dump"):
        payload = payload.model_dump()
    response_json = json.dumps(payload, ensure_ascii=False, default=str)

    existing = await session.get(AgentCache, cache_key)
    if existing is not None:
        existing.response_json = response_json
        existing.agent_name = agent_name
        return
    session.add(
        AgentCache(
            cache_key=cache_key, agent_name=agent_name, response_json=response_json
        )
    )


async def cache_stats(session: AsyncSession) -> list[dict[str, Any]]:
    """Thống kê cache theo agent — dùng cho `/api/analytics/overview`."""
    rows = (
        await session.execute(
            select(
                AgentCache.agent_name,
                AgentCache.cache_key,
                AgentCache.hit_count,
            )
        )
    ).all()
    by_agent: dict[str, dict[str, int]] = {}
    for agent_name, _key, hits in rows:
        bucket = by_agent.setdefault(agent_name, {"entries": 0, "hits": 0})
        bucket["entries"] += 1
        bucket["hits"] += hits or 0
    return [{"agent_name": k, **v} for k, v in sorted(by_agent.items())]
