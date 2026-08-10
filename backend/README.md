# VocabForge Pro — Backend

Backend cho ứng dụng học từ vựng IELTS dùng spaced repetition + lớp AI agent.
Triển khai theo spec trong `../docs/` (files 00–04).

## Chạy

```bash
cd backend
uv venv --python 3.12 ../.venv          # hoặc python -m venv
uv pip install -e ".[dev]"              # hoặc pip install -e ".[dev]"

cp .env.example .env
# điền DEEPSEEK_API_KEY vào .env

uvicorn app.main:app --reload
```

Mở http://127.0.0.1:8000/docs để xem toàn bộ endpoint.

```bash
pytest                                   # 88 test, không gọi mạng (dùng MockProvider)
```

## Nguyên tắc kiến trúc quan trọng nhất

Hai vòng lặp tách rời hoàn toàn (file 00 mục 4):

| | Vòng REVIEW (fast path) | Vòng AGENT (background) |
|---|---|---|
| Endpoint | `/api/review/*`, `/api/clusters/*/practice` | `/api/ingestion/*`, `/api/lexical-items` (POST) |
| Gọi LLM | **KHÔNG BAO GIỜ** | Có |
| Độ trễ | < 10ms, thuần Python | giây–phút, có retry, có trạng thái |

Ngoại lệ duy nhất là **Production Grading** (`/api/production/attempts`): bắt buộc gọi
LLM trong lúc user tương tác, nên xử lý bằng cách trả `attempt_id` ngay
(`status=pending`) rồi chấm nền — user đi tiếp thẻ sau, poll kết quả sau.

Có một test canh giữ ràng buộc này: `test_review_endpoint_never_calls_llm`.

## Cấu trúc

```
app/
├── core/          config, db (async SQLite), security (JWT), time
├── models/        SQLAlchemy — đúng schema file 01
├── schemas/       agent_io.py (I/O của agent) + api.py (REST)
├── srs/
│   ├── engine.py  wrapper FSRS + error_type-aware scheduling  ← logic quan trọng nhất
│   ├── leech.py   ngưỡng leech (file 02 mục 4)
│   └── rampup.py  tăng/giảm từ mới mỗi ngày (file 02 mục 7)
├── agents/
│   ├── base.py      LLMProvider (ABC)
│   ├── factory.py   chọn provider + fallback DeepSeek → Gemini
│   ├── providers/   deepseek.py, gemini.py, mock.py
│   ├── prompts.py   5 system prompt COPY NGUYÊN VĂN từ file 03 + 1 prompt mở rộng
│   ├── runner.py    cache → gọi LLM → parse → validate → retry
│   ├── cache.py     agent_cache (sha256)
│   └── *_agent.py   5 agent trong spec + sense_agent.py (mở rộng)
├── api/           auth, decks, ingestion, review, production, clusters, analytics
└── services/      content_ingestion, ingestion_pipeline, cluster_service,
                   review_service, production_service, leech_service,
                   analytics_service, card_factory, similarity
```

## Những chỗ lệch khỏi spec (và lý do)

### 1. FSRS-6 thay vì FSRS-7 — tạm thời

`py-fsrs` mới nhất trên PyPI là **6.3.2**, chưa có FSRS-7 (`Scheduler._next_interval`
vẫn `round()` về ngày nguyên → chưa có fractional interval, là điểm khác biệt cốt lõi
của FSRS-7). Đây đúng là phương án fallback mà file 02 mục 1 và file 04 cho phép.

Đã chuẩn bị sẵn cho việc nâng cấp:
- version được **pin cứng** `fsrs==6.3.2`;
- toàn bộ FSRS bọc trong `app/srs/engine.py`, hằng số `FSRS_VARIANT` /
  `FSRS_SUPPORTS_FRACTIONAL_INTERVAL` cho biết đang chạy bản nào (`GET /health` cũng trả);
- `due_at` lưu datetime **tới micro-giây** nên same-day review đã hoạt động ngay bây giờ;
- `_fractional_interval_days()` đã tính interval phân số cho nhánh điều chỉnh error_type;
- test bám hành vi, không bám version → nâng cấp không phải viết lại test.

### 2. Agent mở rộng: Sense Agent (`app/agents/sense_agent.py`)

Spec có khoảng trống: Extraction Agent (Agent 1) không trả về định nghĩa, nhưng bảng
`senses` bắt buộc `definition_en NOT NULL`, và Context Agent (Agent 2) lẫn Mnemonic
Agent (Agent 4) đều **nhận `definition_en` làm input**. Thiếu đúng một bước ở giữa.

Sense Agent lấp bước đó, đồng thời trả `needs_mnemonic` — chính là "heuristic từ khó
hình dung" mà file 03 mục 6 nói tới, dùng để chỉ chạy Mnemonic Agent khi cần (tiết kiệm
chi phí). 5 prompt gốc **không bị sửa một ký tự nào** (có test kiểm chứng:
`test_prompts_match_spec_file_verbatim`).

### 3. Bảng `ingestion_candidates`

API spec có `GET /jobs/{id}/candidates` và `POST /jobs/{id}/approve` nhận
`selected_lexical_item_ids`, nhưng `lexical_items` không có chỗ chứa `reason` /
`sentence_context` mà Extraction Agent sinh ra, cũng không có cờ đã-duyệt. Bảng này giữ
đúng phần đó.

### 4. Cột `cards.learning_step`

`py-fsrs` mô hình hoá chuỗi learning steps bằng `Card.step`. Không persist thì mỗi lần
load lại từ DB, thẻ reset về step 0 và không bao giờ tốt nghiệp khỏi Learning đúng cách.
Cột nội bộ engine, không lộ ra API.

### 5. Cột `production_attempts.corrected_sentence` và `users.password_hash`

Cái đầu: output schema của Agent 5 có `corrected_sentence` nhưng bảng file 01 không có
cột chứa. Cái sau: file 04 yêu cầu đăng nhập email/password nhưng schema không có chỗ
lưu hash.

### 6. Trạng thái job đi qua `done` hai lần

`ingestion_jobs.status` chỉ có 5 giá trị, không có "chờ user duyệt":

```
pending → extracting → done      (candidates sẵn sàng, chờ duyệt)
approve → enriching  → done      (đã enrich, cards đã tạo)
```

`GET /api/ingestion/jobs/{id}` trả thêm `candidate_count`, `approved_count`,
`awaiting_approval` để UI phân biệt, không phải nới CHECK constraint.

### 7. Tiền lọc cận nghĩa dùng TF-IDF, không dùng embedding

File 03 gợi ý DeepSeek embedding API hoặc sentence-transformers. DeepSeek hiện không có
endpoint embedding công khai; sentence-transformers kéo theo torch (~2GB) — quá nặng cho
một bước vốn được spec mô tả là "thuật toán rẻ tiền". Nên dùng TF-IDF cosine thuần
Python. `EmbeddingBackend` trong `services/similarity.py` là điểm cắm sẵn: implement
`embed()` rồi truyền vào `group_similar_senses`, không phải sửa cluster service.

### 8. PDF đi qua `url` hoặc base64

Body của `POST /api/ingestion/jobs` trong spec chỉ có `{source_type, raw_text|url}`,
không có multipart upload. PDF scan (không có text layer) báo lỗi rõ ràng là cần OCR —
chưa hỗ trợ.

## Điều chỉnh lịch ôn theo `error_type`

Phần mở rộng ngoài FSRS chuẩn (file 02 mục 5), nằm trọn trong `SRSEngine.process_review`.
Với thẻ `stability=20` bị rating Again:

| error_type | stability mới | state | lapse | hệ quả |
|---|---|---|---|---|
| (không có) | 5.83 | relearning | +1 | — |
| `meaning` | 5.83 | relearning | +1 | ưu tiên card `en_to_vi` trước production |
| `collocation` | 12.0 | review | +1 | hiện thêm ví dụ câu |
| `spelling` | 18.0 | review | 0 | chỉ log thống kê |
| `register` | 20.0 | review | 0 | thêm bài tập phân biệt register |

Nguyên tắc: tách **lỗi trí nhớ** khỏi **lỗi sử dụng**. Ba điều được test canh giữ:
`difficulty` (D của FSRS) **không bao giờ** bị ta chạm vào; khi user được Good/Easy thì
error_type **không** ảnh hưởng gì; và `meaning` bị phạt **đúng bằng** Again trần trụi —
không được nhẹ tay.

## Kiểm tra bằng LLM thật

Sau khi điền `DEEPSEEK_API_KEY` vào `.env`:

```bash
python -m scripts.smoke_llm            # gọi thật 1 lượt mỗi agent, in kết quả
```
