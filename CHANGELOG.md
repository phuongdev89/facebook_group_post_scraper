# Nhật Ký Thay Đổi (Changelog)

Tất cả những thay đổi, cải tiến và bản sửa lỗi của dự án **Facebook Post & Comment Scraper AI** được ghi nhận chi tiết tại đây.

---

## [1.0.7] - 2026-08-27

### ✨ Tính Năng Mới & Kiến Trúc Đa Luồng (Added)
- **Quét Đa Luồng Nhóm Song Song (`Luồng cào: 1-10`)**:
  - Hỗ trợ chọn số luồng cào nhóm từ 1 đến 10 thông qua Dropdown tinh gọn, cho phép cào đồng thời nhiều nhóm Facebook độc lập với tốc độ vượt trội.
  - Tách rời hoàn toàn các tiến trình: **Scraper** (cào dữ liệu), **AI Analyzer** (lắng nghe database và phân tích tự động), và **Telegram Dispatcher** (lắng nghe database và gửi thông báo tức thì).
- **Quy Tắc Thiết Lập Số Lượng Bình Luận Cần Cào (`Cmt tối thiểu`)**:
  - `0 (Mặc định)`: Không cào bình luận (chỉ cào bài viết, tốc độ quét nhanh nhất, tiết kiệm băng thông và token).
  - `-1`: Cào **TẤT CẢ** bình luận và phản hồi của mỗi bài viết.
  - `> 0 (ví dụ 5, 20...)`: Cào tối thiểu/tối đa $N$ bình luận cho mỗi bài viết. Nếu bài viết có ít hơn $N$ bình luận thì vẫn cào bài viết đó và lấy toàn bộ bình luận hiện có, không bỏ qua bài viết.
- **Bộ Lọc Từ Khóa Logic Chuyên Sâu & Diễn Giải Tiếng Việt (`KeywordFilterDialog`)**:
  - Hỗ trợ đầy đủ toán tử Boolean `AND`, `OR`, `NOT` và biểu thức lồng dấu ngoặc `()`.
  - Hộp thoại cấu hình phóng to toàn màn hình với 2 chế độ: **🧱 Dựng điều kiện trực quan (Visual Rule Builder)** và **✍️ Tự nhập biểu thức (Raw Expression)**.
  - Hỗ trợ toán tử nối nhóm (`HOẶC (OR)`, `VÀ (AND)`, `VÀ KHÔNG CHỨA (AND NOT)`) từ Nhóm 2 trở đi.
  - Chuyển đổi 2 chiều thông minh, tự động bóc tách toán tử ra khỏi ô nhập text từ khóa và diễn giải ý nghĩa bằng tiếng Việt tự nhiên thời gian thực.
- **Lọc Mốc Thời Gian Bài Viết (Cutoff Timestamp)**:
  - Chọn nhanh 1-7 ngày trước hoặc tùy chỉnh qua DateTimePicker, tự động dừng phân trang khi bài viết vượt quá mốc thời gian yêu cầu.
- **Trợ Giúp Trực Quan (Nút `?` Tooltip & Modal Hướng Dẫn)**:
  - Bổ sung nút `?` cạnh **Cmt tối thiểu** và **Luồng cào** giúp người dùng tra cứu nhanh quy tắc và khuyến nghị sử dụng.

### 🛠 Cải Tiến Giao Diện & Tối Ưu Diện Tích (Changed)
- Toàn bộ 6 tham số quét (Bài/nhóm, Cmt tối thiểu, Luồng cào, Thời gian, Lặp vô hạn, Nghỉ) được sắp xếp trên 1 hàng ngang duy nhất.
- Bỏ nút mũi tên lên xuống trên các ô số, hỗ trợ nhập số trực tiếp từ bàn phím.
- Thu gọn chiều cao khung nhật ký hoạt động (Logs) xuống còn 1/4, mở rộng tối đa không gian cho Danh sách nhóm Facebook (`GroupListWidget`) tự động co giãn theo kích thước cửa sổ.

### 🐛 Sửa Lỗi (Fixed)
- Sửa lỗi `'NoneType' object has no attribute 'get'` trong `comment_scraper.py` bằng hàm điều hướng an toàn `_safe()`.

---

## [1.0.6] - 2026-08-27

### ✨ Tính Năng Mới & Khử Trùng Lặp AI (Added)
- **Bổ Sung Cột `comment_id` & Khử Trùng Lặp Phân Tích AI (`ai_analyses`)**:
  - Thêm cột `comment_id TEXT` vào bảng `ai_analyses` trong SQLite kèm tự động Migration kiểm tra schema và tạo Index tối ưu `idx_ai_analyses_post_comment`.
  - Phân định rõ nguồn khớp: Lưu `comment_id` tương ứng khi từ khóa khớp từ bình luận hoặc phản hồi (`reply_id`), đồng thời vẫn lưu đầy đủ `post_id`.
  - Xây dựng cơ chế kiểm tra chống trùng lặp `ai_analysis_exists(post_id, comment_id)`:
    - Nếu `comment_id` là `NULL` / rỗng (khớp bài viết gốc): Kiểm tra tồn tại theo `post_id`.
    - Nếu `comment_id` có giá trị (khớp bình luận / phản hồi): Kiểm tra tồn tại theo cả `post_id` và `comment_id`.
  - Tích hợp kiểm tra trước khi gọi API AI trong `ScraperThread`, `CommentUpdateWorker` và `AIAnalysisWorker`: Bỏ qua các bài viết/bình luận đã phân tích trước đó, tiết kiệm triệt để Token API AI và loại bỏ hoàn toàn cảnh báo Telegram trùng lặp.
  - Hiển thị `Comment / Reply ID` và `Nguồn khớp` trực quan trong hộp thoại **Chi tiết bài viết** (`PostDetailDialog`) và tooltip tại bảng Lịch sử phân tích.

### 🛠 Cải Tiến & Chuẩn Hóa Cấu Hình (Changed)
- **Chuẩn Hóa Nhập Cookie JSON & Xử Lý Xóa Trắng (`CookieDialog`)**:
  - Bắt buộc chuỗi Cookie nhập vào phải là định dạng JSON hợp lệ (xuất từ tiện ích *Cookie-Editor* hoặc *J2Team Cookies* bằng tính năng **Export as JSON**).
  - Tự động phát hiện và hiển thị hộp thoại cảnh báo hướng dẫn người dùng khi nhập nhầm chuỗi text phân cách chấm phẩy cũ (`c_user=...; xs=...`).
  - Hỗ trợ xóa hoàn toàn Cookie: Người dùng chỉ cần xóa trắng ô nhập Cookie và bấm *Lưu cấu hình*, hệ thống sẽ tự động xóa sạch `cookie_string`, `cookie_raw_json`, `fb_dtsg` trong SQLite và reset toàn bộ cache `COOKIES` của các module cào.

### 🐛 Sửa Lỗi (Fixed)
- **Tương Thích Toàn Diện Python 3.10+ / 3.13 (`src/utils/compat.py`)**:
  - Bổ sung module tương thích `compat.py` tự động ánh xạ `collections.Callable = collections.abc.Callable` (và các abstract class tương tự) trước khi nạp các thư viện kế thừa như `pyreadline` / `seleniumbase`.
  - Sửa dứt điểm lỗi `AttributeError: module 'collections' has no attribute 'Callable'` khi chạy chức năng lấy nhóm bằng trình duyệt hoặc chạy bộ kiểm thử.

---

## [1.0.5] - 2026-08-27

### ✨ Tính Năng Mới (Added)
- **Ghi Log Thời Gian Thực (`RealtimeFileHandler`)**:
  - Xây dựng `RealtimeFileHandler` với cơ chế flush bộ đệm và gọi `os.fsync(fileno)` ngay lập tức trên từng dòng log.
  - Người dùng và nhà phát triển có thể mở xem trực tiếp `access.log` và `error.log` bất kỳ lúc nào trong quá trình quét mà không cần đợi kết thúc phiên quét.
  - Tự động nhận diện các bản ghi lỗi/cảnh báo (`❌`, `🛑`, `Lỗi`, `Exception`, `Error`, v.v.) để phân luồng đồng thời vào cả `error.log` và `access.log`.
  - Các worker chạy ngầm (`ScraperThread`, `CommentUpdateWorker`, `GroupFetchWorker`, `AIWorker`, `TelegramWorker`) ghi log trực tiếp xuống file trong thread nền, tránh nghẽn luồng giao diện chính.
- **Bộ Nhận Diện Thương Hiệu (Favicon & Application Icon)**:
  - Thiết kế bộ icon nhận diện cao cấp phong cách Facebook Blue + AI Radar Lens & Smart Beacon (đầy đủ định dạng SVG, PNG 512x512 và multi-size Windows ICO `16x16` đến `256x256`).
  - Tự động tích hợp vào cửa sổ Desktop App (`QMainWindow`, `QApplication`), thanh Taskbar, các Dialogs con và tài liệu web `guides/index.html`.
  - Tích hợp icon vào file `.exe` PyInstaller và bộ cài đặt Inno Setup (`setup.iss`).
- **Sắp Xếp Dữ Liệu Linh Hoạt Qua Tiêu Đề Bảng (Click Thead Sort A-Z / Z-A)**:
  - Cho phép người dùng bấm vào bất kỳ tiêu đề cột nào của bảng **Dữ liệu cào** (Tab 2) và **Lịch sử phân tích** (Tab 3) để sắp xếp tăng dần hoặc giảm dần kèm chỉ báo mũi tên trực quan (▲ / ▼).
  - Tích hợp lớp `SmartTableWidgetItem` tự động so sánh số tự nhiên đối với STT, Post ID, Số lượng bình luận và Thời gian đăng bài.

- **Cải Tiến Trình Cập Nhật Tự Động OTA (Tải Trực Tiếp `.exe` & Cài Đặt 1-Click)**:
  - Tải trực tiếp tệp thực thi bản vá/bộ cài (`FacebookNotification_Patch_vX.X.X.exe` hoặc `Setup_vX.X.X.exe`), giữ nguyên đuôi `.exe` thay vì lưu nhầm dạng `.zip`.
  - Sau khi tải xong, phần mềm hiển thị hộp thoại xác nhận: **"Bạn có muốn cài đặt ngay bây giờ không?"**.
  - Khi người dùng bấm **Có (⚡ Cài đặt ngay)**: Ứng dụng tự động khởi chạy tệp cài đặt `.exe` và đóng ứng dụng ngay lập tức mà không cần mở thư mục thủ công.

### 🛠 Cải Tiến & Tối Ưu (Changed)
- **Tối Ưu Không Gian & Bố Cục Cột Bảng Dữ Liệu**:
  - **Tab 2 (Dữ liệu cào)**: Rút ngắn cột "Nhóm / Trang" về `150px` với chế độ rút gọn chuỗi (`...`) và tooltip đầy đủ; mở rộng tối đa cột "Nội dung bài viết" (`Stretch`) chiếm toàn bộ diện tích còn trống.
  - **Tab 3 (Lịch sử phân tích)**: Rút ngắn cột "Nhóm / Trang" và "Mục tiêu / Nhu cầu" về `130px`; mở rộng toàn diện hai cột "Vai trò & Trích đoạn" và "Đánh giá AI" (`Stretch`) giúp đọc nhận định phân tích rõ ràng và thuận tiện hơn.

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
