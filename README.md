# Facebook Notification & Scraper AI 🕷️

**[🇻🇳 Tiếng Việt](README.md) | [🇬🇧 English](README.en.md) | [📖 Hướng Dẫn HTML (guides/index.html)](guides/index.html)**

Ứng dụng chuyên nghiệp thu thập (cào) bài viết, bình luận từ các hội nhóm Facebook, tự động phân tích và sàng lọc nội dung bằng AI (Google Gemini & OpenAI / OpenRouter / DeepSeek / Ollama), sau đó gửi cảnh báo tức thì qua Telegram Bot.

---

## 🎯 Điểm Nổi Bật

- **🌐 Hỗ Trợ Đa Ngôn Ngữ Tức Thì (Tiếng Việt 🇻🇳 / English 🇬🇧)**: Chuyển đổi toàn bộ giao diện, bảng dữ liệu, diễn giải biểu thức và thông báo sang Tiếng Việt hoặc Tiếng Anh chỉ với 1 cú click vào biểu tượng cờ trên thanh tiêu đề.
- **Thuần HTTP Requests & Cào Đa Luồng Song Song (1-10 Luồng)**: Hoạt động hoàn toàn qua Facebook GraphQL API và giao thức HTTP, không cần mở trình duyệt giả lập. Hỗ trợ quét song song đồng thời từ 1 đến 10 nhóm Facebook độc lập với tốc độ vượt trội.
- **Bộ Lọc Từ Khóa Boolean Logic & Diễn Giải Ngôn Ngữ Tự Nhiên**:
  - Hỗ trợ xây dựng biểu thức logic chuyên sâu (`AND`, `OR`, `NOT`, `()`).
  - Hộp thoại cấu hình 2 chế độ: **🧱 Dựng trực quan (Visual Rule Builder)** và **✍️ Tự nhập biểu thức (Raw Expression)**, tự động diễn giải ý nghĩa sang tiếng Việt / tiếng Anh thời gian thực.
  - Tùy biến cào bình luận linh hoạt (`Cmt tối thiểu`): `0` (không cào bình luận, nhanh nhất), `-1` (cào tất cả bình luận), `> 0` (cào tối đa/tối thiểu N bình luận/bài, không bỏ qua bài viết ít cmt).
  - Giới hạn thời gian bài viết (Cutoff timestamp): Lọc bài viết 1-7 ngày trước hoặc tùy chỉnh lịch.
- **Phân Tích AI Đa Nền Tảng & Khử Trùng Lặp Thông Minh**:
  - Hỗ trợ cả **Google Gemini API** và toàn bộ các nhà cung cấp tương thích **OpenAI** (OpenAI chính hãng, OpenRouter, DeepSeek, Groq, Together AI, Ollama, vLLM, LM Studio).
  - Tự động luân phiên (Fallback / Rotation) giữa các model để tránh lỗi nghẽn hạn mức (Rate Limit) và tối ưu độ trễ.
  - **Khử trùng lặp đa tầng (`post_id` + `comment_id`)**: Tự động nhận diện bài viết hoặc bình luận/reply đã được phân tích trước đó, bỏ qua không gọi AI lại giúp tiết kiệm triệt để Token API.
  - Bộ bóc tách JSON siêu bền bỉ: Tự động lọc khối suy nghĩ (`<think>`), sửa dấu phẩy thừa, tự sửa cú pháp JSON thiếu ngoặc.
- **Cảnh Báo Telegram Tức Thì**: Tích hợp luồng Dispatcher nền quét cơ sở dữ liệu và tự động bắn thông báo kèm định dạng HTML chuyên nghiệp khi AI đánh giá bài viết khớp từ khóa / nhu cầu.
- **Quản Lý Nhóm Thông Minh & Cookie JSON Chuẩn Hóa**:
  - Tự động cào danh sách toàn bộ các nhóm Facebook mà tài khoản đã tham gia thông qua Cookie JSON từ extension (Cookie-Editor, J2Team).
  - Tự động phát hiện lỗi định dạng cookie và hỗ trợ xóa sạch hoàn toàn Cookie chỉ với 1 cú click.
  - Bộ lọc tìm kiếm nhóm theo thời gian thực, hỗ trợ gõ tiếng Việt không dấu.
- **Cơ Sở Dữ Liệu SQLite Tối Ưu**: Lưu trữ dữ liệu an toàn tại thư mục người dùng (`~/.facebook-notification/`), bật chế độ ghi song song PRAGMA WAL, tự động khử trùng lặp. Log hoạt động ghi ra file thời gian thực (`access.log`, `error.log`) thay vì DB để giữ SQLite nhẹ.
- **Xem Trước Media Trong Hộp Thoại Chi Tiết**: Thumbnail ảnh & video hiển thị trực tiếp trong dialog Chi tiết bài viết, tải bất đồng bộ, click để mở trình duyệt.
- **Tự Động Cập Nhật (OTA Updates)**: Kiểm tra và tải bản cập nhật mới nhất trực tiếp từ GitHub Releases hoặc máy chủ file tĩnh.

---

## 🚀 Cài Đặt & Sử Dụng

### 1. Dành cho người dùng (Chạy trực tiếp trên Windows)

Ứng dụng hỗ trợ chạy độc lập trên Windows mà **không cần cài đặt môi trường Python**:

- **Bộ cài đặt Windows Setup**:
  1. Tải file `FacebookNotification_Setup_vX.X.X.exe` từ mục Releases.
  2. Nhấp đúp để cài đặt theo hướng dẫn. Ứng dụng sẽ tự tạo biểu tượng trên Desktop và Start Menu.

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
   git clone https://gitlab.com/phuongdev89/facebook_group_post_scraper.git
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

Dự án cung cấp sẵn cấu hình PyInstaller và Inno Setup tại thư mục `installer/`:

| Kịch bản | Lệnh thực thi | Kết quả đầu ra |
| :--- | :--- | :--- |
| **Bản Standalone (PyInstaller)** | `pyinstaller installer/build.spec` | Thư mục chạy độc lập `dist/FacebookNotification/` |
| **Bộ cài đặt Setup (.exe)** | `installer/build_setup.bat` *(hoặc `bash installer/build_setup.sh`)* | Bộ cài đặt Inno Setup `dist/FacebookNotification_Setup_vX.X.X.exe` |

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
│   ├── locales/                          # Từ điển đa ngôn ngữ (i18n)
│   │   ├── en.json                       # Ngôn ngữ Tiếng Anh
│   │   └── vi.json                       # Ngôn ngữ Tiếng Việt
│   ├── ui/                               # Giao diện đồ họa PyQt6
│   │   ├── app.py                        # Cửa sổ chính (MainWindow) và điều hướng 4 Tab
│   │   ├── components/                   # Các Widget tùy biến (Model Selector, Keyword Filter...)
│   │   ├── dialogs/                      # Hộp thoại popup (Cookie, GroupSelect, PromptGuide...)
│   │   └── workers/                      # Các luồng chạy ngầm QThread (Scraper, AI, Telegram...)
│   └── utils/                            # Tiện ích bổ trợ (i18n, keyword engine, logger, helpers)
│       ├── i18n.py                       # Quản lý ngôn ngữ động thời gian thực
│       ├── keyword_engine.py             # Bộ phân tích AST & giải nghĩa từ khóa Boolean
│       ├── file_logger.py                # Ghi log ra file access.log / error.log theo thời gian thực
│       └── helpers.py                    # Trợ giúp trích xuất link, ảnh, token & app icon
├── assets/                               # Tài nguyên icon nhận diện (SVG, PNG 512px, Windows ICO, cờ quốc gia)
│   ├── flags/                            # Icon cờ chuyển đổi ngôn ngữ (vn.svg, us.svg)
│   ├── favicon.svg
│   ├── icon.ico
│   ├── icon.png
│   └── icon.svg
├── guides/                               # Tài liệu hướng dẫn sử dụng tương tác (HTML song ngữ)
│   ├── favicon.svg                       # Web favicon cho tài liệu hướng dẫn
│   ├── index.html                        # Hướng dẫn chi tiết Tiếng Việt
│   └── en.html                           # Hướng dẫn chi tiết English
├── installer/                            # Kịch bản đóng gói PyInstaller & Inno Setup
│   ├── build.spec                        # File cấu hình PyInstaller
│   ├── setup.iss                         # Kịch bản Inno Setup tạo bộ cài đặt Windows
│   ├── build_setup.bat                   # File thực thi build setup trên Windows
│   └── build_setup.sh                    # Shell script build setup trên Linux/macOS
├── tests/                                # Bộ bài kiểm thử tự động (Unit Tests)
├── run_ui.py                            # Điểm khởi chạy ứng dụng chính
├── .version                              # File định danh phiên bản duy nhất của ứng dụng
├── CHANGELOG.md                          # Chi tiết lịch sử thay đổi qua các phiên bản
├── CHANGELOG.en.md                       # Changelog in English
├── README.md                             # Tài liệu giới thiệu tiếng Việt
└── README.en.md                          # English Documentation
```

---

## 📚 Tài Liệu Hướng Dẫn & Nhật Ký Thay Đổi

- 📖 **Hướng Dẫn Sử Dụng Chi Tiết**: Vui lòng tham khảo tài liệu đầy đủ tại [`guides/index.html`](guides/index.html) *(bao gồm hướng dẫn lấy Cookie Facebook, tạo Telegram Bot, cấu hình API Key AI và mẹo sử dụng hiệu quả)*.
- 📝 **Nhật Ký Cập Nhật (Changelog)**: Xem chi tiết toàn bộ tính năng mới, cải tiến và bản sửa lỗi qua từng phiên bản tại [`CHANGELOG.md`](CHANGELOG.md).

---

## ⚠️ Tuyên Bố Từ Chối Trách Nhiệm (Disclaimer)

- Dự án này được phát triển hoàn toàn vì mục đích **học tập, nghiên cứu kỹ thuật và tự động hóa quy trình cá nhân**.
- Tác giả không chịu trách nhiệm đối với bất kỳ hành vi sử dụng sai mục đích hoặc vi phạm Điều khoản Dịch vụ của Facebook / Meta. Người dùng tự chịu trách nhiệm khi triển khai và sử dụng ứng dụng.
