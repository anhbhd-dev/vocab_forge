# Prompt để tạo Design System cho VocabForge Pro

Dùng prompt này với Claude (bật khả năng tạo artifact/frontend) hoặc Claude Code khi
bắt đầu phần frontend React + TypeScript. Prompt được viết để tránh 3 "default" UI mà
AI hay tạo ra (nền cream + serif + cam đất; nền đen + accent xanh chuối/đỏ tươi; layout
kiểu báo in hairline) — ép ra một hướng thiết kế thực sự gắn với bản chất của việc học
từ vựng lặp lại ngắt quãng.

---

```
Tôi cần thiết kế một design system hoàn chỉnh cho VocabForge Pro — ứng dụng học từ vựng
tiếng Anh học thuật (chuẩn bị IELTS) dùng spaced repetition, có tích hợp AI agent để
sinh mnemonic, ví dụ câu, và chấm bài viết.

BẢN CHẤT SẢN PHẨM cần phản ánh trong thiết kế:
- Đây KHÔNG phải app "vui nhộn gamification" kiểu Duolingo (không cú mèo, không huy
  hiệu rực rỡ, không progress bar kiểu trò chơi trẻ em) — người dùng mục tiêu là người
  học nghiêm túc chuẩn bị thi IELTS, cần cảm giác tập trung, đáng tin cậy, "học thật".
- Nhưng cũng KHÔNG phải Anki (giao diện chức năng thuần túy, lạnh lùng, giống phần mềm
  thập niên 2000) — cần cảm giác hiện đại, được chăm chút, vì đây là lợi thế cạnh tranh.
- Trọng tâm trải nghiệm là VÒNG LẶP REVIEW THẺ (flashcard) — đây là màn hình người dùng
  nhìn thấy hàng trăm lần mỗi ngày, phải cực kỳ thoải mái cho mắt, không mỏi khi dùng
  liên tục 20-30 phút, và tạo được cảm giác "tiến bộ đang tích lũy" theo thời gian mà
  KHÔNG cần dùng ngôn ngữ trò chơi.
- Có yếu tố dữ liệu/thống kê thật (retention rate, stability curve của từ, error
  breakdown) — đây là điểm khác biệt kỹ thuật thật sự, nên thiết kế cần biết tôn vinh dữ
  liệu này một cách rõ ràng, không giấu nó trong một tab "stats" hời hợt.

CHỦ ĐỀ/CHẤT LIỆU nên khai thác (chọn một hướng, đừng trộn lẫn tất cả):
- Ẩn dụ về "củng cố trí nhớ theo thời gian" (đường cong stability/retrievability của
  FSRS-7 là một artifact thị giác đẹp và có thật, không phải trang trí giả — có thể là
  signature element)
- Ẩn dụ về ngôn ngữ học thuật/academic (không sến kiểu "thư viện cổ điển", mà theo
  hướng tài liệu nghiên cứu hiện đại, typography chính xác, cảm giác precision)
- Tuyệt đối tránh: hình ảnh sách vở/mũ tốt nghiệp/bút chì kiểu clip-art, tránh
  illustration trẻ con

YÊU CẦU KỸ THUẬT:
- React + TypeScript, Tailwind CSS (chỉ dùng utility class chuẩn, không cần compiler
  tùy chỉnh)
- Cần hoạt động tốt ở cả light/dark mode (người dùng sẽ ôn tập vào nhiều thời điểm
  trong ngày, kể cả buổi tối)
- Component quan trọng nhất cần thiết kế trước: (1) Flashcard review component (mặt
  trước/sau, nút rating 4 mức Again/Hard/Good/Easy), (2) Dashboard hiển thị due cards +
  streak + retention rate, (3) Production writing input với feedback từ AI hiển thị
  theo error_type (meaning/collocation/register/grammar — mỗi loại nên có mã màu riêng
  nhất quán xuyên suốt app), (4) Cluster discrimination exercise (chọn từ đúng trong
  nhóm cận nghĩa)
- Đảm bảo contrast đạt chuẩn accessibility, vì đây là app dùng lâu dài mỗi ngày

QUY TRÌNH LÀM VIỆC:
1. Trước khi thiết kế, hãy brainstorm ngắn gọn: palette (4-6 màu có mã hex cụ thể, đặt
   tên), typography (2-3 font cho display/body/data — ưu tiên font có chữ số rõ ràng,
   dễ đọc vì có nhiều thống kê số liệu), layout concept, và MỘT signature element duy
   nhất mà toàn bộ app sẽ được nhớ tới.
2. Tự phản biện: nếu bất kỳ phần nào trong plan giống với thiết kế AI mặc định (nền
   cream+serif+cam đất, hoặc nền đen+accent chói, hoặc layout báo in hairline), hãy đổi
   hướng và giải thích tại sao hướng mới hợp với VocabForge Pro hơn.
3. Chỉ sau khi plan được chốt, mới bắt đầu code component theo đúng plan.

Hãy trình bày plan thiết kế (token system) trước để tôi duyệt, sau đó mới build
component.
```

---

## Ghi chú thêm khi dùng prompt này

- Nếu dùng trực tiếp trong Claude.ai (không phải Claude Code), Claude sẽ tự áp dụng
  nguyên tắc thiết kế tránh 3 "default look" nói trên khi tạo artifact — bạn không cần
  lặp lại chi tiết kỹ thuật này, chỉ cần đảm bảo phần "bản chất sản phẩm" ở trên đủ rõ
  để tránh bị rơi vào giao diện học tập rập khuôn.
- Khi đã có token system (màu, font, layout) được chốt, hãy lưu nó thành một file riêng
  `DESIGN_TOKENS.md` trong repo, tương tự cách bạn front-load spec cho Claude Code —
  mọi lần sinh thêm component mới về sau chỉ cần đính kèm file này để giữ nhất quán,
  không cần lặp lại toàn bộ prompt gốc.
