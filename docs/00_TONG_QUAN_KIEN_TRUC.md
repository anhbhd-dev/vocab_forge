# VocabForge Pro — Tổng quan sản phẩm & Kiến trúc hệ thống

## 1. Tầm nhìn sản phẩm

VocabForge Pro là ứng dụng học từ vựng dùng **spaced repetition** làm lõi (kế thừa triết lý Anki: minimum information per card, interval-based scheduling, leech detection), nhưng giải quyết điểm yếu lớn nhất của Anki: **Anki không hiểu nội dung nó đang dạy**.

VocabForge Pro thêm một **lớp AI agent** để:
- Tự động biến bài đọc thật thành thẻ học chất lượng cao (ưu tiên collocation, không phải từ đơn lẻ)
- Sinh ngữ cảnh đa dạng, mnemonic cho từ trừu tượng
- Phát hiện và luyện các nhóm từ cận nghĩa dễ nhầm
- Chấm khả năng *sản xuất* (production) chứ không chỉ *nhận diện* (recognition)
- Điều chỉnh lịch ôn tập dựa trên **loại lỗi**, không chỉ đúng/sai

Đối tượng chính: người học IELTS ở band 5.5–7.5 cần từ vựng học thuật (academic collocations), nhưng kiến trúc đủ tổng quát để mở rộng sang từ vựng chuyên ngành khác sau này.

## 2. Khác biệt so với Anki/Memrise/Duolingo

| Vấn đề | Anki | Memrise/Duolingo | VocabForge Pro |
|---|---|---|---|
| Thuật toán ôn tập | SM-2 cứng | Không rõ ràng, thiên gamification | FSRS-7 (học từ dữ liệu review thật, hỗ trợ interval phân số/same-day review) |
| Nội dung thẻ | Người dùng tự soạn thủ công | Bộ từ có sẵn, không cá nhân hóa | AI trích xuất từ bài đọc thật của người dùng |
| Đơn vị học | Từ đơn | Từ đơn | Ưu tiên **collocation/chunk** |
| Từ trừu tượng | Không hỗ trợ gì thêm | Không hỗ trợ | Agent sinh mnemonic dual-coding |
| Cận nghĩa | Không phân biệt | Không phân biệt | Agent cluster + bài tập phân biệt |
| Đánh giá | Tự chấm (Again/Good/Easy) | Trắc nghiệm | LLM chấm câu tự viết, phân loại lỗi |
| Lịch ôn | Chỉ dựa trên đúng/sai | — | Dựa trên loại lỗi (nghĩa/collocation/văn phong) |

## 3. Tech stack

Kế thừa stack hiện tại của bạn, mở rộng thêm phần agent:

- **Backend**: FastAPI (Python), SQLite (có thể migrate Postgres khi scale)
- **Frontend**: React + TypeScript
- **SRS core**: triển khai **FSRS-7** (bản mới nhất, hỗ trợ interval phân số — phù hợp với ramp-up nhiều thẻ ôn cùng ngày; theo tác giả thuật toán đây là bản "cuối cùng" về kiến trúc nên ít rủi ro lỗi thời). Thư viện tham khảo: `py-fsrs` — cần kiểm tra version đã hỗ trợ FSRS-7 chưa tại thời điểm code, nếu chưa thì dùng FSRS-6 làm fallback tạm. Giữ SM-2 làm fallback phụ cho card cũ/import từ Anki
- **LLM providers**: DeepSeek (chính, rẻ), Gemini (dự phòng/đối chiếu) — theo Provider pattern bạn đã dùng ở project text-to-video
- **Job queue**: cần thêm — dùng **Celery + Redis** hoặc đơn giản hơn là **FastAPI BackgroundTasks + SQLite job table** nếu muốn tránh thêm hạ tầng (khuyến nghị bắt đầu với cách 2, migrate Celery khi cần scale)
- **Cache**: SQLite table `agent_cache` (key = hash(prompt+input), value = JSON response) — tránh gọi lại LLM cho cùng một từ

## 4. Nguyên tắc kiến trúc quan trọng nhất: TÁCH RIÊNG SRS ENGINE VÀ AI AGENT

Đây là quyết định thiết kế quan trọng nhất, tránh lỗi phổ biến khi ghép AI vào app học:

```
┌─────────────────────────────────────────────────────────────┐
│  VÒNG LẶP REVIEW (phải NHANH, chạy offline-first)            │
│                                                                │
│   User thấy thẻ → tự chấm/trả lời → SRS Engine tính interval  │
│   → lưu SQLite → thẻ tiếp theo                                │
│                                                                │
│   KHÔNG gọi LLM trong vòng lặp này (trừ production grading,   │
│   xem mục 4.2)                                                │
└─────────────────────────────────────────────────────────────┘
                              ▲
                              │ đọc dữ liệu đã cache sẵn
                              │
┌─────────────────────────────────────────────────────────────┐
│  VÒNG LẶP AGENT (chạy ASYNC, có thể chậm, chạy nền)           │
│                                                                │
│   Extraction Agent → Context Agent → Mnemonic Agent →         │
│   Cluster Agent → ghi vào DB → sẵn sàng cho vòng review        │
└─────────────────────────────────────────────────────────────┘
```

### 4.1 Vòng Review (fast path)
- Toàn bộ dữ liệu thẻ (nghĩa, ví dụ, mnemonic, cluster cận nghĩa) đã được agent sinh sẵn và lưu trong DB **trước khi** thẻ xuất hiện trong hàng đợi review
- SRS Engine là code thuần Python, không gọi API ngoài, latency < 10ms

### 4.2 Ngoại lệ: Production Grading
- Đây là lúc BẮT BUỘC phải gọi LLM trong lúc user đang tương tác (user viết câu, cần chấm ngay)
- Xử lý: gọi API bất đồng bộ (streaming hoặc loading state rõ ràng trên UI), KHÔNG chặn toàn bộ session review — user có thể tiếp tục thẻ tiếp theo trong khi chờ chấm câu trước, kết quả trả về sau

### 4.3 Vòng Agent (background pipeline)
- Kích hoạt khi: user import bài đọc mới, hoặc user thêm từ thủ công cần enrich
- Chạy như job queue, có retry, có trạng thái (pending/processing/done/failed) hiển thị cho user
- Cache theo từ/cụm — nếu từ đã được xử lý bởi user khác hoặc trước đó, tái sử dụng (tiết kiệm chi phí LLM đáng kể vì nhiều người học IELTS sẽ trùng từ vựng học thuật)

## 5. Các thành phần hệ thống

1. **Content Ingestion** — nhận input (bài đọc dán vào, URL, PDF) → OCR/parse text
2. **Extraction Agent** — trích xuất ứng viên từ/cụm từ đáng học từ text
3. **Enrichment Pipeline** (3 agent con) — Context Agent, Mnemonic Agent, Cluster Agent
4. **SRS Engine** — FSRS-7 scheduler, quản lý card state
5. **Production Grading Agent** — chấm câu/đoạn văn user tự viết
6. **Review UI** — flashcard interface, production writing interface
7. **Analytics** — thống kê tiến độ, loại lỗi hay gặp, streak, retention rate

## 6. Roadmap triển khai đề xuất (MVP → nâng cao)

**Phase 1 (MVP — làm trước):**
- SRS Engine với FSRS-7
- Extraction Agent cơ bản (ưu tiên collocation)
- Context Agent (sinh 2-3 câu ví dụ)
- Review UI dạng flashcard chuẩn

**Phase 2:**
- Mnemonic Agent
- Cluster Agent (phân biệt cận nghĩa)
- Cache layer cho agent

**Phase 3 (nâng cao, tạo lợi thế cạnh tranh thật sự):**
- Production Grading Agent
- Lịch ôn điều chỉnh theo loại lỗi
- Analytics chi tiết theo loại lỗi

Đề xuất bắt đầu Phase 1 trước để có sản phẩm chạy được, tránh over-engineer agent layer khi chưa có SRS core ổn định.
