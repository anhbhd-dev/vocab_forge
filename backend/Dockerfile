# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# Dependency lấy TRỰC TIẾP từ pyproject.toml — không chép lại danh sách vào Dockerfile
# để tránh hai nguồn sự thật lệch nhau. Cache mount của BuildKit giữ wheel đã tải nên
# rebuild sau khi sửa code vẫn nhanh.
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-compile .

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# --- Stage dev: thêm test dependency + auto-reload ---
# Code được mount qua volume trong docker-compose nên sửa file là server tự nạp lại.
FROM base AS dev
USER root
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-compile "pytest>=8.3" "pytest-asyncio>=0.24" "anyio>=4.6"
USER appuser
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
