# VocabForge Pro — Mô hình dữ liệu & API Spec

## 1. Schema SQLite (DDL)

```sql
-- ============ USERS & DECKS ============
CREATE TABLE users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    daily_new_word_goal INTEGER DEFAULT 10,  -- ramp-up target, hướng tới 30
    timezone TEXT DEFAULT 'Asia/Ho_Chi_Minh'
);

CREATE TABLE decks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============ CARD CORE ============
-- Một "lexical_item" là đơn vị từ vựng: có thể là từ đơn HOẶC collocation
CREATE TABLE lexical_items (
    id TEXT PRIMARY KEY,
    surface_form TEXT NOT NULL,           -- vd: "have a detrimental effect on"
    item_type TEXT NOT NULL CHECK(item_type IN ('single_word','collocation','phrasal_verb','idiom')),
    ipa TEXT,                              -- phiên âm (chỉ cho single_word)
    cefr_level TEXT,                       -- A2/B1/B2/C1/C2 nếu xác định được
    academic_word_list_sublist INTEGER,    -- nếu thuộc AWL, ghi số sublist
    source_deck_id TEXT REFERENCES decks(id),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Một từ có thể có nhiều nghĩa -> nhiều "sense", mỗi sense là 1 card riêng
CREATE TABLE senses (
    id TEXT PRIMARY KEY,
    lexical_item_id TEXT NOT NULL REFERENCES lexical_items(id),
    definition_en TEXT NOT NULL,
    definition_vi TEXT,
    part_of_speech TEXT,
    register TEXT CHECK(register IN ('academic','neutral','informal')),
    frequency_rank INTEGER                 -- độ phổ biến trong ngữ liệu academic (nếu có)
);

CREATE TABLE example_sentences (
    id TEXT PRIMARY KEY,
    sense_id TEXT NOT NULL REFERENCES senses(id),
    sentence TEXT NOT NULL,
    essay_type TEXT CHECK(essay_type IN ('opinion','discussion','problem_solution','advantage_disadvantage','general')),
    source TEXT CHECK(source IN ('user_reading','agent_generated')),
    generated_by_model TEXT                -- 'deepseek' | 'gemini' | null nếu từ bài đọc thật
);

-- ============ MNEMONIC & CLUSTER (agent-enriched) ============
CREATE TABLE mnemonics (
    id TEXT PRIMARY KEY,
    sense_id TEXT NOT NULL REFERENCES senses(id),
    mnemonic_text TEXT NOT NULL,
    mnemonic_type TEXT CHECK(mnemonic_type IN ('keyword_dual_coding','etymology','story_link')),
    generated_by_model TEXT
);

CREATE TABLE confusion_clusters (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    cluster_label TEXT,                    -- vd: "degree adjectives: significant/substantial/considerable"
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE confusion_cluster_members (
    cluster_id TEXT NOT NULL REFERENCES confusion_clusters(id),
    sense_id TEXT NOT NULL REFERENCES senses(id),
    distinguishing_note TEXT,              -- nghĩa/sắc thái khác biệt so với các từ khác trong cluster
    PRIMARY KEY (cluster_id, sense_id)
);

-- ============ SRS CORE ============
CREATE TABLE cards (
    id TEXT PRIMARY KEY,
    sense_id TEXT NOT NULL REFERENCES senses(id),
    user_id TEXT NOT NULL REFERENCES users(id),
    card_direction TEXT NOT NULL CHECK(card_direction IN ('en_to_vi','vi_to_en','production','cluster_discrimination')),

    -- FSRS-7 state (due_at lưu dạng datetime đầy đủ, không chỉ ngày, vì FSRS-7 hỗ trợ
    -- interval phân số/same-day review nên cần độ chính xác tới giờ/phút)
    state TEXT NOT NULL DEFAULT 'new' CHECK(state IN ('new','learning','review','relearning')),
    stability REAL DEFAULT 0,
    difficulty REAL DEFAULT 0,
    due_at TEXT,
    last_reviewed_at TEXT,
    reps INTEGER DEFAULT 0,
    lapses INTEGER DEFAULT 0,
    is_leech BOOLEAN DEFAULT FALSE,

    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE review_logs (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id),
    reviewed_at TEXT NOT NULL DEFAULT (datetime('now')),
    rating INTEGER NOT NULL CHECK(rating IN (1,2,3,4)),  -- Again/Hard/Good/Easy
    elapsed_days REAL,
    scheduled_days REAL,
    error_type TEXT CHECK(error_type IN (NULL,'meaning','collocation','spelling','register','none'))
);

-- ============ PRODUCTION GRADING ============
CREATE TABLE production_attempts (
    id TEXT PRIMARY KEY,
    card_id TEXT NOT NULL REFERENCES cards(id),
    user_sentence TEXT NOT NULL,
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    -- kết quả chấm (điền sau khi agent trả lời, ban đầu NULL)
    is_correct BOOLEAN,
    error_type TEXT CHECK(error_type IN (NULL,'meaning','collocation','grammar','register','none')),
    feedback_text TEXT,
    graded_by_model TEXT,
    graded_at TEXT
);

-- ============ INGESTION & AGENT JOBS ============
CREATE TABLE ingestion_jobs (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    deck_id TEXT REFERENCES decks(id),
    source_type TEXT CHECK(source_type IN ('pasted_text','url','pdf')),
    raw_text TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','extracting','enriching','done','failed')),
    error_message TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT
);

CREATE TABLE agent_cache (
    cache_key TEXT PRIMARY KEY,             -- hash(agent_name + normalized_input)
    agent_name TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

## 2. API Endpoints (REST)

### Auth & User
```
POST   /api/auth/register
POST   /api/auth/login
GET    /api/users/me
PATCH  /api/users/me/settings          # điều chỉnh daily_new_word_goal
```

### Ingestion (đầu vào bài đọc)
```
POST   /api/ingestion/jobs             # body: {source_type, raw_text|url, deck_id}
GET    /api/ingestion/jobs/{job_id}    # poll trạng thái pending/extracting/enriching/done
GET    /api/ingestion/jobs/{job_id}/candidates   # danh sách từ/cụm agent đề xuất, chờ user duyệt
POST   /api/ingestion/jobs/{job_id}/approve      # body: {selected_lexical_item_ids: []}
```

### Decks & Lexical Items
```
GET    /api/decks
POST   /api/decks
GET    /api/decks/{deck_id}/items
POST   /api/lexical-items                        # thêm thủ công 1 từ/cụm, trigger enrichment agent
GET    /api/lexical-items/{id}
```

### Review (SRS core — fast path, không gọi LLM)
```
GET    /api/review/queue?limit=30      # trả về card đến hạn theo FSRS-7, ưu tiên theo due_at
POST   /api/review/cards/{card_id}/answer   # body: {rating: 1-4}
GET    /api/review/stats                # streak, retention rate, số thẻ due hôm nay
```

### Production Grading (có gọi LLM, async)
```
POST   /api/production/attempts        # body: {card_id, user_sentence} -> trả về attempt_id ngay, status=pending
GET    /api/production/attempts/{id}   # poll cho tới khi graded_at khác NULL
```

### Cluster Discrimination
```
GET    /api/clusters/{cluster_id}
GET    /api/clusters/{cluster_id}/practice   # sinh bài tập chọn từ đúng trong cluster
```

### Analytics
```
GET    /api/analytics/overview          # tổng quan tiến độ
GET    /api/analytics/error-breakdown   # phân loại lỗi hay gặp (meaning/collocation/register...)
GET    /api/analytics/leeches           # danh sách từ leech cần xử lý riêng
```

## 3. Ghi chú thiết kế quan trọng

- **Tách `lexical_item` và `sense`**: một từ như "address" có nghĩa danh từ (địa chỉ) và động từ (giải quyết vấn đề) — đây là 2 sense khác nhau, cần 2 card khác nhau, KHÔNG gộp chung để tránh interference khi ôn tập (đúng nguyên tắc "minimum information" của Anki).
- **`card_direction`**: cho phép cùng 1 sense sinh ra nhiều loại card (nhận diện xuôi/ngược, production, phân biệt cluster) — đây là chỗ để mở rộng độ khó dần theo thời gian, không chỉ dừng ở flashcard 2 mặt.
- **`agent_cache`**: bắt buộc phải có ngay từ đầu, không phải optimization sau này — vì từ vựng academic IELTS có độ trùng lặp rất cao giữa người dùng khác nhau, cache tiết kiệm chi phí LLM đáng kể.
- **`error_type` xuất hiện ở cả `review_logs` và `production_attempts`**: đây là dữ liệu để sau này điều chỉnh lịch ôn theo loại lỗi (spec chi tiết ở file agent).
- **`due_at` phải lưu độ chính xác tới giờ/phút, không chỉ ngày**: vì dùng FSRS-7 hỗ trợ interval phân số cho same-day review (xem file 02), nếu chỉ lưu ngày sẽ mất khả năng phân biệt thứ tự ôn trong cùng một ngày.
