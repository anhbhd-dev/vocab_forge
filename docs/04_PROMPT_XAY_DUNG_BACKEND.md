# Prompt để đưa vào Claude Code — Xây dựng Backend VocabForge Pro

Copy toàn bộ nội dung dưới đây vào Claude Code cùng với 3 file spec đính kèm
(`00_TONG_QUAN_KIEN_TRUC.md`, `01_MO_HINH_DU_LIEU_VA_API.md`, `02_SRS_ENGINE_SPEC.md`,
`03_AI_AGENTS_SPEC_VA_PROMPT.md`) để Claude Code có đầy đủ context trước khi code,
đúng triết lý front-load context bạn đã dùng cho project text-to-video.

---

```
Bạn sẽ xây dựng backend cho VocabForge Pro — một ứng dụng học từ vựng SRS tích hợp AI
agent, dành cho người học IELTS. Tôi đã đính kèm 4 file spec đầy đủ, hãy đọc kỹ toàn bộ
trước khi viết bất kỳ dòng code nào.

STACK BẮT BUỘC:
- FastAPI (Python 3.11+), async/await xuyên suốt
- SQLite qua SQLAlchemy 2.0 (async engine, dùng aiosqlite)
- Pydantic v2 cho toàn bộ request/response schema
- Provider pattern cho LLM (interface chung, implementation riêng cho DeepSeek và
  Gemini) — tham khảo cách tôi đã làm ở project text-to-video, dùng abstract base
  class + factory, KHÔNG hardcode provider cụ thể vào business logic
- Job xử lý bất đồng bộ: dùng FastAPI BackgroundTasks + bảng ingestion_jobs trong
  SQLite để track trạng thái (KHÔNG dùng Celery/Redis ở giai đoạn này, giữ đơn giản)
- FSRS-7: dùng thư viện `fsrs` (py-fsrs) cho phần tính toán lõi — TRƯỚC KHI code, kiểm
  tra version thư viện hiện tại đã hỗ trợ FSRS-7 (fractional interval, 8 tham số) chưa;
  nếu chưa, dùng FSRS-6 làm fallback tạm thời và ghi rõ TODO để nâng cấp sau. Wrap logic
  FSRS trong module srs_engine.py để dễ can thiệp phần mở rộng error_type-aware
  scheduling và dễ swap version sau này.

CẤU TRÚC THƯ MỤC ĐỀ XUẤT:
backend/
├── app/
│   ├── main.py
│   ├── core/
│   │   ├── config.py
│   │   └── db.py
│   ├── models/              # SQLAlchemy models, đúng schema trong file 01
│   ├── schemas/             # Pydantic schemas cho API request/response
│   ├── srs/
│   │   ├── engine.py        # FSRS wrapper + error_type adjustment (theo file 02 mục 6)
│   │   └── leech.py
│   ├── agents/
│   │   ├── base.py          # LLMProvider abstract interface
│   │   ├── providers/
│   │   │   ├── deepseek.py
│   │   │   └── gemini.py
│   │   ├── extraction_agent.py
│   │   ├── context_agent.py
│   │   ├── cluster_agent.py
│   │   ├── mnemonic_agent.py
│   │   ├── production_grading_agent.py
│   │   └── cache.py          # agent_cache lookup/store
│   ├── api/
│   │   ├── auth.py
│   │   ├── decks.py
│   │   ├── ingestion.py
│   │   ├── review.py
│   │   ├── production.py
│   │   ├── clusters.py
│   │   └── analytics.py
│   └── services/
│       └── ingestion_pipeline.py   # orchestration theo file 03 mục 6
└── tests/

YÊU CẦU TRIỂN KHAI CỤ THỂ:

1. Implement CHÍNH XÁC schema SQLite trong file 01 (mục 1) bằng SQLAlchemy models,
   giữ nguyên tên bảng/cột để khớp với API spec.

2. Implement toàn bộ endpoint trong file 01 mục 2. Endpoint review (POST
   /api/review/cards/{card_id}/answer) TUYỆT ĐỐI KHÔNG được gọi bất kỳ LLM API nào —
   đây là fast path thuần thuật toán, xem nguyên tắc tách biệt ở file 00 mục 4.

3. Implement srs/engine.py theo đúng pseudocode ở file 02 mục 6, bao gồm cả phần mở
   rộng error_type-aware adjustment (file 02 mục 5) — đây KHÔNG phải FSRS chuẩn, là
   phần mở rộng riêng của chúng ta, cần code rõ ràng, có comment giải thích lý do mỗi
   nhánh điều chỉnh.

4. Với mỗi agent trong file 03, implement:
   - System prompt COPY CHÍNH XÁC từ spec, không tự ý diễn giải lại
   - Response schema validation bằng Pydantic, nếu LLM trả về JSON không khớp schema
     → retry tối đa 2 lần với prompt nhắc lại yêu cầu format, sau đó raise lỗi rõ ràng
   - Cache lookup TRƯỚC khi gọi LLM (agents/cache.py), cache key = sha256(agent_name +
     normalized_input + target_band)

5. Implement ingestion_pipeline.py orchestrate đúng luồng ở file 03 mục 6: Extraction
   → user approve (KHÔNG tự động enrich hết, chờ endpoint approve) → chạy song song
   Context/Mnemonic/Cluster agent bằng asyncio.gather cho các item đã duyệt.

6. Viết unit test cho srs/engine.py là ưu tiên cao nhất (đây là phần logic quan trọng
   nhất, cần test các case: New→Learning→Review, Review→Relearning khi Again, leech
   detection threshold, error_type adjustment không phá vỡ FSRS core).

7. KHÔNG implement authentication phức tạp (OAuth...) ở giai đoạn này — dùng JWT đơn
   giản với email/password là đủ.

8. Với mỗi file agent, thêm docstring trích dẫn ĐÚNG mục trong file
   03_AI_AGENTS_SPEC_VA_PROMPT.md mà nó implement, để dễ đối chiếu sau này khi cần sửa
   prompt.

Hãy bắt đầu bằng cách outline lại cấu trúc file/module bạn dự định tạo để tôi xác nhận
trước khi bạn viết code đầy đủ, tránh phải sửa lại nhiều sau khi đã viết xong.
```
