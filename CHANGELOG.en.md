# Change Log (Changelog)

All notable changes, enhancements, and bug fixes for the **Facebook Post & Comment Scraper AI** project are documented here in detail.

---

## [1.0.8] - 2026-08-28

### ✨ New Features & Multilingual System (Added)
- **Instant Multilingual System (i18n - Vietnamese 🇻🇳 & English 🇬🇧)**:
  - Integrated a dynamic localization engine backed by standardized JSON translation dictionaries in `src/locales/vi.json` and `src/locales/en.json`.
  - Added 2 flag icon buttons (🇻🇳 and 🇬🇧) in the top header: Click to switch the entire application interface, data tables, action buttons, settings, cookie dialog, and filter widget dynamically.
  - Automatically persists language preference in SQLite database and restores it on next launch.
  - Created comprehensive bilingual HTML user guide web documentation [`guides/index.html`](guides/index.html) and [`guides/en.html`](guides/en.html).
- **Multilingual Natural Language Keyword Explainer**:
  - Automatically generates real-time plain-English and plain-Vietnamese explanations for complex Boolean keyword expressions.

---

## [1.0.7] - 2026-08-27

### ✨ New Features & Multi-Threaded Architecture (Added)
- **Parallel Multi-Threaded Group Scraping (`Threads: 1-10`)**:
  - Selectable concurrent group scraper threads (from 1 to 10) via a streamlined dropdown, enabling parallel scraping across multiple independent Facebook groups at unprecedented speed.
  - Complete decoupling of asynchronous background worker pipelines: **Scraper** (fetching posts & comments), **AI Analyzer** (listening to SQLite database and running automated LLM evaluations), and **Telegram Dispatcher** (polling SQLite database and delivering instant notifications).
- **Flexible Comment Scraping Rule (`Min comments`)**:
  - `0 (Default)`: Skip comment scraping entirely (fetch posts only, fastest scraping speed, saves bandwidth and AI tokens).
  - `-1`: Fetch **ALL** comments and replies for every post.
  - `> 0 (e.g. 5, 20...)`: Scrape a minimum/maximum of $N$ comments per post. If a post has fewer than $N$ comments, it is still scraped and all existing comments are retained without skipping the post.
- **Deep Boolean Logic Keyword Filter & Visual Rule Builder (`KeywordFilterDialog`)**:
  - Full support for Boolean operators `AND`, `OR`, `NOT`, and nested parenthesized expressions `()`.
  - Fullscreen dual-mode configuration dialog: **🧱 Visual Rule Builder** and **✍️ Raw Expression**.
  - Inter-group logic connectors (`OR`, `AND`, `AND NOT`) from Group 2 onwards.
  - Intelligent bidirectional AST conversion: automatically parses keywords and displays real-time natural language explanation.
- **Post Timestamp Cutoff Stopper**:
  - Quick-select 1–7 days ago or custom datetime via DateTimePicker; automatically stops pagination when posts exceed the cutoff timestamp.
- **Visual Help (Tooltip `?` Buttons & Guidance Modals)**:
  - Added `?` help buttons next to **Min comments** and **Threads** for quick reference and recommended best practices.

### 🛠 UI Improvements & Layout Optimization (Changed)
- All 6 scraping parameters (Posts/group, Min comments, Threads, Cutoff time, Infinite loop, Sleep interval) arranged on a single compact horizontal row.
- Removed up/down arrow buttons on numeric spinboxes, enabling direct keyboard input.
- Compacted the live activity log viewer height down to 1/4, maximizing screen area for the Facebook Group List Widget (`GroupListWidget`) with responsive auto-resizing.

### 🐛 Bug Fixes (Fixed)
- Fixed `'NoneType' object has no attribute 'get'` in `comment_scraper.py` using the safe recursive accessor `_safe()`.

---

## [1.0.6] - 2026-08-27

### ✨ New Features & Multi-Level AI Deduplication (Added)
- **`comment_id` Column & AI Deduplication Engine (`ai_analyses`)**:
  - Added `comment_id TEXT` column to `ai_analyses` SQLite table with automatic schema migration and optimized composite index `idx_ai_analyses_post_comment`.
  - Distinguishes match source: saves corresponding `comment_id` when keywords match a comment or reply (`reply_id`), while preserving the parent `post_id`.
  - Multi-level deduplication checker `ai_analysis_exists(post_id, comment_id)`:
    - If `comment_id` is `NULL` / empty (matched main post): Checks existence by `post_id`.
    - If `comment_id` is present (matched comment / reply): Checks existence by both `post_id` and `comment_id`.
  - Integrated pre-flight check before AI API requests in `ScraperThread`, `CommentUpdateWorker`, and `AIAnalysisWorker`: skips previously analyzed posts/comments, saving AI API tokens and eliminating duplicate Telegram alerts.
  - Displays `Comment / Reply ID` and `Match Source` in **Post Details Dialog** (`PostDetailDialog`) and tooltips in AI Analysis History table.

### 🛠 Configuration Standardizations (Changed)
- **Standardized Cookie JSON Input & Clear/Reset (`CookieDialog`)**:
  - Enforced valid JSON format for cookies (exported from *Cookie-Editor* or *J2Team Cookies* extensions via **Export as JSON**).
  - Automatically detects and displays warning alerts when users mistakenly enter semicolon-delimited cookie strings (`c_user=...; xs=...`).
  - Full cookie reset support: clearing the cookie input and clicking *Save* wipes `cookie_string`, `cookie_raw_json`, `fb_dtsg` in SQLite and resets scraper cache `COOKIES`.

### 🐛 Bug Fixes (Fixed)
- **Python 3.10+ / 3.13 Compatibility Module (`src/utils/compat.py`)**:
  - Added `compat.py` compatibility layer automatically mapping `collections.Callable = collections.abc.Callable` (and similar abstract classes) before loading legacy dependencies (`pyreadline` / `seleniumbase`).
  - Resolved `AttributeError: module 'collections' has no attribute 'Callable'` during browser-based group fetching and unit tests.

---

## [1.0.5] - 2026-08-27

### ✨ New Features (Added)
- **Real-time File Logging (`RealtimeFileHandler`)**:
  - Built `RealtimeFileHandler` with immediate buffer flush and `os.fsync(fileno)` on every log line.
  - Users and developers can view `access.log` and `error.log` in real time during scraping sessions without waiting for completion.
  - Automatically detects error/warning records (`❌`, `🛑`, `Error`, `Exception`) and splits them simultaneously into both `error.log` and `access.log`.
  - Background workers (`ScraperThread`, `CommentUpdateWorker`, `GroupFetchWorker`, `AIWorker`, `TelegramWorker`) write directly to file handlers without UI thread contention.
- **Brand Identity & High-Resolution Icons**:
  - Designed high-resolution Facebook Blue + AI Radar Lens & Smart Beacon branding (SVG, 512x512 PNG, and multi-size Windows ICO `16x16` to `256x256`).
  - Automatically integrated into Desktop App windows (`QMainWindow`, `QApplication`), Windows Taskbar, Child Dialogs, and Web Documentation `guides/index.html`.
  - Bundled into PyInstaller `.exe` and Inno Setup installer (`setup.iss`).
- **Flexible Table Header Sorting (Click Header Sort A-Z / Z-A)**:
  - Enabled clicking on any table column header in **Scraped Data** (Tab 2) and **AI Analysis History** (Tab 3) for ascending/descending sort with visual indicator arrows (▲ / ▼).
  - Integrated `SmartTableWidgetItem` for natural numeric sorting on index, Post ID, comment counts, and post timestamps.
- **Over-The-Air (OTA) Updater (Direct `.exe` Download & 1-Click Install)**:
  - Direct download for patch and installer executables (`FacebookNotification_Patch_vX.X.X.exe` or `Setup_vX.X.X.exe`).
  - Confirmation dialog upon download completion: **"Would you like to install now?"**.
  - Clicking **Yes (⚡ Install Now)** automatically launches the `.exe` installer and closes the running app seamlessly.

### 🛠 Improvements & Optimizations (Changed)
- **Optimized Column Layout for Tables**:
  - **Tab 2 (Scraped Data)**: Shortened "Group / Page" to `150px` with text truncation (`...`) and full tooltip; expanded "Post Content" (`Stretch`) across remaining table width.
  - **Tab 3 (AI History)**: Shortened "Group / Page" and "Target / Demand" to `130px`; expanded "Role & Snippet" and "AI Assessment" (`Stretch`) for enhanced legibility.

---

## [1.0.4] - 2026-08-27

### ✨ New Features (Added)
- **Live Media & Video Previews in Post Details Dialog**:
  - Displays image and video thumbnails (110×88px) directly inside the Post Details dialog.
  - Asynchronous background thumbnail downloading without UI freezing.
  - Click any thumbnail to open the original URL in the system default web browser.
  - Videos display a 🎬 indicator with thumbnail; images load directly from Facebook CDN URLs.
- **File-based Logging System**:
  - App activity logs written to `~/.facebook-notification/access.log`.
  - Error logs written separately to `~/.facebook-notification/error.log`.
  - Significantly reduced SQLite database file size and improved DB read/write performance.
- **ZIP Diagnostic Package Export**:
  - "Send Diagnostics to Dev" exports a `.zip` archive containing `access.log`, `error.log`, and `database_dump.sql` (excluding settings with sensitive tokens).
  - System file dialog to choose output destination.

### 🛠 Improvements & Optimizations (Changed)
- **Concurrent Comment Scraping (`ThreadPoolExecutor`)**:
  - Fetches post comments concurrently using up to 4 parallel threads instead of sequentially per post.
  - Substantially boosts overall scraping throughput when groups contain many posts.
  - Thread-safe serialization for `fetch_posts` preventing race conditions.
- **Resilient GraphQL Parsing**:
  - Added `_safe(*keys)` helper to safely traverse deeply nested dictionaries without `AttributeError: 'NoneType' object has no attribute 'get'`.
  - Applied across `extract_group_name`, `extract_creation_time`, `extract_comment_count`, and `extract_post_data` in `group_scraper.py`.

### 🐛 Bug Fixes (Fixed)
- Fixed `❌ Error: 'NoneType' object has no attribute 'get'` when Facebook returns `null` for certain JSON fields in GraphQL responses.
- Fixed Post Details dialog not showing media (only showing link text) — replaced with interactive clickable thumbnails.
- Fixed diagnostics export format from `.diagnose` (raw SQL) to `.zip` (compressed logs + DB dump).

---

## [1.0.3] - 2026-08-20

### ✨ New Features (Added)
- **OpenAI & Compatible LLM Providers Integration**:
  - Supports official OpenAI and all OpenAI-compatible platforms (OpenRouter, DeepSeek, Groq, Ollama, LM Studio, vLLM, Together AI, etc.).
  - Automatic Base URL and `/chat/completions` endpoint normalization.
- **Checkbox Model Management Grid for OpenAI (`OpenAIModelSelectorWidget`)**:
  - Smooth 2-column scrollable grid interface matching the Gemini selector layout.
  - Automatically sorts models alphabetically A–Z and groups Thinking models at the bottom.
  - Quick addition bar **`+ Add custom model`** supporting comma-separated inputs.
  - Dedicated **`🗑 Clear all`** button for OpenAI mode.
  - Quick action tools: **Select All**, **Deselect All**.
- **Auto-Fetch Models from API (`fetch_openai_models_from_api`)**:
  - Automatically queries the `/models` endpoint from any custom Base URL.
  - Filters out non-conversational LLMs (embeddings, whisper, tts, dall-e, vision, moderation, etc.).
- **Asynchronous Non-Blocking Live Model Benchmarking (`TestAIModelsWorker`)**:
  - Runs on a dedicated `QThread` background worker keeping UI responsive.
  - Live progress indicators: `⏳ model_name (Testing...)` highlighted in purple.
  - Dynamic **`⏹ Stop test`** button: turns red `⏹ Stop test (i/N)` allowing cancellation at any moment.
- **Color-Coded Status Badge System**:
  - 🟡 **Yellow / Amber (`#D97706`)**: Newly added model or freshly fetched from API (Untested).
  - 🟣 **Purple / Indigo (`#4F46E5`)**: Currently undergoing live API testing.
  - 🟢 **Green (`#047857`)**: API test succeeded, valid pure JSON returned (`model_name ✓`).
  - 🔴 **Red (`#DC2626` / `#EF4444`)**: API error or Thinking/Reasoner model (automatically disabled).

### 🛠 Improvements & Optimizations (Changed)
- **Server-Sent Events (SSE) Streaming Support (`extract_chat_completion_response`)**:
  - Automatically stitches `data: {"id":...}` chunks into complete JSON when connecting through SSE-enabled proxies/gateways.
  - Always transmits `"stream": False` in request payload to prioritize direct JSON responses.
- **Ultra-Resilient JSON Parser (`parse_json_from_response`)**:
  - Automatically extracts and strips `<think>...</think>` / `<reasoning>...</reasoning>` blocks.
  - Repaires unclosed JSON brackets, handles trailing commas, and processes unescaped newlines (`strict=False`).
- **User Role Fallback**: Automatically merges `role: system` into `role: user` if the target model does not support system prompts.

### 🐛 Bug Fixes (Fixed)
- Fixed `TypeError: verify_single_model_pure_json() unexpected keyword argument 'model'`.
- Fixed raw HTML `<span>` and `<s>` tags appearing in Qt checkbox text.
- Fixed `JSONDecodeError: Line 1` when proxy responses start with `data: {"id":...`.
- Added 56 automated unit tests covering Core Analyzer, SQLite Repository, Worker Threads, and PyQt6 UI.

---

## [1.0.2] - 2026-08-18

### ✨ New Features (Added)
- **Automatic Joined Groups Fetching via Session Cookies**:
  - Supports multiple cookie input formats: raw cookie strings, cURL commands copied from DevTools, or JSON arrays.
  - Automatically extracts `fb_dtsg` security tokens and synchronizes joined groups via mbasic and desktop GraphQL.
- **Real-Time Group Search & Filter**:
  - Instant filtering by group name, URL, or group ID.
  - Accent-insensitive Vietnamese search (typing `lap trinh` matches `Lập Trình Python`).
- **Expanded Group Management Dialogs (`GroupManagerDialog` & `GroupSelectDialog`)**:
  - Fullscreen support, batch URL pasting, filter-based quick selection, and inverted selection.

---

## [1.0.1] - 2026-08-15

### ✨ New Features (Added)
- **SQLite Storage & Deduplication**:
  - Database schema for posts, comments, and AI analysis records.
  - Updates new comments for existing posts without overwriting data.
- **Multi-Format Telegram Notifications**:
  - Real-time alert delivery when posts match keywords / AI evaluation criteria.
  - Detailed HTML notification templates with post permalinks, proof quotes, and AI reasoning.

---

## [1.0.0] - 2026-08-10

### 🚀 Initial Release
- Facebook post and comment scraper built with pure `requests` (no Selenium / Browser automation required).
- PyQt6 graphical user interface with 4 dedicated tabs.
- Google AI Studio (Gemini) integration for automated post evaluation.
- Proxy rotation support and exponential backoff retry mechanism.
