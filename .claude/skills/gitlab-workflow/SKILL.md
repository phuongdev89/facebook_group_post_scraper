---
name: gitlab-workflow
description: Quy trình quản lý task trên GitLab bằng glab CLI — tạo Issue, làm trên nhánh feature/issue-N, đổi nhãn, tạo Merge Request. Dùng khi người dùng nói "tạo issue", "chạy workflow", "làm theo quy trình GitLab", "phân việc", hoặc yêu cầu bắt đầu một task mới cần theo dõi.
---

# Quy trình GitLab (glab CLI)

Nhánh đích luôn là `main`. Toàn bộ task/tài liệu quản lý trên GitLab — không tạo file task local, không dùng `./storage/`.

## 1. Tạo Issue

Description CỰC KỲ ngắn gọn, dạng gạch đầu dòng hoặc AC kiểu Gherkin. Không viết văn xuôi.

```bash
glab issue create --title "<tên task ngắn>" --description "<Spec/AC gạch đầu dòng>" --label "To Do"
```

➔ Gửi URL Issue cho người dùng.

## 2. Nhận việc

```bash
glab issue edit <id> --assignee "<dev>" --label-add "In Progress" --label-remove "To Do"
glab issue note <id> --message "🚀 Bắt đầu làm trên branch feature/issue-<id>"
git checkout -b feature/issue-<id>
```

## 3. Làm xong code → chuyển Review

```bash
glab issue edit <id> --label-add "Review" --label-remove "In Progress"
```

Trước khi commit: xóa file test/ảnh/log tạm, file SQLite debug, dọn rác (xem CLAUDE.md).

## 4. Kiểm thử

Dùng skill `verify-and-cleanup`. Kết quả:

- **FAILED** → trả nhãn về In Progress, comment lỗi + bằng chứng:
  ```bash
  glab issue edit <id> --label-add "In Progress" --label-remove "Review"
  glab issue note <id> --message "❌ FAILED: <mô tả lỗi ngắn>"
  ```
- **PASSED** → comment bằng chứng lên Issue:
  ```bash
  glab issue note <id> --message "✅ PASSED: <bằng chứng log/output>"
  ```

## 5. Done + tạo MR

Chỉ làm khi đã PASSED và bằng chứng đã nằm trên Issue.

```bash
glab issue edit <id> --label-add "Done" --label-remove "Review"
git push -u origin feature/issue-<id>
glab mr create --source-branch "feature/issue-<id>" --target-branch "main" --title "Feat: <tên task> (Closes #<id>)" --fill
```

➔ Gửi URL Merge Request cho người dùng.

## 6. DỪNG LẠI

**TUYỆT ĐỐI KHÔNG chạy `glab mr merge` hay `git merge`.** Báo cáo link Issue + link MR + bằng chứng, rồi dừng để người dùng tự review và bấm Merge.
