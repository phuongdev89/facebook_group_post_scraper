# Facebook Notification & Scraper AI 🕷️

**[🇻🇳 Tiếng Việt](README.md) | [🇬🇧 English](README.en.md)**

A high-performance desktop application for extracting (scraping) posts and comments from Facebook Groups, automatically analyzing and filtering content using AI (Google Gemini & OpenAI / OpenRouter / DeepSeek / Ollama), and dispatching real-time alert notifications via Telegram Bot.

---

## 🎯 Key Highlights

- **Pure HTTP Requests**: Operates entirely via Facebook GraphQL APIs and HTTP protocols without spinning up headless browser instances (no Selenium/Playwright/Puppeteer), drastically saving CPU and RAM.
- **Multi-Platform AI Analysis**:
  - Full support for **Google Gemini API** and all **OpenAI-compatible** providers (Official OpenAI, OpenRouter, DeepSeek, Groq, Together AI, Ollama, vLLM, LM Studio).
  - Intelligent Model Fallback & Rotation mechanism to avoid Rate Limit bottlenecks and minimize latency.
  - Ultra-resilient JSON parser: Automatically strips thinking blocks (`<think>`), auto-fixes trailing commas, and repairs unclosed JSON structures.
- **Instant Telegram Alerts**: Integrated background Dispatcher thread constantly monitors the database and delivers professionally formatted HTML alerts as soon as AI marks a post as matching user criteria/keywords.
- **Smart Group Management**:
  - Automatically scrapes the list of all Facebook groups joined by the account using Session Cookies (supports raw Cookie strings, cURL commands, or JSON arrays).
  - Real-time search and filter with Vietnamese accent-insensitive matching support.
- **Optimized SQLite Engine**: Safely stored in the user home directory (`~/.facebook-notification/`) with PRAGMA WAL concurrent mode, automatic post deduplication, and automated log cleanup (> 1 day).
- **Over-The-Air (OTA) Updates**: Automatically checks and downloads the latest release directly from GitHub Releases or static mirrors.

---

## 🚀 Installation & Usage

### 1. For End-Users (Windows Pre-built Executable)

The application runs standalone on Windows **without requiring Python installation**:

- **Windows Setup Installer (Recommended)**:
  1. Download `FacebookNotification_Setup_vX.X.X.exe` from the Releases section.
  2. Double-click the installer and follow the wizard. Shortcuts will be placed on the Desktop and Start Menu.
- **Portable ZIP Package (Zero-installation)**:
  1. Download `FacebookNotification-vX.X.X-windows-x64-portable.zip`.
  2. Extract the archive into any folder and run `FacebookNotification.exe`.

> [!NOTE]
> **Data Storage Location:** All SQLite database files (`facebook_scraper.sqlite`), AI configurations, tokens, and logs are safely stored in:  
> `~/.facebook-notification/` (equivalent to `C:\Users\<Username>\.facebook-notification`).

---

### 2. For Developers (Run from Source)

#### System Requirements:
- Python 3.9+ (tested and fully compatible with Python 3.11 – 3.13)
- Operating System: Windows 10 / 11 (64-bit)

#### Setup Steps:

1. **Clone the repository**:
   ```bash
   git clone https://gitlab.com/phuongdev89/facebook_post_comment_scraper.git
   cd facebook_post_comment_scraper
   ```

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch GUI Application (PyQt6)**:
   ```bash
   python run_gui.py
   ```

4. **Run Automated Tests (Unit Tests)**:
   ```bash
   pytest
   ```

---

## 🛠️ Build & Packaging

Dedicated build scripts are available in the project root and `scripts/` directory:

| Build Type | Execution Command | Output Artifact |
| :--- | :--- | :--- |
| **Standalone Directory (PyInstaller)** | `python scripts/build_standalone.py` | Standalone application folder `dist/FacebookNotification/` |
| **Portable ZIP Package** | `python scripts/create_portable_zip.py` | Compressed archive `dist/FacebookNotification-vX.X.X-windows-x64-portable.zip` |
| **Lightweight Patch (.zip & .exe)** | `build_patch.bat` *(or `bash build_patch.sh`)* | Lightweight update package (~14MB) `dist/FacebookNotification_Patch_vX.X.X.*` |
| **Windows Setup Installer (.exe)** | `build_installer.bat` *(or `bash build_installer.sh`)* | Inno Setup installer executable `dist/FacebookNotification_Setup_vX.X.X.exe` |

---

## 📁 Project Architecture

```
facebook_post_comment_scraper/
├── src/                                  # Main application source code
│   ├── config/                           # System configuration, versioning & default prompts
│   │   ├── constants.py                  # Endpoints, regex, constants & version loader
│   │   └── default_prompts.py            # Pre-configured buyer/seller AI prompt templates
│   ├── core/                             # Business logic (Scraper, AI, Telegram, Proxy, Updater)
│   │   ├── ai_analyzer.py                # AI analysis via Gemini & OpenAI-compatible APIs
│   │   ├── comment_scraper.py            # Scrapes comments and nested thread replies
│   │   ├── group_scraper.py              # Scrapes group posts via Facebook GraphQL API
│   │   ├── page_scraper.py               # Scrapes posts from Fanpages and Profiles
│   │   ├── media_scraper.py              # Extracts high-resolution media and image albums
│   │   ├── proxy_utils.py                # Proxy management and liveness testing
│   │   ├── telegram_notifier.py          # Dispatches alerts and summaries via Telegram Bot
│   │   └── updater.py                    # Checks and downloads OTA updates automatically
│   ├── database/                         # SQLite persistence layer
│   │   ├── connection.py                 # SQLite connection manager & PRAGMA WAL mode
│   │   ├── schema.py                     # Table definitions, schemas and indexes
│   │   └── repository.py                 # CRUD operations, deduplication & log purging
│   ├── ui/                               # PyQt6 Graphical User Interface
│   │   ├── app.py                        # MainWindow coordinator and 4-Tab navigation
│   │   ├── components/                   # Custom UI Widgets (Gemini/OpenAI Model Selector, TagWidget...)
│   │   ├── dialogs/                      # Modal dialogs (Cookie, GroupSelect, PromptGuide, Update...)
│   │   └── workers/                      # Background QThreads (Scraper, AI, Telegram, TestModel...)
│   └── utils/                            # Helper utilities (Cookie parser, ID extractor, date formatter)
├── guides/                               # Interactive HTML user guides and documentation
│   └── index.html                        # Web-based detailed documentation and manual
├── installer/                            # Inno Setup build configurations
│   ├── setup.iss                         # Full Windows installer setup script
│   └── patch.iss                         # Lightweight patch update script
├── scripts/                              # Packaging and distribution Python scripts
│   ├── build_standalone.py               # Builds PyInstaller bundle with version metadata
│   ├── create_portable_zip.py            # Packages standalone folder into Portable ZIP
│   └── create_patch_zip.py               # Generates lightweight patch ZIP
├── tests/                                # Automated unit test suite
├── build_installer.bat / .sh             # One-click command to build full setup installer
├── build_patch.bat / .sh                 # One-click command to build patch packages
├── facebook_notification.spec            # PyInstaller specification file
├── run_gui.py                            # Main application entry point
├── .version                              # Single source of truth for versioning
├── CHANGELOG.md                          # Comprehensive release history and changelog
├── README.en.md                          # English documentation
└── README.md                             # Vietnamese documentation
```

---

## 📚 Documentation & Changelog

- 📖 **User Guide & Manual**: Please visit [`guides/index.html`](guides/index.html) for detailed step-by-step instructions *(including Facebook Cookie extraction, Telegram Bot creation, AI API Key configuration, and best practices)*.
- 📝 **Release Changelog**: Review all new features, enhancements, and bug fixes across all versions in [`CHANGELOG.md`](CHANGELOG.md).

---

## ⚠️ Disclaimer

- This software is developed strictly for **educational, research, and personal automation purposes**.
- The author assumes no liability for any misuse or violation of Facebook / Meta Terms of Service. Users are solely responsible for compliance with applicable terms and regulations.
