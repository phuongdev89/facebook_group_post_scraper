---
name: verify-and-cleanup
description: Kiểm thử scraper, parser, SQLite deduplication và Telegram alert ở localhost, thu bằng chứng thực tế, đính kèm lên GitLab Issue rồi xóa sạch file tạm / test db. Dùng trước khi báo hoàn thành bất kỳ task nào, hoặc khi người dùng yêu cầu test/kiểm thử/verify.
---

# Kiểm thử & Dọn dẹp

Không được báo PASS / hoàn thành nếu chưa chạy thật và có bằng chứng.

## 1. Chạy thật ở local

Chạy unit tests, e2e parser tests hoặc test script với mock/sample data:

```bash
# Ví dụ: chạy test suite hoặc script test runner
npm test
# hoặc
python -m pytest
```

## 2. Thu bằng chứng

- **Cào/Trích xuất dữ liệu (Scraper/DOM Parser)** → Log bóc tách đúng `post_id`, timestamp, URL bài viết, trích đoạn nội dung từ `m.facebook.com`.
- **Deduplication / SQLite** → Output query kiểm tra bài viết mới được ghi nhận, bài viết cũ/đã tồn tại bị bỏ qua không xử lý trùng.
- **Telegram Notification** → Output response trả về từ Telegram Bot API (HTTP 200 `ok: true`) hoặc preview nội dung alert định dạng chuẩn.
- **Scheduler & Jitter** → Log khoảng cách delay ngẫu nhiên 3–5s giữa các nhóm và chu kỳ chạy lặp.

Nếu không chạy được → nói rõ "chưa verify được vì X (ví dụ: cần cấu hình `.env` hoặc profile cookies)", không suy đoán là đã đúng.

## 3. Đính kèm lên Issue (khi đang chạy quy trình GitLab)

```bash
glab issue note <id> --message "✅ PASSED: <bằng chứng log/output>"
```

hoặc khi lỗi:

```bash
glab issue note <id> --message "❌ FAILED: <mô tả lỗi ngắn>"
```

## 4. Dọn sạch — BẮT BUỘC

Ngay sau khi đẩy bằng chứng lên Issue / báo cáo cho người dùng:

- Xóa toàn bộ script test tạm, file database test `*.test.sqlite`, output dump JSON, log debug đã tạo.
- Kiểm tra lại trước khi commit:

```bash
git status
```

**TUYỆT ĐỐI KHÔNG commit** file credentials (`.env`, `.credentials.local`), browser session cookies / user data dir, database file thật, hay log rác lên repository.
