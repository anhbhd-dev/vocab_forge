# VocabForge Pro

Ứng dụng học từ vựng học thuật (IELTS) dùng spaced repetition làm lõi, cộng một lớp AI
agent để biến bài đọc thật thành thẻ học chất lượng cao, chấm câu tự viết và điều chỉnh
lịch ôn **theo loại lỗi** chứ không chỉ đúng/sai.

Spec đầy đủ nằm trong `docs/` (files 00–05). Code bám sát spec; mọi chỗ lệch đều được
ghi rõ lý do trong `backend/README.md` mục "Những chỗ lệch khỏi spec".

```
vocab_forge/
├── docs/               # spec gốc (nguồn chân lý)
├── backend/            # FastAPI + PostgreSQL + FSRS + 6 agent
├── frontend/           # React + TS + Vite + Tailwind v4 + shadcn/ui
└── docker-compose.yml  # postgres + backend + frontend
```

## Chạy toàn bộ bằng Docker

```bash
cp .env.example .env
#  → dán DEEPSEEK_API_KEY vào .env
#    (muốn xem UI trước khi có key: đặt LLM_PROVIDER=mock)

docker compose up -d
```

| Dịch vụ | Địa chỉ |
|---|---|
| Frontend | http://localhost:5173 |
| API + Swagger | http://localhost:8000/docs |
| PostgreSQL | `localhost:5432` (user/pass/db: `vocabforge`) |

Mặc định cả backend lẫn frontend chạy ở **chế độ dev**: code được mount vào container
nên sửa file là tự reload / HMR. Đổi sang bản build tĩnh:

```bash
VF_BUILD_TARGET=base VF_FE_BUILD_TARGET=prod docker compose up -d --build
```

Cổng bị trùng thì đổi `VF_DB_PORT` / `VF_API_PORT` / `VF_WEB_PORT` trong `.env`.

## Test

```bash
# Trên SQLite tạm, nhanh, không cần Docker
cd backend && pytest

# Trên đúng PostgreSQL sẽ chạy production
docker compose exec -e TEST_DATABASE_URL=postgresql+asyncpg://vocabforge:vocabforge@db:5432/vocabforge_test \
  backend pytest
```

88 test, không có test nào gọi mạng (dùng `MockProvider`). Cần tạo DB test một lần:

```bash
docker compose exec db psql -U vocabforge -d vocabforge -c "CREATE DATABASE vocabforge_test;"
```

## Kiến trúc: hai vòng lặp tách rời

Đây là quyết định thiết kế quan trọng nhất (file 00 mục 4):

| | Vòng REVIEW (fast path) | Vòng AGENT (chạy nền) |
|---|---|---|
| Endpoint | `/api/review/*`, `/api/clusters/*/practice` | `/api/ingestion/*`, `POST /api/lexical-items` |
| Gọi LLM | **KHÔNG BAO GIỜ** | Có, kèm retry + trạng thái job |
| Độ trễ | thuần thuật toán, không I/O ngoài | giây → phút |

Ngoại lệ duy nhất là **production grading**: bắt buộc gọi LLM lúc người dùng đang thao
tác, nên xử lý bằng cách trả `attempt_id` ngay rồi chấm nền — người học đi tiếp thẻ sau
mà không phải chờ. Ràng buộc "review không gọi LLM" được canh bằng test
(`test_review_endpoint_never_calls_llm`).

## Điểm khác biệt so với Anki

- **Lịch ôn theo loại lỗi** (file 02 mục 5): sai chính tả hay sai văn phong **không** bị
  siết lịch như quên nghĩa. Tách lỗi trí nhớ khỏi lỗi sử dụng.
- **Leech không bị ẩn đi**: thẻ quên quá nhiều lần sẽ được Mnemonic Agent viết lại mẹo
  nhớ bằng cách tiếp cận **khác hẳn** (đổi cả kỹ thuật), thay vì suspend im lặng.
- **Đơn vị học là collocation**, không phải từ đơn — Extraction Agent được prompt để ưu
  tiên cụm từ học thuật.
- **Chấm khả năng sản xuất**, không chỉ nhận diện.

## Tài liệu chi tiết

- `backend/README.md` — cấu trúc module, phiên bản FSRS, các chỗ lệch khỏi spec
- `frontend/DESIGN_TOKENS.md` — bảng màu, typography, layout, signature element
