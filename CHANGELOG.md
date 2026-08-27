# Nhật Ký Thay Đổi (Changelog)

Tất cả những thay đổi, cải tiến và bản sửa lỗi của dự án **Facebook Post & Comment Scraper AI** được ghi nhận chi tiết tại đây.

---

## [1.0.4] - 2026-08-27

### ✨ Tính Năng Mới (Added)
- **Xem Trước Ảnh & Video Trực Tiếp Trong Hộp Thoại Chi Tiết Bài Viết**:
  - Hiển thị thumbnail ảnh và video kích thước nhỏ (110×88px) ngay trong dialog Chi tiết bài viết.
  - Tải thumbnail bất đồng bộ trên luồng nền — giao diện không bị đơ trong lúc chờ ảnh tải về.
  - Bấm vào thumbnail bất kỳ để mở URL gốc bằng trình duyệt mặc định của hệ thống.
  - Video hiển thị biểu tượng 🎬 kèm thumbnail nếu có; ảnh hiển thị trực tiếp từ URL CDN của Facebook.
- **Hệ Thống Log File Thay Thế Log SQLite**:
  - Log hoạt động ứng dụng được ghi vào `~/.facebook-notification/access.log`.
  - Log lỗi được ghi riêng vào `~/.facebook-notification/error.log`.
  - Giảm đáng kể kích thước file SQLite, cải thiện hiệu năng ghi đọc DB.
- **Xuất Chẩn Đoán Dạng ZIP Kèm Log File**:
  - Nút "Gửi phân tích cho Dev" xuất file `.zip` gồm `access.log`, `error.log` và `database_dump.sql` (trừ bảng settings chứa thông tin nhạy cảm).
  - Hỏi nơi lưu file qua hộp thoại hệ thống trước khi xuất.

### 🛠 Cải Tiến & Tối Ưu (Changed)
- **Cào Bình Luận Song Song (`ThreadPoolExecutor`)**:
  - Trong mỗi lượt cào một nhóm, toàn bộ bình luận của các bài viết được tải **đồng thời** tối đa 4 luồng song song thay vì tuần tự từng bài.
  - Tốc độ cào tổng thể tăng đáng kể khi nhóm có nhiều bài viết.
  - `fetch_posts` vẫn serialize (do `group_scraper` dùng global state) — an toàn tuyệt đối, không race condition.
- **Bắt Lỗi An Toàn Hơn Khi Phân Tích Dữ Liệu GraphQL**:
  - Thêm hàm `_safe(*keys)` để duyệt chuỗi dict lồng nhau mà không bao giờ gặp `AttributeError: 'NoneType' object has no attribute 'get'`.
  - Áp dụng cho toàn bộ các hàm `extract_group_name`, `extract_creation_time`, `extract_comment_count`, `extract_post_data` trong `group_scraper.py`.
  - Lỗi parse đơn lẻ không còn làm crash toàn bộ luồng cào.

### 🐛 Sửa Lỗi (Fixed)
- Sửa lỗi `❌ Lỗi cào dữ liệu: 'NoneType' object has no attribute 'get'` xảy ra khi Facebook trả về `null` trong một số trường JSON của GraphQL response.
- Sửa lỗi dialog Chi tiết bài viết không hiển thị ảnh/video (chỉ hiện link text) — đã thay bằng thumbnail có thể click.
- Sửa hàm xuất chẩn đoán: định dạng file đầu ra đổi từ `.diagnose` (SQL text) sang `.zip` (nén kèm log).

---

## [1.0.3] - 2026-08-20

### ✨ Tính Năng Mới (Added)
- **Tích hợp Nhà cung cấp OpenAI & Tương thích (OpenAI-Compatible Providers)**:
  - Hỗ trợ kết nối tới OpenAI chính hãng và toàn bộ các nền tảng LLM tương thích (OpenRouter, DeepSeek, Groq, Ollama, LM Studio, vLLM, Together AI, v.v.).
  - Tự động chuẩn hóa Base URL và endpoint `/chat/completions`, tự động xử lý tiền tố và hậu tố URL.
- **Bảng Quản Lý Model Checkbox Cho OpenAI (`OpenAIModelSelectorWidget`)**:
  - Giao diện dạng lưới 2 cột cuộn mượt mà tương tự bộ chọn model Gemini.
  - Tự động sắp xếp danh sách model theo thứ tự chữ cái A-Z và gom nhóm các model tư duy (Thinking) về cuối.
  - Thanh nhập nhanh **`+ Thêm model tùy chỉnh`** hỗ trợ thêm một hoặc nhiều model cùng lúc (phân tách bằng dấu phẩy).
  - Nút **`🗑 Xóa tất cả`** dành riêng cho chế độ OpenAI để làm sạch toàn bộ danh sách khi cần.
  - Các công cụ chọn nhanh: **Chọn tất cả**, **Bỏ chọn**.
- **Tự Động Tải Danh Sách Model Từ API (`fetch_openai_models_from_api`)**:
  - Tự động truy vấn endpoint `/models` từ bất kỳ Base URL nào.
  - Tự động lọc bỏ các model không phải LLM hội thoại (embeddings, whisper, tts, dall-e, vision, moderation, v.v.).
- **Kiểm Tra Thực Tế Bất Đồng Bộ Không Treo Giao Diện (`TestAIModelsWorker`)**:
  - Chạy trên luồng nền `QThread` riêng biệt, giao diện luôn mượt mà trong suốt quá trình kiểm tra.
  - Hiệu ứng xoay và tiến trình trực tiếp: Model đang kiểm tra lập tức hiển thị `⏳ model_name (Đang test...)` kèm màu tím sáng.
  - Nút **`⏹ Dừng test`** động: Nút bắt đầu test tự động đổi sang màu đỏ `⏹ Dừng test (i/N)`, cho phép người dùng hủy bỏ quá trình kiểm tra bất kỳ lúc nào.
- **Hệ Thống Chỉ Báo Trạng Thái Màu Sắc Trực Quan**:
  - 🟡 **Màu Vàng / Hổ phách (`#D97706`)**: Model mới thêm vào hoặc vừa fetch từ API (Chưa kiểm tra).
  - 🟣 **Màu Tím / Indigo (`#4F46E5`)**: Model đang được kiểm tra trực tiếp.
  - 🟢 **Màu Xanh lá cây (`#047857`)**: Model đã kiểm tra qua API thành công, trả về JSON thuần hợp lệ (hiển thị `model_name ✓`).
  - 🔴 **Màu Đỏ (`#DC2626` / `#EF4444`)**: Model gặp lỗi API hoặc thuộc dòng Thinking / Reasoner (tự động loại trừ và vô hiệu hóa).

### 🛠 Cải Tiến & Tối Ưu (Changed)
- **Hỗ Trợ Phản Hồi Server-Sent Events (SSE) Streaming (`extract_chat_completion_response`)**:
  - Tự động ghép nối các chunk `data: {"id":...}` thành chuỗi hoàn chỉnh khi kết nối qua các proxy/gateway có bật SSE Stream.
  - Luôn gửi kèm `"stream": False` trong payload request để ưu tiên nhận JSON trực tiếp.
- **Bộ Phân Tích JSON Siêu Bền Bỉ (`parse_json_from_response`)**:
  - Tự động bóc tách và loại bỏ khối `<think>...</think>` / `<reasoning>...</reasoning>`.
  - Hỗ trợ khôi phục JSON khi thiếu đóng ngoặc nhọn, xử lý dấu phẩy thừa (trailing commas), chuỗi chứa ký tự xuống dòng chưa escape (`strict=False`).
- **Cơ Chế Fallback Role User**: Tự động chuyển đổi từ `role: system` sang gộp vào `role: user` nếu model không hỗ trợ system prompt (như một số dòng model o1/o3 hoặc custom proxy).

### 🐛 Sửa Lỗi (Fixed)
- Sửa lỗi văng `TypeError: verify_single_model_pure_json() unexpected keyword argument 'model'`.
- Sửa lỗi hiển thị nguyên chuỗi thẻ HTML `<span>` và `<s>` trên văn bản của checkbox Qt.
- Sửa lỗi `JSONDecodeError: Line 1` khi phản hồi từ proxy bắt đầu bằng `data: {"id":...`.
- Bổ sung 56 bài kiểm thử tự động (Unit Tests) với độ bao phủ toàn diện từ Core Analyzer, SQLite Repository, Worker Threads đến Giao diện PyQt6.

---

## [1.0.2] - 2026-08-18

### ✨ Tính Năng Mới (Added)
- **Tự Động Lấy Danh Sách Nhóm Đã Tham Gia Qua Cookie**:
  - Hỗ trợ đa định dạng Cookie đầu vào: Chuỗi Cookie thô, lệnh cURL copy từ DevTools, hoặc mảng JSON.
  - Tự động trích xuất token bảo mật `fb_dtsg` và đồng bộ nhóm qua mbasic + desktop GraphQL.
- **Bộ Lọc & Tìm Kiếm Nhóm Thời Gian Thực (Real-time Search Filter)**:
  - Lọc tức thì theo tên nhóm, URL, hoặc ID nhóm.
  - Hỗ trợ tiếng Việt không dấu (gõ `lap trinh` tự động khớp `Lập Trình Python`).
- **Hộp Thoại Quản Lý Nhóm Mở Rộng (`GroupManagerDialog` & `GroupSelectDialog`)**:
  - Hỗ trợ phóng to giao diện, dán hàng loạt link nhóm (Batch Paste), chọn nhanh theo nhóm đang lọc, và đảo chọn.

---

## [1.0.1] - 2026-08-15

### ✨ Tính Năng Mới (Added)
- **Hệ Thống Lưu Trữ SQLite & Khử Trùng Lặp**:
  - Bảng cơ sở dữ liệu lưu trữ bài viết, bình luận, và lịch sử phân tích AI.
  - Cập nhật bình luận mới cho bài viết cũ mà không ghi đè dữ liệu.
- **Thông Báo Telegram Đa Định Dạng**:
  - Gửi thông báo tức thì khi phát hiện bài viết khớp từ khóa / AI phân tích phù hợp.
  - Định dạng thông báo HTML chi tiết với link bài viết, trích dẫn chứng minh, và lý do AI đánh giá.

---

## [1.0.0] - 2026-08-10

### 🚀 Khởi Tạo Dự Án (Initial Release)
- Thu thập dữ liệu bài viết và bình luận Facebook bằng thuần thư viện `requests` (không dùng Selenium/Browser).
- Giao diện người dùng đồ họa bằng PyQt6 với hệ thống 4 Tab chuyên biệt.
- Tích hợp Google AI Studio (Gemini) phân tích bài viết tự động.
- Hỗ trợ Proxy xoay vòng và cơ chế Retry với Exponential Backoff.
