# Facebook Notification & Scraper AI 🕷️

**[🇻🇳 Tiếng Việt](README.md) | [🇬🇧 English](README.en.md)**

Ứng dụng chuyên nghiệp thu thập (cào) bài viết, bình luận từ các hội nhóm Facebook, tự động phân tích và sàng lọc nội dung bằng AI (Google Gemini & OpenAI / OpenRouter / DeepSeek / Ollama), sau đó gửi cảnh báo tức thì qua Telegram Bot.

---

## 🎯 Điểm Nổi Bật

- **Thuần HTTP Requests**: Hoạt động hoàn toàn qua Facebook GraphQL API và giao thức HTTP, không cần mở trình duyệt giả lập (Selenium/Playwright/Puppeteer), tiết kiệm tối đa RAM và CPU.
- **Phân Tích AI Đa Nền Tảng**:
  - Hỗ trợ cả **Google Gemini API** và toàn bộ các nhà cung cấp tương thích **OpenAI** (OpenAI chính hãng, OpenRouter, DeepSeek, Groq, Together AI, Ollama, vLLM, LM Studio).
  - Tự động luân phiên (Fallback / Rotation) giữa các model để tránh lỗi nghẽn hạn mức (Rate Limit) và tối ưu độ trễ.
  - Bộ bóc tách JSON siêu bền bỉ: Tự động lọc khối suy nghĩ (`<think>`), sửa dấu phẩy thừa, tự sửa cú pháp JSON thiếu ngoặc.
- **Cảnh Báo Telegram Tức Thì**: Tích hợp luồng Dispatcher nền quét cơ sở dữ liệu và tự động bắn thông báo kèm định dạng HTML chuyên nghiệp khi AI đánh giá bài viết khớp từ khóa / nhu cầu.
- **Quản Lý Nhóm Thông Minh**:
  - Tự động cào danh sách toàn bộ các nhóm Facebook mà tài khoản đã tham gia thông qua Cookie JSON từ extension (Cookie-Editor, J2Team).
  - Bộ lọc tìm kiếm nhóm theo thời gian thực, hỗ trợ gõ tiếng Việt không dấu.
- **Cơ Sở Dữ Liệu SQLite Tối Ưu**: Lưu trữ dữ liệu an toàn tại thư mục người dùng (`~/.facebook-notification/`), bật chế độ ghi song song PRAGMA WAL, tự động khử trùng lặp. Log hoạt động ghi ra file (`access.log`, `error.log`) thay vì DB để giữ SQLite nhẹ.
- **Xem Trước Media Trong Hộp Thoại Chi Tiết**: Thumbnail ảnh & video hiển thị trực tiếp trong dialog Chi tiết bài viết, tải bất đồng bộ, click để mở trình duyệt.
- **Tự Động Cập Nhật (OTA Updates)**: Kiểm tra và tải bản cập nhật mới nhất trực tiếp từ GitHub Releases hoặc máy chủ file tĩnh.

---

## 🚀 Cài Đặt & Sử Dụng

### 1. Dành cho người dùng (Chạy trực tiếp trên Windows)

Ứng dụng hỗ trợ chạy độc lập trên Windows mà **không cần cài đặt môi trường Python**:

- **Bộ cài đặt Windows Setup (Khuyến nghị)**:
  1. Tải file `FacebookNotification_Setup_vX.X.X.exe` từ mục Releases.
  2. Nhấp đúp để cài đặt theo hướng dẫn. Ứng dụng sẽ tự tạo biểu tượng trên Desktop và Start Menu.
- **Gói Portable ZIP (Chạy ngay)**:
  1. Tải file `FacebookNotification-vX.X.X-windows-x64-portable.zip`.
  2. Giải nén vào thư mục bất kỳ và nhấp đúp file `FacebookNotification.exe`.

> [!NOTE]
> **Vị trí lưu trữ dữ liệu:** Toàn bộ cơ sở dữ liệu SQLite (`facebook_scraper.sqlite`), log hoạt động (`access.log`, `error.log`), cấu hình AI, token và lịch sử được lưu trữ tại thư mục:  
> `~/.facebook-notification/` (tương đương `C:\Users\<Tên_User>\.facebook-notification`).

---

### 2. Dành cho lập trình viên (Chạy từ mã nguồn)

#### Yêu cầu hệ thống:
- Python 3.9 trở lên (đã kiểm thử tương thích tốt trên Python 3.11 - 3.13)
- Hệ điều hành: Windows 10 / 11 (64-bit)

#### Các bước cài đặt:

1. **Clone repository về máy**:
   ```bash
   git clone https://gitlab.com/phuongdev89/facebook_post_comment_scraper.git
   cd facebook_post_comment_scraper
   ```

2. **Cài đặt thư viện phụ thuộc**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Khởi chạy giao diện người dùng (PyQt6)**:
   ```bash
   python run_ui.py
   ```

4. **Chạy kiểm thử tự động (Unit Tests)**:
   ```bash
   pytest
   ```

---

## 🛠️ Đóng Gói Ứng Dụng (Build & Packaging)

Dự án cung cấp sẵn các công cụ đóng gói chuyên dụng tại thư mục gốc và thư mục `scripts/`:

| Kịch bản | Lệnh thực thi | Kết quả đầu ra |
| :--- | :--- | :--- |
| **Bản Standalone (PyInstaller)** | `python scripts/build_standalone.py` | Thư mục chạy độc lập `dist/FacebookNotification/` |
| **Gói Portable ZIP** | `python scripts/create_portable_zip.py` | File nén `dist/FacebookNotification-vX.X.X-windows-x64-portable.zip` |
| **Bản Patch siêu nhẹ (.zip & .exe)** | `build_patch.bat` *(hoặc `bash build_patch.sh`)* | File cập nhật đè siêu nhẹ (~14MB) `dist/FacebookNotification_Patch_vX.X.X.*` |
| **Bộ cài đặt Setup (.exe)** | `build_installer.bat` *(hoặc `bash build_installer.sh`)* | Bộ cài đặt Inno Setup `dist/FacebookNotification_Setup_vX.X.X.exe` |

---

## 📁 Cấu Trúc Dự Án

```
facebook_post_comment_scraper/
├── src/                                  # Mã nguồn chính của ứng dụng
│   ├── config/                           # Cấu hình hệ thống, phiên bản & prompt mặc định
│   │   ├── constants.py                  # Endpoints, regex, hằng số và bộ nạp phiên bản
│   │   └── default_prompts.py            # Prompt AI mẫu cho người mua và người bán
│   ├── core/                             # Lõi nghiệp vụ (Scraper, AI, Telegram, Proxy, Updater)
│   │   ├── ai_analyzer.py                # Phân tích bài viết bằng Gemini & OpenAI-compatible
│   │   ├── comment_scraper.py            # Cào bình luận và các phản hồi lồng nhau
│   │   ├── group_scraper.py              # Cào bài viết từ nhóm Facebook qua GraphQL
│   │   ├── page_scraper.py               # Cào bài viết từ Fanpage / Profile
│   │   ├── media_scraper.py              # Trích xuất hình ảnh chất lượng cao
│   │   ├── proxy_utils.py                # Quản lý và kiểm tra danh sách Proxy
│   │   ├── telegram_notifier.py          # Gửi tin nhắn và cảnh báo qua Telegram Bot
│   │   └── updater.py                    # Kiểm tra và tải bản cập nhật OTA tự động
│   ├── database/                         # Tầng lưu trữ cơ sở dữ liệu SQLite
│   │   ├── connection.py                 # Quản lý kết nối SQLite & chế độ WAL
│   │   ├── schema.py                     # Cấu trúc bảng, cột và chỉ mục (indexes)
│   │   └── repository.py                 # Thao tác dữ liệu (CRUD, khử trùng lặp, nhật ký log)
│   ├── ui/                               # Giao diện đồ họa PyQt6
│   │   ├── app.py                        # Cửa sổ chính (MainWindow) và điều hướng 4 Tab
│   │   ├── components/                   # Các Widget tùy biến (Gemini/OpenAI Model Selector, TagWidget...)
│   │   ├── dialogs/                      # Hộp thoại popup (Cookie, GroupSelect, PromptGuide, Update...)
│   │   └── workers/                      # Các luồng chạy ngầm QThread (Scraper, AI, Telegram, TestModel...)
│   └── utils/                            # Tiện ích bổ trợ (Xử lý cookie, bóc tách ID, định dạng ngày giờ)
│       └── file_logger.py                # Ghi log ra file access.log / error.log (thay thế log SQLite)
├── guides/                               # Tài liệu hướng dẫn sử dụng tương tác (HTML)
│   └── index.html                        # Giao diện Web hướng dẫn sử dụng chi tiết
├── installer/                            # Kịch bản Inno Setup để tạo bộ cài đặt Windows
│   ├── setup.iss                         # Kịch bản đóng gói bộ cài đặt chính (Full Setup)
│   └── patch.iss                         # Kịch bản đóng gói bản cập nhật vá lỗi (Lightweight Patch)
├── scripts/                              # Các kịch bản Python hỗ trợ đóng gói và phân phối
│   ├── build_standalone.py               # Đóng gói PyInstaller kèm file metadata phiên bản
│   ├── create_portable_zip.py            # Nén thư mục độc lập thành file Portable ZIP
│   └── create_patch_zip.py               # Tạo file ZIP bản vá siêu nhẹ
├── tests/                                # Bộ bài kiểm thử tự động (Unit Tests)
├── build_installer.bat / .sh             # Lệnh 1-click tạo bộ cài đặt Full Setup
├── build_patch.bat / .sh                 # Lệnh 1-click tạo bản cập nhật Patch
├── facebook_notification.spec            # Cấu hình đóng gói PyInstaller
├── run_ui.py                            # Điểm khởi chạy ứng dụng chính
├── .version                              # File định danh phiên bản duy nhất của ứng dụng
├── CHANGELOG.md                          # Chi tiết lịch sử thay đổi qua các phiên bản
├── README.en.md                          # Tài liệu tiếng Anh (English Documentation)
└── README.md                             # Tài liệu giới thiệu tổng quan dự án
```

---

## 📚 Tài Liệu Hướng Dẫn & Nhật Ký Thay Đổi

- 📖 **Hướng Dẫn Sử Dụng Chi Tiết**: Vui lòng tham khảo tài liệu đầy đủ tại [`guides/index.html`](guides/index.html) *(bao gồm hướng dẫn lấy Cookie Facebook, tạo Telegram Bot, cấu hình API Key AI và mẹo sử dụng hiệu quả)*.
- 📝 **Nhật Ký Cập Nhật (Changelog)**: Xem chi tiết toàn bộ tính năng mới, cải tiến và bản sửa lỗi qua từng phiên bản tại [`CHANGELOG.md`](CHANGELOG.md).

---

## ⚠️ Tuyên Bố Từ Chối Trách Nhiệm (Disclaimer)

- Dự án này được phát triển hoàn toàn vì mục đích **học tập, nghiên cứu kỹ thuật và tự động hóa quy trình cá nhân**.
- Tác giả không chịu trách nhiệm đối với bất kỳ hành vi sử dụng sai mục đích hoặc vi phạm Điều khoản Dịch vụ của Facebook / Meta. Người dùng tự chịu trách nhiệm khi triển khai và sử dụng ứng dụng.
