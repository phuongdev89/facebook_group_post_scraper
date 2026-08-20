# Facebook Scraper 🕷️

A powerful Python-based Facebook scraping tool with a PyQt6 GUI interface for extracting posts, comments, and images from Facebook pages, groups, and individual posts without using the official Facebook API.

## 🎯 Key Highlights

- **Pure Requests-Based**: No browser automation or Selenium required - uses direct HTTP requests to Facebook's GraphQL API
- **Lightweight & Fast**: Minimal dependencies, efficient memory usage, and faster execution
- **No Browser Intervention**: Operates entirely through HTTP requests without spawning browser instances
- **Headless Operation**: Perfect for servers and automated workflows

## ✨ Features

- **Multiple Scraping Modes**:
  - 📄 Single post scraping (text, images, comments, and replies)
  - 👤 Page/Profile posts scraping
  - 👥 Facebook Group posts scraping
  - 🖼️ High-quality image extraction
  
- **Rich Data Extraction**:
  - Post content (text, reactions, shares)
  - Comments and nested replies
  - User information (names, IDs, profile links)
  - Media content (images with multiple resolution support)
  - Timestamps and engagement metrics

- **User-Friendly GUI**:
  - PyQt6-based desktop interface
  - Real-time logging and progress tracking
  - Tabbed interface for different scraping types
  - Easy configuration and export

- **Robust Architecture**:
  - Pure `requests` library implementation (no browser/Selenium)
  - Automatic retry mechanism with exponential backoff
  - Proxy support for privacy and rate limiting
  - Pagination handling for large data sets
  - JSON export for easy data processing
  - Direct GraphQL API communication

## 🆕 Tính Năng Mới (v1.0.2)

- **🌐 Tự Động Lấy Danh Sách Nhóm Đã Tham Gia Qua Cookie**:
  - Hỗ trợ đa định dạng Cookie đầu vào: Chuỗi Cookie thô (`c_user=...; xs=...`), lệnh cURL copy từ DevTools (`curl ... -b ...`), hoặc mảng JSON.
  - Tự động trích xuất toàn bộ các nhóm Facebook mà tài khoản đã tham gia (mbasic phân trang + desktop script parsing).
  - Tự động khử trùng lặp và sắp xếp theo thứ tự bảng chữ cái A-Z.
- **🔍 Bộ Lọc & Tìm Kiếm Nhóm Thời Gian Thực (Real-time Filter)**:
  - Lọc tức thì theo tên nhóm, URL, hoặc ID nhóm.
  - Hỗ trợ tiếng Việt không dấu (gõ `lap trinh` tự động khớp `Lập Trình Python`).
  - Tích hợp thanh tìm kiếm ngay trong hộp thoại chọn nhóm và cửa sổ Phóng to quản lý nhóm (`GroupManagerDialog`).
- **📋 Hộp Thoại Chọn Nhóm (GroupSelectDialog)**:
  - Checkbox tùy biến sắc nét, độ tương phản cao (nền xanh biển `#2563EB` + dấu tích trắng `✓`).
  - Các công cụ chọn nhanh: **Chọn tất cả**, **Bỏ chọn**, **Chọn nhóm đang lọc**, **Đảo chọn**.
  - Chế độ nhập linh hoạt: Thêm vào danh sách hiện tại (giữ nhóm cũ, khử trùng link) hoặc Thay thế toàn bộ danh sách.

## 🎯 Key Highlights

Ứng dụng hỗ trợ 2 hình thức cài đặt chạy độc lập trên Windows mà **hoàn toàn không cần cài đặt môi trường Python**:

### Cách 1: Bộ cài đặt Windows Setup (Khuyến nghị)
1. Tải file **`FacebookNotificationSetup.exe`** từ mục Releases / Bộ cài đặt.
2. Nhấp đúp để tiến hành cài đặt theo wizard.
3. Ứng dụng sẽ tự động tạo biểu tượng trên Desktop và Start Menu.
4. Nhấp vào biểu tượng để khởi chạy ngay.

### Cách 2: Gói Portable ZIP (Chạy ngay không cần cài đặt)
1. Tải file **`FacebookNotification-v1.0.0-windows-x64-portable.zip`**.
2. Giải nén vào một thư mục bất kỳ.
3. Chạy file **`FacebookNotification.exe`**.

> [!NOTE]
> **Vị trí lưu trữ dữ liệu:** Toàn bộ cơ sở dữ liệu SQLite (`facebook_scraper.sqlite`), phiên đăng nhập và profile duyệt web được lưu tự động và an toàn tại thư mục:
> `~/.facebook-notification/` (tương đương `C:\Users\<Tên_User>\.facebook-notification`).

---

## 🛠️ Hướng Dẫn Đóng Gói Ứng Dụng (Dành Cho Developer)

### 1. Đóng gói Standalone Executable (PyInstaller)
Chạy script đóng gói tự động:
```bash
python scripts/build_standalone.py
```
Sau khi hoàn tất, thư mục độc lập chứa đầy đủ runtime và executable sẽ nằm tại `dist/FacebookNotification/`.

### 2. Tạo gói Portable ZIP
```bash
python scripts/create_portable_zip.py
```
File nén sẽ được xuất ra `dist/FacebookNotification-v1.0.0-windows-x64-portable.zip`.

### 3. Biên dịch Bộ cài đặt Setup .exe (Inno Setup)
Mở file `installer/setup.iss` bằng phần mềm [Inno Setup Compiler](https://jrsoftware.org/isdl.php) và nhấn **Compile** (hoặc chạy lệnh `ISCC.exe installer/setup.iss`). File cài đặt sẽ được tạo tại `installer/Output/FacebookNotificationSetup.exe`.

---

## 🚀 Cài Đặt Từ Mã Nguồn (Development Mode)

### Prerequisites

- Python 3.8 hoặc cao hơn
- Hệ điều hành Windows / macOS / Linux

### Cài đặt môi trường phát triển:

1. Clone repository:
```bash
git clone https://gitlab.com/phuongdev89/facebook_post_comment_scraper.git
cd facebook_post_comment_scraper
```

2. Cài đặt các thư viện phụ thuộc:
```bash
pip install -r requirements.txt
```


## 📖 Usage

### GUI Mode (Khởi chạy Giao diện)

Khởi chạy ứng dụng đồ họa PyQt6 (4 Tab hoàn chỉnh):
```bash
python run_gui.py
```
*(Hoặc dùng `python facebook_notification_ui.py` để tương thích ngược)*

Giao diện cung cấp 4 tab chức năng chuyên nghiệp:
1. **📁 Group Posts**: Quét bài viết nhóm Facebook, trích xuất bình luận, theo dõi tiến trình và log thời gian thực
2. **📜 Dữ liệu cào**: Xem toàn bộ bài viết đã lưu vào SQLite, phân trang, bộ lọc từng cột và dropdown nhóm Autocomplete
3. **🤖 Lịch sử phân tích**: Xem danh sách các bài viết được AI đánh giá khớp tin bán máy (`should_notify=True`), lọc nâng cao, mở bài viết và xóa bản ghi
4. **⚙️ Cấu hình**: Thiết lập thông báo Telegram Bot và cấu hình AI phân tích Đa Model Tagging (Random Fallback timeout 20s, hỗ trợ Hot-reload thời gian thực)

### CLI Mode

```python
from src.utils.helpers import extract_post_id_from_url, extract_group_id_from_url
from src.core.group_scraper import fetch_posts as fetch_group_posts
from src.database.repository import save_or_update_post

# Cào dữ liệu theo nhóm
posts = fetch_group_posts(group_id="123456789", target_count=10)
```

## 📁 Cấu trúc Dự án Chuẩn (Project Architecture)

```
facebook_post_comment_scraper/
├── src/                                  # Mã nguồn chính của dự án
│   ├── config/                           # Cấu hình & Hằng số
│   │   ├── constants.py                  # Endpoints, regex, doc_ids, headers
│   │   └── default_prompts.py            # DEFAULT_AI_PROMPT & DEFAULT_BUYER_AI_PROMPT
│   ├── core/                             # Lõi nghiệp vụ (Scrapers, AI, Telegram, Proxy)
│   │   ├── ai_analyzer.py                # Phân tích AI đa model & fallback
│   │   ├── comment_scraper.py            # Cào bình luận và phản hồi
│   │   ├── group_scraper.py              # Cào bài viết nhóm Facebook
│   │   ├── page_scraper.py               # Cào bài viết Page/Profile Facebook
│   │   ├── media_scraper.py              # Trích xuất ảnh & media
│   │   ├── proxy_utils.py                # Quản lý proxy xoay vòng / tĩnh
│   │   └── telegram_notifier.py          # Gửi cảnh báo & báo cáo Telegram
│   ├── database/                         # Tầng cơ sở dữ liệu SQLite
│   │   ├── connection.py                 # SQLite connection contextmanager & PRAGMA WAL
│   │   ├── schema.py                     # Định nghĩa schema bảng & index
│   │   └── repository.py                 # Các hàm CRUD thao tác dữ liệu
│   ├── ui/                               # Giao diện người dùng PyQt6
│   │   ├── app.py                        # MainWindow & điều phối ứng dụng
│   │   ├── components/                   # Custom UI Widgets (TagWidget, GroupListWidget)
│   │   ├── dialogs/                      # Popup modals (PostDetailDialog, CookieDialog)
│   │   └── workers/                      # Các luồng xử lý ngầm (AI Worker, Scraper Worker)
│   └── utils/                            # Tiện ích bổ trợ (Cookie parser, URL extractor)
├── tests/                                # Bộ kiểm thử tự động (Unit & Integration tests)
│   ├── test_database.py                  # Test SQLite CRUD, index, delete
│   ├── test_ai_analyzer.py               # Test AI JSON bundle, fallback
│   ├── test_telegram.py                  # Test Telegram formatting & alerts
│   └── test_workers.py                   # Test worker concurrency & hot-reload
├── run_gui.py                            # Entry point khởi chạy GUI nhanh: python run_gui.py
├── main.py                               # CLI entry point & backward wrapper
├── requirements.txt                      # Danh sách thư viện phụ thuộc
├── .gitignore                            # Git ignore hoàn chỉnh
└── README.md                             # Tài liệu hướng dẫn sử dụng
```

## 📊 Output Format

Data is saved in JSON format with the following structure:

### Post Data
```json
{
  "post_id": "123456789",
  "author": "User Name",
  "author_id": "100001234567890",
  "content": "Post text content",
  "timestamp": "2024-01-01T12:00:00",
  "reactions": 150,
  "shares": 25,
  "images": ["url1.jpg", "url2.jpg"],
  "comments_count": 45
}
```

### Comment Data
```json
{
  "comment_id": "987654321",
  "author": "Commenter Name",
  "author_id": "100009876543210",
  "text": "Comment text",
  "timestamp": "2024-01-01T12:30:00",
  "replies": [...]
}
```

## ⚠️ Important Notes

### Legal & Ethical Considerations

- **Terms of Service**: This tool may violate Facebook's Terms of Service. Use at your own risk.
- **Rate Limiting**: Implement appropriate delays between requests to avoid detection.
- **Privacy**: Respect user privacy and data protection laws (GDPR, CCPA, etc.).
- **Personal Use**: This tool is intended for educational and research purposes only.

### Technical Limitations

- **Doc IDs**: Facebook's GraphQL document IDs change frequently. You'll need to update them periodically.
- **Authentication**: Requires valid Facebook session tokens that expire.
- **Rate Limits**: Excessive requests may result in temporary blocks or account restrictions.
- **Private Content**: Cannot access content that requires authentication beyond what's provided.

## 🛠️ Troubleshooting

### Common Issues

**1. "Failed after 5 attempts" error**
- Check your internet connection
- Verify proxy settings
- Update DOC_ID values
- Ensure session tokens are valid

**2. No data returned**
- Verify the URL/ID is correct
- Check if content is publicly accessible
- Update authentication headers

**3. GUI not launching**
- Ensure PyQt6 is properly installed: `pip install --upgrade PyQt6`
- Check Python version compatibility

### Debug Mode

Enable verbose logging by modifying the scripts:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

### Development Setup

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📝 License

This project is provided for educational purposes only. Users are responsible for ensuring compliance with Facebook's Terms of Service and applicable laws.

## 🙏 Acknowledgments

- Built with Python and PyQt6
- Uses pure `requests` library for HTTP communication
- Direct GraphQL API integration (unofficial)
- No browser automation required
- Inspired by the need for lightweight, efficient data research tools

## 📞 Support

For issues, questions, or suggestions:
- Open an issue on GitHub
- Check existing issues for solutions
- Review the troubleshooting section

## ⚡ Roadmap

**Completed:**
- [x] Enhanced comment count detection with 6 extraction paths
- [x] Advanced Story node discovery in nested structures
- [x] Complete album scraping (up to 50 images per post)
- [x] Post deduplication for interrupted sessions
- [x] Automatic retry logic for transient API errors
- [x] Robust pagination with proper error handling
- [x] Reel/video filtering
- [x] Configurable comment threshold filtering

**Upcoming:**
- [ ] Add support for Facebook Stories
- [ ] Implement video download functionality
- [ ] Add data export to CSV/Excel
- [ ] Improve authentication flow
- [ ] Add scheduling and automation features
- [ ] Create web-based interface
- [ ] Add data analysis and visualization tools

---

**Disclaimer**: This tool is not affiliated with or endorsed by Facebook/Meta. Use responsibly and ethically.
