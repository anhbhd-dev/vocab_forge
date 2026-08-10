# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# espeak-ng: tầng fallback của phiên âm IPA (app/services/phonetics.py) — xử lý được
# collocation và từ không có trong CMUdict. Gói hệ điều hành ~5MB, không kéo theo gì nặng.
RUN apt-get update \
    && apt-get install -y --no-install-recommends espeak-ng \
    && rm -rf /var/lib/apt/lists/*

# Dependency lấy TRỰC TIẾP từ pyproject.toml — không chép lại danh sách vào Dockerfile
# để tránh hai nguồn sự thật lệch nhau. Cache mount của BuildKit giữ wheel đã tải nên
# rebuild sau khi sửa code vẫn nhanh.
COPY pyproject.toml ./
COPY app ./app
COPY scripts ./scripts
RUN --mount=type=cache,target=/root/.cache/pip pip install --no-compile .

# Tạo sẵn thư mục audio TRƯỚC khi chown: volume Docker mount vào đây sẽ thừa kế quyền
# sở hữu của thư mục có trong image. Không có bước này thì volume thuộc root và appuser
# không ghi được file audio.
RUN mkdir -p /app/audio

RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


# --- Stage dev: auto-reload ---
# Code được mount qua volume trong docker-compose nên sửa file là server tự nạp lại.
FROM base AS dev
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
