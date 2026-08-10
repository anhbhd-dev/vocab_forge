# VocabForge Pro — Design tokens

Hướng thiết kế: **"Sổ tay từ vựng"** — giấy, mực, bút dạ, bút đỏ chấm bài.

File 05 (`docs/05_PROMPT_THIET_KE_UI.md`) yêu cầu lưu token system thành file riêng để
mọi component sinh thêm về sau chỉ cần đính kèm file này là giữ được nhất quán. Nguồn
chân lý duy nhất về giá trị màu là `src/index.css` — file này giải thích *vì sao*.

## 1. Bản chất sản phẩm phản ánh trong thiết kế

| Yêu cầu (file 05) | Cách đáp ứng |
|---|---|
| Không gamification kiểu Duolingo | Không huy hiệu, không "level up", không linh vật. Tiến độ buổi ôn là **một vạch mảnh** như nét bút chì gạch lề, không phải progress bar trò chơi. |
| Không lạnh lùng kiểu Anki | Giấy kẻ ô mờ, đường lề đỏ, font hiển thị có cá tính, chuyển động ngắn có chủ đích. |
| Trọng tâm là vòng lặp review | Trang Ôn tập không có sidebar. Một cột hẹp, khoảng trắng rộng, phím tắt Space/1-4. |
| Tôn vinh dữ liệu thật | Stability/retention/error breakdown hiển thị bằng font mono tabular, và **vệt bút dạ** mã hoá stability ngay trên thẻ. |

## 2. Bảng màu

Đặt trong `:root` (sáng) và `.dark` (tối) ở `src/index.css`.

| Token | Tên | Light | Dark | Dùng cho |
|---|---|---|---|---|
| `--paper` | giấy tái chế | `#EFF1EC` | `#12171B` | nền trang |
| `--paper-raised` | trang giấy nổi | `#F7F8F5` | `#1A2128` | thẻ, panel |
| `--ink` | mực xanh đen | `#1C2C3B` | `#E6EBEF` | chữ chính |
| `--graphite` | chì | `#6B7A88` | `#93A4B3` | chữ phụ, chú thích |
| `--rule` | đường kẻ vở | `#D9DDD4` | `#2A333C` | viền, kẻ ô |
| `--highlight` | bút dạ vàng | `#F2D06B` | `#E8C55F` | đang học, cần chú ý |
| `--mint` | bút dạ bạc hà | `#3E9E7A` | `#5FCFA4` | nhớ chắc, đúng |
| `--redpen` | mực đỏ chấm bài | `#C1453B` | `#F08279` | sai nghĩa, lề vở |
| `--violet-pen` | bút tím | `#7A5CC4` | `#A78BFA` | sai kết hợp từ |

**Vì sao giấy ngả xanh xám chứ không phải cream ấm**: cream + serif + accent cam đất là
"default look" số 1 mà file 05 cấm. `#EFF1EC` vẫn đọc ra là giấy nhưng lệch về phía
lạnh, và accent là đỏ mực/bạc hà chứ không phải cam đất.

**Vì sao dark mode không phải đen tuyền**: `#12171B` là mực xanh đen. Đen tuyền
(`#000`) cộng chữ trắng tạo quầng sáng (halation), gây mỏi mắt khi ôn liên tục 20–30
phút — chính là kịch bản dùng của app này. Đây cũng là cách tránh "default look" số 2
(nền đen + một màu neon): các accent ở dark mode đều giảm bão hoà, không có màu neon.

### Mã màu theo `error_type` — nhất quán toàn app

Ẩn dụ bút chấm bài của giáo viên. Dùng ở: badge khi ôn thẻ, viền feedback chấm bài,
cột biểu đồ ở trang Phân tích.

| error_type | Token | Icon (Lucide) | Ý nghĩa |
|---|---|---|---|
| `meaning` | `--err-meaning` (đỏ) | `AlertCircle` | nhầm hẳn nghĩa — nặng nhất |
| `collocation` | `--err-collocation` (tím) | `Link2` | sai giới từ / kết hợp từ |
| `register` | `--err-register` (vàng đậm) | `PenLine` | sai văn phong |
| `grammar` / `spelling` | `--err-grammar` (chì) | `Type` / `SpellCheck` | không phải lỗi về từ mục tiêu |
| `none` | `--err-none` (bạc hà) | `Check` | không lỗi |

Màu **không bao giờ** là kênh thông tin duy nhất: mỗi loại đi kèm icon riêng + nhãn
tiếng Việt, để phân biệt được khi in đen trắng hoặc với người mù màu.

### Nút rating

`--rate-again` (đỏ) · `--rate-hard` (vàng đậm) · `--rate-good` (bạc hà) · `--rate-easy`
(xanh mực). Giữ thứ tự 4 mức của Anki để người dùng cũ không phải học lại thói quen.

## 3. Typography

| Vai trò | Font | Ghi chú |
|---|---|---|
| Hiển thị | **Bricolage Grotesque Variable** | Chỉ dùng cho từ vựng chính + tiêu đề. Có cá tính, cố ý không phải grotesk trung tính mặc định. |
| Thân bài | **Inter Variable** | Đọc dài không mỏi. |
| Số liệu | **JetBrains Mono Variable** | Class `.tnum` + `font-variant-numeric: tabular-nums` — cột thống kê không nhảy khi số đổi. |

Self-host qua `@fontsource-variable/*` (import trong `index.css`), **không** gọi Google
Fonts CDN lúc chạy: app dùng hằng ngày, không nên phụ thuộc bên thứ ba và không nên rò
thông tin người dùng sang CDN.

## 4. Layout

**Trang Ôn tập** (quan trọng nhất) — "một trang sổ tay":
- Một cột căn giữa `max-w-2xl`, không sidebar.
- `.paper-margin`: đường lề dọc màu đỏ mực bên trái thẻ — **một** đường có chức năng
  (mốc bắt đầu nội dung), không phải lưới hairline trang trí (default look số 3).
- Số thẻ ở góc phải như số trang: `3/24`.
- Tiến độ là vạch 1px chạy ngang phía trên.

**Dashboard** — "trang mở đầu của cuốn sổ": việc hôm nay → 4 ô ghi chú số liệu →
ramp-up → phân bố trạng thái thẻ + từ khó.

Nền trang dùng `.paper-grid` (kẻ ô 28px, độ mờ thấp). **Không** dùng kẻ ô bên trong
thẻ đang đọc — nền có hoạ tiết phía sau chữ làm giảm tốc độ đọc.

## 5. Signature element — "vệt highlight bút dạ"

`src/components/HighlighterSweep.tsx`.

Khi lật thẻ, từ vựng được tô bằng một vệt bút dạ quét ngang (Framer Motion, 420ms).
Vệt **không phải trang trí** — hình dạng của nó là cách app này biểu diễn tiến trình
ghi nhớ của một từ:

| stability | Vệt |
|---|---|
| 0 (từ mới) | mảnh, ngắt quãng, vàng |
| ~7 ngày | liền, dày hơn, vàng ngả xanh |
| 30+ ngày | đầy, màu bạc hà |

Độ trưởng thành tính theo thang log (`log10(1+S) / log10(31)`): khác biệt giữa 1 và 7
ngày đáng kể hơn nhiều so với giữa 60 và 90 ngày, thang tuyến tính sẽ làm mọi thẻ chín
trông giống hệt nhau.

Biến thể `SweepBar` (chỉ vệt, không chữ) dùng trong danh sách và ô thống kê, để
signature element xuất hiện nhất quán ở mọi cấp độ của app.

## 6. Chuyển động

Framer Motion, dùng tiết chế — chỉ 3 chỗ:
1. Vệt bút dạ khi lật thẻ (420ms).
2. Thẻ vào/ra khi chuyển câu (280ms, trượt lên 10px).
3. Danh sách ứng viên khi nhập bài (stagger tối đa 300ms).

Easing chung `cubic-bezier(0.22, 1, 0.36, 1)`. Toàn bộ tôn trọng
`prefers-reduced-motion` (qua `useReducedMotion` + media query trong `index.css`).

## 7. Accessibility

- Tương phản: `--ink` trên `--paper` ≈ 13:1; `--graphite` trên `--paper` ≈ 4.8:1 (đạt
  AA cho text thường). Dark mode tương đương.
- Focus ring dùng `--ring` (bạc hà), luôn thấy rõ — app này dùng bàn phím nhiều
  (Space lật thẻ, 1–4 chấm điểm).
- Mọi icon trang trí có `aria-hidden`; icon mang thông tin có `aria-label`.
- Component nền là shadcn/ui trên Radix primitives nên hành vi bàn phím / ARIA của
  Tabs, Dialog, Progress đã đúng chuẩn.
