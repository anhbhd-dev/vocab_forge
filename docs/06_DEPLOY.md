# Deploy FE và BE tách nhau

Bố cục: **frontend** là site tĩnh (Cloudflare Workers/Pages), **backend** là container
FastAPI + PostgreSQL ở một nhà cung cấp khác. Trình duyệt gọi thẳng từ domain FE sang
domain BE, nên hai thứ phải khớp nhau ở đúng ba chỗ: URL API, CORS, và HTTPS.

## 1. Backend trước, frontend sau

Frontend nhúng URL backend vào bundle **lúc build**, nên phải biết URL backend trước khi
build. Deploy backend trước, lấy domain, rồi mới build FE.

## 2. Backend

Biến môi trường bắt buộc (chi tiết trong `backend/.env.example`):

| Biến | Giá trị | Vì sao |
| --- | --- | --- |
| `DEBUG` | `false` | Bật guard cấu hình + tắt regex CORS cho dải IP nội bộ |
| `JWT_SECRET` | chuỗi ngẫu nhiên ≥32 ký tự | Còn giá trị mẫu là backend **từ chối khởi động** |
| `DATABASE_URL` | `postgresql+asyncpg://...` | Chuỗi nhà cung cấp đưa thường là `postgres://` — phải đổi driver |
| `CORS_ORIGINS` | origin của FE, không có `/` cuối | Thiếu là trình duyệt chặn mọi request |
| `DEEPSEEK_API_KEY` | key thật | |
| `TTS_ENABLED` | `false` nếu không dựng Kokoro | Mặc định trỏ tới service `tts` của docker-compose, deploy lẻ sẽ timeout |

Sinh secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Cổng: image đọc `PORT` nếu nền tảng có cấp, mặc định 8000.

Kiểm tra sau khi deploy — `status` phải là `ok`:

```bash
curl https://api.example.com/health
```

### Hai thứ dễ quên

- **Audio phát âm nằm trên đĩa** (`AUDIO_DIR`, mặc định `/app/audio`). Nền tảng có
  filesystem tạm sẽ xoá sau mỗi lần restart trong khi DB vẫn giữ đường dẫn → audio 404.
  Gắn volume bền, hoặc chấp nhận chạy lại `scripts/backfill_audio.py`.
- **Backend phải chạy HTTPS.** Trang `https://` gọi `http://` bị trình duyệt chặn thẳng
  (mixed content) và lỗi hiện ra chỉ là "Failed to fetch".

## 3. Frontend (Cloudflare Workers)

`VITE_API_BASE_URL` là biến **build-time**, không phải runtime: nó được thay thẳng vào
mã JavaScript lúc `npm run build`. Đặt ở phần *Runtime variables* của Cloudflare sẽ
không có tác dụng gì.

Deploy bằng CLI:

```bash
cd frontend
VITE_API_BASE_URL=https://api.example.com npm run build
npx wrangler deploy
```

Deploy bằng dashboard (Workers Builds nối Git):

- Root directory: `frontend`
- Build command: `npm run build`
- Output directory: `dist`
- **Build variables**: `VITE_API_BASE_URL = https://api.example.com`

Đổi URL backend ⇒ phải build và deploy lại FE.

`frontend/wrangler.jsonc` đặt `not_found_handling: single-page-application` — thiếu nó
thì mở thẳng `/login` hay F5 giữa chừng sẽ ra 404.

## 4. Khi không login được

Mở DevTools, tab Console/Network:

| Triệu chứng | Nguyên nhân |
| --- | --- |
| `[VocabForge] Bản build này chưa có VITE_API_BASE_URL` | Quên đặt biến lúc build |
| Request đi tới `https://<domain-FE>:8000` | Cũng là quên đặt biến (bản build cũ) |
| `blocked by CORS policy` | Origin FE chưa có trong `CORS_ORIGINS`, hoặc có dấu `/` thừa |
| `Mixed Content` | `VITE_API_BASE_URL` đang là `http://` |
| 502/503 từ chính domain BE | Backend chưa chạy — xem `/health` |
