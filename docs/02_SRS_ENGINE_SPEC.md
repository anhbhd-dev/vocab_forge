# VocabForge Pro — SRS Engine Spec (FSRS-7)

## 1. Vì sao chọn FSRS-7 thay vì SM-2 thuần

SM-2 (thuật toán gốc của Anki/SuperMemo) dùng hệ số cố định (ease factor) được thiết kế thủ công từ thập niên 80s. **FSRS (Free Spaced Repetition Scheduler)** là họ thuật toán mới hơn, dùng mô hình toán học (DSR: Difficulty, Stability, Retrievability) được **fit từ dữ liệu review thật**, cho kết quả retention tốt hơn với cùng số lượng review — đây là lý do Anki đã chuyển sang dùng FSRS làm mặc định từ bản 23.10.

**Chọn cụ thể phiên bản FSRS-7** (không dùng FSRS-6 hay bản cũ hơn), vì các lý do sau (đã kiểm chứng thông tin cập nhật, tính đến giữa 2026):

- FSRS-7 là bản mới nhất, và theo chính tác giả thuật toán (Jarrett Ye), đây được xem là **phiên bản cuối cùng** về mặt kiến trúc — sẽ không có major release tiếp theo trong tương lai gần, nên xây dựng dựa trên nó không lo sớm lỗi thời.
- Khác biệt kỹ thuật quan trọng nhất: FSRS-7 hỗ trợ **interval dạng phân số (fractional)** thay vì chỉ số nguyên như các bản trước — nghĩa là nó dự đoán chính xác xác suất nhớ lại cho **các lần ôn trong cùng một ngày**. Đây là điểm rất khớp với hệ thống ramp-up 30 từ/ngày của VocabForge: khi user học nhiều từ mới trong ngày, nhiều thẻ sẽ cần ôn lại ngay trong buổi, FSRS-6 xử lý case này kém chính xác hơn.
- FSRS-7 dùng đường cong quên (forgetting curve) với 8 tham số tối ưu hóa được, mô hình hóa tốt hơn các trường hợp rìa (very short/very long interval).

**Lưu ý quan trọng về mức độ trưởng thành**: tính đến thời điểm viết spec này, một số app lớn (kể cả Anki) vẫn để FSRS-6 làm mặc định production và chỉ cho FSRS-7 chạy thử nghiệm theo từng deck, vì công thức thượng nguồn của FSRS-7 vẫn đang trong giai đoạn hoàn thiện cộng đồng. Với VocabForge Pro, vì đây là sản phẩm bạn tự build từ đầu (không bị ràng buộc phải tương thích ngược với hàng triệu deck cũ như Anki), dùng thẳng FSRS-7 là hợp lý — nhưng nên: (1) khóa version thư viện cụ thể, (2) viết test kỹ phần optimizer vì ít tài liệu/cộng đồng hơn FSRS-6, (3) theo dõi repo `open-spaced-repetition` để cập nhật nếu có breaking change trước khi "đóng băng" chính thức.

Vì bạn đã có nền SM-2 trong VocabForge, khuyến nghị: **giữ SM-2 làm fallback** (đặc biệt hữu ích nếu sau này muốn cho phép import deck từ Anki cũ), triển khai FSRS-7 làm engine chính — dùng thư viện tham khảo `py-fsrs` (kiểm tra đã hỗ trợ FSRS-7 chưa tại thời điểm code, nếu chưa thì FSRS-6 là fallback tạm thời chấp nhận được trong lúc chờ) làm nền, không cần tự derive công thức từ đầu.

## 2. Khái niệm cốt lõi

- **Difficulty (D)**: độ khó nội tại của thẻ, thang 1-10, cập nhật sau mỗi lần review
- **Stability (S)**: số ngày để retrievability giảm từ 100% xuống 90% — càng cao càng "nhớ lâu"
- **Retrievability (R)**: xác suất nhớ lại đúng tại thời điểm hiện tại, hàm giảm theo thời gian kể từ lần review trước
- **Rating**: 1=Again, 2=Hard, 3=Good, 4=Easy (giữ nguyên thang 4 mức của Anki để user không cần học lại thói quen)

## 3. Card states

```
NEW ──(review đầu tiên)──> LEARNING ──(qua các bước học ban đầu)──> REVIEW
                                                                        │
                                                            rating=Again│
                                                                        ▼
                                                                  RELEARNING
                                                                        │
                                                            (học lại xong)
                                                                        ▼
                                                                     REVIEW
```

- **New**: chưa từng review
- **Learning**: đang trong chuỗi bước học ban đầu (vd: 1 phút → 10 phút → 1 ngày)
- **Review**: đã "tốt nghiệp" learning, interval tính bằng ngày theo FSRS
- **Relearning**: bị quên (rating=Again ở state Review), quay lại chuỗi bước ngắn trước khi vào lại Review

## 4. Leech detection

Thẻ được đánh dấu `is_leech = true` khi:
- `lapses >= 8` (số lần quên liên tục từ trạng thái Review), HOẶC
- Trong 5 lần review gần nhất, có >= 3 lần rating=Again

**Xử lý leech — đây là chỗ khác biệt với Anki (Anki chỉ suspend thẻ):**
Thay vì suspend im lặng, hệ thống:
1. Đánh dấu leech, hiển thị cho user trong `/api/analytics/leeches`
2. Trigger lại **Mnemonic Agent** để sinh mnemonic MỚI (khác cách cũ, vì cách cũ rõ ràng không hiệu quả)
3. Nếu leech tiếp tục sau khi có mnemonic mới → gợi ý user tự thêm ghi chú cá nhân hoặc tạm ẩn thẻ

## 5. Điều chỉnh lịch ôn theo `error_type` (khác biệt cốt lõi so với Anki)

Đây là phần **mở rộng ngoài FSRS chuẩn**, tận dụng dữ liệu `error_type` từ bảng `review_logs`/`production_attempts`:

| error_type | Ý nghĩa | Điều chỉnh |
|---|---|---|
| `meaning` | Nhầm hẳn nghĩa | Giảm interval mạnh (như Again chuẩn), ưu tiên hiện lại card `en_to_vi` cơ bản trước khi cho làm `production` |
| `collocation` | Hiểu nghĩa nhưng sai giới từ/kết hợp từ | Giảm interval vừa phải, ưu tiên hiện thêm ví dụ câu (Context Agent) thay vì chỉ lặp định nghĩa |
| `spelling` | Chỉ sai chính tả, hiểu đúng nghĩa | Gần như không giảm interval (đây không phải lỗi ghi nhớ nghĩa), chỉ log để thống kê |
| `register` | Dùng đúng nghĩa nhưng sai văn phong (quá informal cho academic writing) | Không giảm interval học thuật, nhưng trigger thêm bài tập phân biệt register nếu có |

Nguyên tắc: **không phải mọi lỗi đều "quên" theo nghĩa SRS truyền thống** — tách rời lỗi trí nhớ (memory failure) khỏi lỗi sử dụng (usage failure) để không lãng phí review budget vào việc lặp lại nghĩa mà user đã nhớ rõ.

## 6. Pseudocode luồng xử lý 1 lần review

```python
def process_review(card_id: str, rating: int, error_type: Optional[str] = None):
    card = get_card(card_id)
    old_state = card.state

    # 1. Tính D, S mới theo công thức FSRS (dùng thư viện py-fsrs)
    new_difficulty, new_stability = fsrs_update(
        card.difficulty, card.stability, rating, card.state
    )

    # 2. Điều chỉnh theo error_type (mở rộng ngoài FSRS chuẩn)
    if error_type == "spelling":
        # không phạt nặng như Again chuẩn nếu chỉ sai chính tả
        new_stability = max(new_stability, card.stability * 0.9)

    # 3. Tính interval mới từ retrievability target (mặc định 90%)
    interval_days = fsrs_next_interval(new_stability, target_retrievability=0.9)

    # 4. Cập nhật state machine
    new_state = transition_state(old_state, rating)

    # 5. Leech check
    lapses = card.lapses + (1 if rating == 1 and old_state == "review" else 0)
    is_leech = lapses >= 8 or recent_again_ratio(card_id) >= 0.6

    # 6. Ghi log + update card
    save_review_log(card_id, rating, error_type)
    update_card(card_id, difficulty=new_difficulty, stability=new_stability,
                due_at=now() + interval_days, state=new_state,
                lapses=lapses, is_leech=is_leech)

    if is_leech and not card.is_leech:
        enqueue_job("regenerate_mnemonic", sense_id=card.sense_id)
```

## 7. Ramp-up hệ thống từ mới (đã có trong VocabForge, giữ nguyên logic)

- Bắt đầu thấp (vd: 5-10 từ/ngày), tăng dần theo tuần tới mục tiêu 30 từ/ngày
- Điều kiện tăng: retention rate 7 ngày gần nhất >= 85% VÀ số thẻ due không vượt quá 1.5x số từ mới/ngày hiện tại
- Nếu retention rate < 75% trong 3 ngày liên tiếp → tự động giảm số từ mới/ngày, ưu tiên trả nợ review trước
