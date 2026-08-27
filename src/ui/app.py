import sys
import os
import json
import time
import re
import math
import queue
import requests
import webbrowser
from datetime import datetime
from urllib.parse import parse_qs
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QPushButton, 
                             QTextEdit, QSpinBox, QComboBox, QTabWidget, QProgressBar, 
                             QGroupBox, QMessageBox, QDialog, QDialogButtonBox, 
                             QFrame, QCheckBox, QScrollArea, QGridLayout,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QAbstractItemView, QMenu, QCompleter, QProgressDialog,
                             QFileDialog)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QUrl, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QDesktopServices, QCursor, QTextDocument, QIntValidator, QColor

# Ensure stdout and stderr handle utf-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import database module
import src.database as database
database.init_db()

# Import notifier module
import src.core.telegram_notifier as telegram_notifier

# Import AI analyzer module
import src.core.ai_analyzer as ai_analyzer
from src.core.updater import check_github_update

# Import scraper modules
from src.utils.helpers import extract_group_id_from_url, save_post_data
from src.core.comment_scraper import fetch_comments as fetch_comments_for_post
from src.core.group_scraper import fetch_posts as fetch_group_posts
from src.core.group_fetcher import fetch_user_joined_groups, parse_cookies_from_any
import src.core.group_scraper as group_post_scraper_v2
import src.core.comment_scraper as comment_scraper
import src.core.page_scraper as post_scraper
import src.core.media_scraper as single_post_image
from src.config.constants import CHROME_DATA_DIR, DATA_DIR, ensure_data_dir, APP_VERSION
from src.core.proxy_utils import select_proxy, normalize_proxy_url
from src.ui.components.tag_widget import ModelTagWidget
from src.ui.components.gemini_model_selector import GeminiModelSelectorWidget
from src.ui.components.openai_model_selector import OpenAIModelSelectorWidget
from src.ui.dialogs.telegram_guide_dialog import TelegramGuideDialog
from src.ui.dialogs.prompt_guide_dialog import PromptGuideDialog
from src.ui.dialogs.cookie_dialog import CookieDialog
from src.ui.dialogs.group_select_dialog import GroupSelectDialog
from src.ui.dialogs.update_dialog import UpdateDialog
from src.ui.workers.group_fetch_worker import GroupFetchWorker
from src.ui.workers.telegram_worker import TelegramDispatcherThread
from src.ui.workers.ai_worker import AIAnalysisWorker, FetchOpenAIModelsWorker, TestAIModelsWorker
from src.ui.workers.scraper_worker import ScraperThread



# ==============================================================================
# Helper: Cookie Management
# ==============================================================================
def parse_cookies(cookie_string):
    """Parse cookie string in format 'key1=value1;key2=value2' or JSON format into dictionary"""
    if not cookie_string:
        return {}
    if isinstance(cookie_string, dict):
        return cookie_string
    
    try:
        c_dict, _, _ = parse_cookies_from_any(str(cookie_string))
        if c_dict:
            return c_dict
    except Exception:
        pass

    cookies = {}
    _JUNK_KEYS = {"hostonly", "httponly", "secure", "session", "name", "value",
                  "domain", "path", "expirationdate", "storeid", "samesite",
                  "expires", "sameparty", "sourceport", "sourcescheme", "partitionkey"}
    for cookie in str(cookie_string).split(';'):
        cookie = cookie.strip()
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            k = key.strip()
            if k and k.lower() not in _JUNK_KEYS:
                cookies[k] = value.strip()
    return cookies


# ==============================================================================
# Widget: Keyword Tag Input (Chip Badges)
# ==============================================================================
class TagWidget(QWidget):
    """Widget nhập từ khóa dạng Tag/Chip linh hoạt"""
    tags_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        self.setLayout(main_layout)

        # Input row
        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Nhập từ khóa rồi nhấn Enter hoặc bấm Thêm...")
        self.input_field.returnPressed.connect(self.add_from_input)
        input_layout.addWidget(self.input_field)

        self.add_btn = QPushButton("➕ Thêm")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        self.add_btn.clicked.connect(self.add_from_input)
        input_layout.addWidget(self.add_btn)
        main_layout.addLayout(input_layout)

        # Scroll area for tags container
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(110)
        self.scroll_area.setMinimumHeight(45)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #D1D5DB; border-radius: 4px; background: #F9FAFB; }")

        self.tags_container = QWidget()
        self.tags_container.setStyleSheet("background: #F9FAFB;")
        self.tags_layout = QHBoxLayout()
        self.tags_layout.setContentsMargins(6, 6, 6, 6)
        self.tags_layout.setSpacing(6)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.tags_container.setLayout(self.tags_layout)
        self.scroll_area.setWidget(self.tags_container)

        main_layout.addWidget(self.scroll_area)

    def add_from_input(self):
        text = self.input_field.text().strip()
        if not text:
            return
        raw_items = [t.strip() for t in text.split(",") if t.strip()]
        for item in raw_items:
            if item not in self.tags:
                self.tags.append(item)
        self.input_field.clear()
        self.refresh_tags_ui()
        self.tags_changed.emit()

    def remove_tag(self, tag_text):
        if tag_text in self.tags:
            self.tags.remove(tag_text)
            self.refresh_tags_ui()
            self.tags_changed.emit()

    def refresh_tags_ui(self):
        while self.tags_layout.count():
            item = self.tags_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        if not self.tags:
            empty_lbl = QLabel("(Không có từ khóa — Mặc định sẽ cào tất cả)")
            empty_lbl.setStyleSheet("color: #6B7280; font-style: italic; font-size: 11px;")
            self.tags_layout.addWidget(empty_lbl)
        else:
            for tag in self.tags:
                chip = QFrame()
                chip.setStyleSheet("""
                    QFrame {
                        background-color: #3B82F6;
                        border-radius: 12px;
                        padding: 2px 6px;
                    }
                """)
                chip_layout = QHBoxLayout()
                chip_layout.setContentsMargins(4, 2, 4, 2)
                chip_layout.setSpacing(4)
                chip.setLayout(chip_layout)

                lbl = QLabel(tag)
                lbl.setStyleSheet("color: white; font-weight: bold; font-size: 11px;")
                chip_layout.addWidget(lbl)

                del_btn = QPushButton("✕")
                del_btn.setFixedSize(16, 16)
                del_btn.setStyleSheet("""
                    QPushButton {
                        background: transparent;
                        color: #E0E7FF;
                        border: none;
                        font-weight: bold;
                        font-size: 10px;
                    }
                    QPushButton:hover { color: #EF4444; }
                """)
                del_btn.clicked.connect(lambda checked, t=tag: self.remove_tag(t))
                chip_layout.addWidget(del_btn)

                self.tags_layout.addWidget(chip)

        self.tags_layout.addStretch()

    def get_tags(self) -> list[str]:
        return self.tags.copy()

    def set_tags(self, tags_list: list[str]):
        self.tags = [t.strip() for t in tags_list if t and t.strip()]
        self.refresh_tags_ui()


# ==============================================================================
# Helper & Dialogs: Dynamic Facebook Group List & Auto URL Parsing
# ==============================================================================
def parse_and_clean_fb_url(url: str) -> str:
    """
    Tự động chuẩn hóa và chuyển link bài viết / link nhóm FB về dạng link group chuẩn:
    - https://www.facebook.com/groups/{group_id_or_slug}/
    Hỗ trợ:
    - https://www.facebook.com/groups/123456789/posts/987654321
    - https://facebook.com/groups/my_group/permalink/987654321/
    - https://m.facebook.com/groups/123456789/?ref=share
    - facebook.com/groups/123456789
    - 123456789 (numeric ID)
    - https://www.facebook.com/share/g/xyz/
    """
    if not url:
        return ""
    url = url.strip()

    # 1. Pure numeric ID (vd: 123456789)
    if url.isdigit():
        return f"https://www.facebook.com/groups/{url}/"

    # 2. Add https:// if missing
    clean_url = url
    if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
        if clean_url.startswith("facebook.com") or clean_url.startswith("www.facebook.com") or clean_url.startswith("m.facebook.com") or clean_url.startswith("web.facebook.com"):
            clean_url = "https://" + clean_url
        elif clean_url.startswith("groups/"):
            clean_url = "https://www.facebook.com/" + clean_url

    # 3. Share URL (vd: https://www.facebook.com/share/g/xyz/)
    match_share = re.search(r'https?://(?:www\.|m\.|web\.)?facebook\.com/share/g/([a-zA-Z0-9._-]+)', clean_url)
    if match_share:
        return f"https://www.facebook.com/share/g/{match_share.group(1)}/"

    # 4. Standard /groups/{identifier}/... (posts, permalink, buy_sell_discussion, etc.)
    match_group = re.search(r'https?://(?:www\.|m\.|web\.|mbasic\.|mobile\.)?facebook\.com/groups/([a-zA-Z0-9._-]+)', clean_url)
    if match_group:
        group_identifier = match_group.group(1)
        if group_identifier not in ('create', 'discover', 'feed', 'notifications', 'joins'):
            return f"https://www.facebook.com/groups/{group_identifier}/"

    # 5. Query param group_id or gid (vd: https://m.facebook.com/story.php?...&group_id=123456)
    match_param = re.search(r'[?&](?:group_id|gid)=(\d+)', clean_url)
    if match_param:
        return f"https://www.facebook.com/groups/{match_param.group(1)}/"

    return url


def show_group_help_dialog(parent=None):
    """Hiển thị hộp thoại hướng dẫn định dạng URL nhóm Facebook"""
    msg = (
        "<b>Hướng dẫn nhập / dán URL nhóm Facebook:</b><br><br>"
        "• <b>URL nhóm:</b> <code>https://www.facebook.com/groups/123456789</code> hoặc <code>https://www.facebook.com/groups/ten-nhom/</code><br>"
        "• <b>URL bài viết bất kỳ trong nhóm:</b> <code>https://www.facebook.com/groups/123456789/posts/987654321</code><br>"
        "• <b>ID nhóm số:</b> <code>123456789</code><br>"
        "• <b>URL chia sẻ nhóm:</b> <code>https://www.facebook.com/share/g/.../</code><br><br>"
        "<i>⚡ Khi bạn nhập hoặc dán link bài viết rồi bấm ra ngoài (blur), hệ thống sẽ <b>tự động phân tích và chuyển đổi thành link nhóm chuẩn</b>.</i>"
    )
    QMessageBox.information(parent, "❓ Hướng dẫn nhập URL nhóm", msg)


class GroupSlugResolverWorker(QThread):
    """Worker chạy ngầm để phân giải Group Slug thành Group ID số và tên nhóm"""
    resolved_signal = pyqtSignal(dict)

    def __init__(self, raw_url: str, cookies: dict = None, parent=None):
        super().__init__(parent)
        self.raw_url = raw_url
        self.cookies = cookies or {}

    def run(self):
        try:
            from src.utils.helpers import resolve_group_details
            res = resolve_group_details(self.raw_url, self.cookies)
            res["input_url"] = self.raw_url
            self.resolved_signal.emit(res)
        except Exception:
            self.resolved_signal.emit({
                "input_url": self.raw_url,
                "group_id": "",
                "name": "",
                "url": self.raw_url,
                "resolved": False
            })


class GroupRowWidget(QWidget):
    """Một dòng trong danh sách nhóm: Tên group, URL group (tự resolve slug thành ID số khi paste/gõ & loading), Nút Xóa"""
    changed = pyqtSignal()
    delete_requested = pyqtSignal(QWidget)
    deduplicate_requested = pyqtSignal()

    def __init__(self, name="", url="", group_id="", last_scraped_at="", parent=None):
        super().__init__(parent)
        self.group_id = str(group_id) if group_id else ""
        self.last_scraped_at = last_scraped_at or ""
        self.resolver_worker = None
        self.resolve_timer = QTimer(self)
        self.resolve_timer.setSingleShot(True)
        self.resolve_timer.timeout.connect(self._on_url_blur)
        self.init_ui(name, url)

    def init_ui(self, name, url):
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)
        self.setLayout(layout)

        # Name input
        self.name_input = QLineEdit(name)
        self.name_input.setPlaceholderText("Tên group (tự động điền)")
        self.name_input.setStyleSheet("padding: 6px; font-size: 12px; border: 1px solid #D1D5DB; border-radius: 4px;")
        self.name_input.textChanged.connect(lambda: self.changed.emit())
        layout.addWidget(self.name_input, stretch=2)

        # URL input (với auto-parse khi paste / gõ / blur)
        self.url_input = QLineEdit(url)
        self.url_input.setPlaceholderText("URL group (vd: https://www.facebook.com/groups/...) hoặc link bài viết")
        self.url_input.setStyleSheet("padding: 6px; font-size: 12px; border: 1px solid #D1D5DB; border-radius: 4px;")
        if self.last_scraped_at:
            self.url_input.setToolTip(f"Lần cào gần nhất: {self.last_scraped_at}")
        self.url_input.textChanged.connect(self._on_url_text_changed)
        self.url_input.editingFinished.connect(self._on_url_blur)
        layout.addWidget(self.url_input, stretch=6)

        # Loading / Status label
        self.status_label = QLabel("")
        self.status_label.setFixedWidth(24)
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet("font-size: 13px;")
        layout.addWidget(self.status_label)

        # Delete button '🗑️'
        self.delete_btn = QPushButton("🗑️")
        self.delete_btn.setFixedSize(30, 30)
        self.delete_btn.setToolTip("Xóa nhóm này")
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #991B1B;
                font-size: 12px;
                border: 1px solid #FECACA;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #FCA5A5; }
        """)
        self.delete_btn.clicked.connect(lambda: self.delete_requested.emit(self))
        layout.addWidget(self.delete_btn)

    def _on_url_text_changed(self):
        self.changed.emit()
        raw = self.url_input.text().strip()
        if raw.startswith("http") or "facebook.com" in raw or "/groups/" in raw:
            # Tự động kích hoạt phân giải sau 350ms khi dán hoặc gõ xong
            self.resolve_timer.start(350)

    def _get_parent_cookies(self):
        # 1. Tìm từ widget cha
        p = self.parent()
        while p:
            if hasattr(p, 'cookies') and p.cookies:
                return p.cookies
            if hasattr(p, 'cookie_string') and p.cookie_string:
                return parse_cookies(p.cookie_string)
            p = p.parent()
        # 2. Tìm từ database settings
        try:
            from src.database.repository import get_all_settings
            st = get_all_settings()
            c_str = st.get("cookies", "")
            if c_str:
                return parse_cookies(c_str)
        except Exception:
            pass
        return {}

    def _on_url_blur(self):
        """Tự động phân tích, phân giải slug -> ID số và chuẩn hóa link group"""
        raw = self.url_input.text().strip()
        if not raw:
            return
        parsed = parse_and_clean_fb_url(raw)

        # 1. Nếu đã là URL chứa ID số (vd: /groups/123456789/)
        m_num = re.search(r'/groups/(\d{4,})(?:/|$)', parsed)
        if m_num:
            gid = m_num.group(1)
            self.group_id = gid
            clean_canonical = f"https://www.facebook.com/groups/{gid}/"
            if clean_canonical != raw:
                self.url_input.blockSignals(True)
                self.url_input.setText(clean_canonical)
                self.url_input.blockSignals(False)
            self.status_label.setText("✓")
            self.status_label.setStyleSheet("color: #059669; font-weight: bold;")
            QTimer.singleShot(2500, lambda: self.status_label.setText(""))
            self.changed.emit()
            self.deduplicate_requested.emit()
            return

        # 2. Nếu là slug (vd: /groups/congdongin3dvietnam/) hoặc link chia sẻ
        m_slug = re.search(r'/groups/([a-zA-Z0-9._-]+)', parsed)
        if m_slug:
            slug = m_slug.group(1).strip()
            if slug not in ('create', 'discover', 'feed', 'notifications', 'joins'):
                self.status_label.setText("⏳")
                self.status_label.setStyleSheet("color: #D97706; font-weight: bold;")
                self.status_label.setToolTip("Đang tìm ID số của nhóm từ Facebook...")
                cookies = self._get_parent_cookies()

                self.resolver_worker = GroupSlugResolverWorker(parsed, cookies=cookies)
                self.resolver_worker.resolved_signal.connect(self._on_slug_resolved)
                self.resolver_worker.start()
                return

    def _on_slug_resolved(self, res: dict):
        self.status_label.setText("")
        if res.get("resolved") and res.get("group_id"):
            gid = res["group_id"]
            self.group_id = gid
            canonical_url = f"https://www.facebook.com/groups/{gid}/"
            self.url_input.blockSignals(True)
            self.url_input.setText(canonical_url)
            self.url_input.blockSignals(False)

            if not self.name_input.text().strip() and res.get("name"):
                self.name_input.blockSignals(True)
                self.name_input.setText(res["name"])
                self.name_input.blockSignals(False)

            self.status_label.setText("✓")
            self.status_label.setStyleSheet("color: #059669; font-weight: bold;")
            QTimer.singleShot(2500, lambda: self.status_label.setText(""))
        else:
            self.status_label.setText("⚠️")
            self.status_label.setStyleSheet("color: #DC2626;")
            self.status_label.setToolTip("Không tìm được ID số. Nhóm có thể yêu cầu Cookie hoặc là nhóm kín.")

        self.changed.emit()
        self.deduplicate_requested.emit()

    def get_data(self) -> dict:
        return {
            "name": self.name_input.text().strip(),
            "url": self.url_input.text().strip(),
            "group_id": self.group_id,
            "last_scraped_at": self.last_scraped_at
        }

    def set_data(self, name: str, url: str, group_id: str = "", last_scraped_at: str = ""):
        self.name_input.blockSignals(True)
        self.url_input.blockSignals(True)
        self.name_input.setText(name)
        self.url_input.setText(url)
        self.group_id = str(group_id) if group_id else ""
        self.last_scraped_at = last_scraped_at or ""
        self.name_input.blockSignals(False)
        self.url_input.blockSignals(False)

    def set_inputs_enabled(self, enabled: bool):
        self.name_input.setEnabled(enabled)
        self.url_input.setEnabled(enabled)
        self.delete_btn.setEnabled(enabled)


class BatchGroupInputDialog(QDialog):
    """Dialog phụ để dán nhanh nhiều link / ID nhóm cùng lúc (mỗi dòng 1 link)"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📥 Nhập nhanh nhiều link nhóm (Batch Paste)")
        self.resize(560, 420)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        self.setLayout(layout)

        label = QLabel("<b>Dán danh sách URL hoặc link bài viết nhóm (mỗi dòng 1 link):</b>")
        label.setStyleSheet("color: #1F2937; font-size: 13px;")
        layout.addWidget(label)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "https://www.facebook.com/groups/123456789\n"
            "https://www.facebook.com/groups/laptrinhpython/posts/998877\n"
            "https://facebook.com/groups/congdongit/permalink/112233/\n"
            "668881464321714\n"
            "..."
        )
        self.text_edit.setStyleSheet("padding: 8px; font-family: Consolas, monospace; font-size: 12px; border: 1px solid #D1D5DB; border-radius: 4px;")
        layout.addWidget(self.text_edit)

        hint = QLabel("<i>⚡ Các link bài viết sẽ tự động được phân tích và chuẩn hóa thành link nhóm chuẩn.</i>")
        hint.setStyleSheet("color: #6B7280; font-size: 11px;")
        layout.addWidget(hint)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.setStyleSheet("padding: 6px 14px; font-size: 12px;")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        import_btn = QPushButton("➕ Thêm vào danh sách")
        import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                padding: 6px 16px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        import_btn.clicked.connect(self.accept)
        btn_layout.addWidget(import_btn)

        layout.addLayout(btn_layout)

    def get_parsed_groups(self) -> list[dict]:
        raw_text = self.text_edit.toPlainText().strip()
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        result = []
        for line in lines:
            parsed_url = parse_and_clean_fb_url(line)
            if parsed_url:
                result.append({"name": "", "url": parsed_url, "group_id": ""})
        return result


class GroupManagerDialog(QDialog):
    """Cửa sổ phóng to để quản lý danh sách nhóm Facebook với đầy đủ tính năng & bộ lọc Filter"""
    def __init__(self, initial_groups: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Quản lý danh sách Nhóm Facebook")
        self.resize(860, 600)
        self.setMinimumSize(680, 420)
        self.row_widgets: list[GroupRowWidget] = []
        self.init_ui(initial_groups)

    def init_ui(self, initial_groups: list[dict]):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(14, 14, 14, 14)
        main_layout.setSpacing(8)
        self.setLayout(main_layout)

        # Header toolbar
        header_layout = QHBoxLayout()
        self.title_label = QLabel("<b>📋 Danh sách Nhóm Facebook:</b>")
        self.title_label.setStyleSheet("font-size: 14px; color: #1E3A8A;")
        header_layout.addWidget(self.title_label)

        self.count_badge = QLabel("0 nhóm")
        self.count_badge.setStyleSheet("background-color: #DBEAFE; color: #1E40AF; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;")
        header_layout.addWidget(self.count_badge)

        header_layout.addStretch()

        # Cookie fetch button
        self.cookie_fetch_btn = QPushButton("🌐 Lấy nhóm từ Cookie")
        self.cookie_fetch_btn.setToolTip("Tải danh sách nhóm Facebook mà tài khoản đã tham gia qua Cookie")
        self.cookie_fetch_btn.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.cookie_fetch_btn.clicked.connect(self.trigger_cookie_fetch)
        header_layout.addWidget(self.cookie_fetch_btn)

        # Batch paste button
        batch_btn = QPushButton("📥 Dán nhiều link")
        batch_btn.setToolTip("Dán nhanh nhiều link / ID nhóm cùng lúc")
        batch_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B5CF6;
                color: white;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #7C3AED; }
        """)
        batch_btn.clicked.connect(self.open_batch_input)
        header_layout.addWidget(batch_btn)

        # Help button
        help_btn = QPushButton("❓ Hướng dẫn")
        help_btn.setToolTip("Xem hướng dẫn định dạng URL")
        help_btn.setStyleSheet("""
            QPushButton {
                background-color: #E0E7FF;
                color: #3730A3;
                font-weight: bold;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #C7D2FE; }
        """)
        help_btn.clicked.connect(lambda: show_group_help_dialog(self))
        header_layout.addWidget(help_btn)

        # Clear all button
        clear_all_btn = QPushButton("🧹 Xóa tất cả")
        clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                padding: 6px 12px;
                border-radius: 4px;
                font-size: 12px;
                border: 1px solid #D1D5DB;
            }
            QPushButton:hover { background-color: #E5E7EB; color: #111827; }
        """)
        clear_all_btn.clicked.connect(self.clear_all_rows)
        header_layout.addWidget(clear_all_btn)

        # Add button
        add_btn = QPushButton("➕ Thêm nhóm")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        add_btn.clicked.connect(lambda: self.add_row())
        header_layout.addWidget(add_btn)

        main_layout.addLayout(header_layout)

        # Search / Filter Bar
        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(6)
        
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("🔍 Lọc nhóm theo tên, link URL hoặc ID nhóm (gõ có dấu hoặc không dấu)...")
        self.filter_input.setStyleSheet("padding: 6px 10px; font-size: 12px; border: 1px solid #D1D5DB; border-radius: 4px; background: white;")
        self.filter_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.filter_input, stretch=1)

        clear_filter_btn = QPushButton("❌")
        clear_filter_btn.setToolTip("Xóa bộ lọc")
        clear_filter_btn.setFixedSize(26, 26)
        clear_filter_btn.setStyleSheet("background: #F3F4F6; border: 1px solid #D1D5DB; border-radius: 13px; font-size: 10px;")
        clear_filter_btn.clicked.connect(lambda: self.filter_input.clear())
        filter_layout.addWidget(clear_filter_btn)

        main_layout.addLayout(filter_layout)

        # Scroll Area for rows
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #D1D5DB; border-radius: 6px; background: #FFFFFF; }")

        self.container = QWidget()
        self.container.setStyleSheet("background: #FFFFFF;")
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(10, 10, 10, 10)
        self.rows_layout.setSpacing(6)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container.setLayout(self.rows_layout)
        self.scroll_area.setWidget(self.container)

        main_layout.addWidget(self.scroll_area)

        # Bottom action buttons
        bottom_layout = QHBoxLayout()
        hint = QLabel("💡 <i>Gợi ý: Dán link bài viết rồi bấm ra ngoài để tự động chuyển thành link nhóm.</i>")
        hint.setStyleSheet("color: #6B7280; font-size: 12px;")
        bottom_layout.addWidget(hint)

        bottom_layout.addStretch()

        cancel_btn = QPushButton("❌ Hủy")
        cancel_btn.setStyleSheet("padding: 8px 18px; font-size: 13px;")
        cancel_btn.clicked.connect(self.reject)
        bottom_layout.addWidget(cancel_btn)

        save_btn = QPushButton("💾 Lưu & Áp dụng")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                padding: 8px 22px;
                border-radius: 5px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        save_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(save_btn)

        main_layout.addLayout(bottom_layout)

        # Populate rows
        for g in initial_groups:
            self.add_row(name=g.get("name", ""), url=g.get("url", ""), group_id=g.get("group_id", ""), last_scraped_at=g.get("last_scraped_at", ""))
        if not initial_groups:
            self.add_row()
        self.update_count_badge()

    def add_row(self, name="", url="", group_id="", last_scraped_at="") -> GroupRowWidget:
        row = GroupRowWidget(name=name, url=url, group_id=group_id, last_scraped_at=last_scraped_at, parent=self)
        row.delete_requested.connect(self.remove_row)
        row.changed.connect(self.update_count_badge)
        row.deduplicate_requested.connect(self.deduplicate_rows)
        self.row_widgets.append(row)
        self.rows_layout.addWidget(row)
        self.update_count_badge()
        return row

    def deduplicate_rows(self):
        """Khử trùng lặp giữa các dòng nhóm (theo Group ID hoặc URL)"""
        seen = set()
        to_remove = []
        for r in self.row_widgets:
            data = r.get_data()
            gid = str(data.get("group_id") or "").strip()
            url = str(data.get("url") or "").strip()
            if not gid and not url:
                continue
            key = f"id:{gid}" if gid else f"url:{url}"
            if key in seen:
                to_remove.append(r)
            else:
                seen.add(key)
        for r in to_remove:
            self.remove_row(r)

    def remove_row(self, row_widget: GroupRowWidget):
        if row_widget in self.row_widgets:
            self.row_widgets.remove(row_widget)
            self.rows_layout.removeWidget(row_widget)
            row_widget.deleteLater()
            self.update_count_badge()

    def clear_all_rows(self):
        while self.row_widgets:
            row = self.row_widgets.pop()
            self.rows_layout.removeWidget(row)
            row.deleteLater()
        self.update_count_badge()

    def update_count_badge(self):
        valid_count = len([r for r in self.row_widgets if r.get_data()["url"] or r.get_data()["name"]])
        total_rows = len(self.row_widgets)
        self.count_badge.setText(f"{valid_count} nhóm" if valid_count == total_rows else f"{valid_count}/{total_rows} nhóm")

    def apply_filter(self):
        query = self.filter_input.text().strip().lower()
        for row in self.row_widgets:
            data = row.get_data()
            name = (data.get("name") or "").lower()
            url = (data.get("url") or "").lower()
            gid = (data.get("group_id") or "").lower()
            if not query or query in name or query in url or query in gid:
                row.setVisible(True)
            else:
                row.setVisible(False)

    def trigger_cookie_fetch(self):
        parent_app = self.parent()
        while parent_app and not hasattr(parent_app, 'fetch_groups_from_cookie'):
            parent_app = parent_app.parent()
        if parent_app and hasattr(parent_app, 'fetch_groups_from_cookie'):
            # Gọi trực tiếp tiến trình tải nhóm của parent
            parent_app.fetch_groups_from_cookie(
                callback=self._on_groups_imported_from_cookie
            )
        else:
            QMessageBox.warning(self, "Chưa sẵn sàng", "Không tìm thấy cấu hình cửa sổ chính để tải nhóm.")

    def _on_groups_imported_from_cookie(self, selected_groups: list[dict], mode: str):
        if mode == "replace":
            self.clear_all_rows()
            for g in selected_groups:
                self.add_row(name=g.get("name", ""), url=g.get("url", ""), group_id=g.get("group_id", ""))
        else:
            existing_urls = {r.get_data()["url"] for r in self.row_widgets if r.get_data()["url"]}
            for g in selected_groups:
                if g.get("url") not in existing_urls:
                    self.add_row(name=g.get("name", ""), url=g.get("url", ""), group_id=g.get("group_id", ""))
                    existing_urls.add(g.get("url"))

    def open_batch_input(self):
        dialog = BatchGroupInputDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_groups = dialog.get_parsed_groups()
            for g in new_groups:
                self.add_row(name=g["name"], url=g["url"], group_id=g["group_id"])

    def get_groups(self) -> list[dict]:
        return [r.get_data() for r in self.row_widgets if r.get_data()["url"] or r.get_data()["name"]]


class GroupListWidget(QWidget):
    """Widget quản lý danh sách động các nhóm Facebook (tự động đồng bộ SQLite)"""
    groups_changed = pyqtSignal()
    fetch_cookie_groups_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.row_widgets: list[GroupRowWidget] = []
        self._sync_enabled = True
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)
        self.setLayout(main_layout)

        # Header toolbar with "+ Thêm nhóm", "🌐 Lấy nhóm từ Cookie", "⛶ Phóng to", and "❓ Hướng dẫn" button
        header_layout = QHBoxLayout()
        title_label = QLabel("Danh sách Nhóm Facebook (Tự động lưu vào SQLite):")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px; color: #1F2937;")
        header_layout.addWidget(title_label)

        header_layout.addStretch()

        # Cookie Fetch button
        self.fetch_cookie_btn = QPushButton("🌐 Lấy nhóm từ Cookie")
        self.fetch_cookie_btn.setToolTip("Tự động tải danh sách nhóm Facebook mà tài khoản đã tham gia từ Cookie")
        self.fetch_cookie_btn.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-weight: bold;
                padding: 5px 12px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #6D28D9; }
            QPushButton:disabled { background-color: #E5E7EB; color: #9CA3AF; }
        """)
        self.fetch_cookie_btn.clicked.connect(lambda: self.fetch_cookie_groups_requested.emit())
        header_layout.addWidget(self.fetch_cookie_btn)

        # 1 Help button for the whole widget
        self.help_btn = QPushButton("❓ Hướng dẫn")
        self.help_btn.setToolTip("Hướng dẫn lấy và dán URL nhóm chính xác")
        self.help_btn.setStyleSheet("""
            QPushButton {
                background-color: #E0E7FF;
                color: #3730A3;
                font-weight: bold;
                padding: 5px 10px;
                border-radius: 4px;
                font-size: 12px;
                border: 1px solid #C7D2FE;
            }
            QPushButton:hover { background-color: #C7D2FE; }
            QPushButton:disabled { background-color: #E5E7EB; color: #9CA3AF; }
        """)
        self.help_btn.clicked.connect(lambda: show_group_help_dialog(self))
        header_layout.addWidget(self.help_btn)

        # Maximize / Expand button
        self.expand_btn = QPushButton("⛶ Phóng to")
        self.expand_btn.setToolTip("Mở cửa sổ phóng to để quản lý danh sách nhóm thuận tiện hơn")
        self.expand_btn.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #4338CA;
                font-weight: bold;
                padding: 5px 12px;
                border-radius: 4px;
                font-size: 12px;
                border: 1px solid #C7D2FE;
            }
            QPushButton:hover { background-color: #E0E7FF; }
            QPushButton:disabled { background-color: #E5E7EB; color: #9CA3AF; }
        """)
        self.expand_btn.clicked.connect(self.open_expand_dialog)
        header_layout.addWidget(self.expand_btn)

        # Add button
        self.add_btn = QPushButton("➕ Thêm nhóm")
        self.add_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                padding: 5px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.add_btn.clicked.connect(lambda: self.add_row())
        header_layout.addWidget(self.add_btn)

        main_layout.addLayout(header_layout)

        # Scroll area for rows (Tăng độ cao lên cho thoáng)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(160)
        self.scroll_area.setMaximumHeight(280)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #D1D5DB; border-radius: 4px; background: #FFFFFF; }")

        self.container = QWidget()
        self.container.setStyleSheet("background: #FFFFFF;")
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(6, 6, 6, 6)
        self.rows_layout.setSpacing(4)
        self.rows_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.container.setLayout(self.rows_layout)
        self.scroll_area.setWidget(self.container)

        main_layout.addWidget(self.scroll_area)

    def open_expand_dialog(self):
        dialog = GroupManagerDialog(initial_groups=self.get_groups(), parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            updated_groups = dialog.get_groups()
            self.set_groups(updated_groups)
            self.save_to_db()
            self.groups_changed.emit()

    def add_row(self, name="", url="", group_id="", last_scraped_at="", auto_save=True) -> GroupRowWidget:
        row = GroupRowWidget(name=name, url=url, group_id=group_id, last_scraped_at=last_scraped_at, parent=self)
        row.changed.connect(self._on_row_changed)
        row.delete_requested.connect(self.remove_row)
        row.deduplicate_requested.connect(self.deduplicate_groups)
        self.row_widgets.append(row)
        self.rows_layout.addWidget(row)
        if auto_save and self._sync_enabled:
            self.save_to_db()
            self.groups_changed.emit()
        return row

    def deduplicate_groups(self):
        """Khử trùng lặp giữa các dòng nhóm (theo Group ID hoặc URL)"""
        seen = set()
        to_remove = []
        for r in self.row_widgets:
            data = r.get_data()
            gid = str(data.get("group_id") or "").strip()
            url = str(data.get("url") or "").strip()
            if not gid and not url:
                continue
            key = f"id:{gid}" if gid else f"url:{url}"
            if key in seen:
                to_remove.append(r)
            else:
                seen.add(key)
        if to_remove:
            self._sync_enabled = False
            for r in to_remove:
                self.remove_row(r)
            self._sync_enabled = True
            self.save_to_db()
            self.groups_changed.emit()

    def remove_row(self, row_widget: GroupRowWidget):
        if row_widget in self.row_widgets:
            self.row_widgets.remove(row_widget)
            self.rows_layout.removeWidget(row_widget)
            row_widget.deleteLater()
            if self._sync_enabled:
                self.save_to_db()
                self.groups_changed.emit()

    def clear_rows(self):
        while self.row_widgets:
            row = self.row_widgets.pop()
            self.rows_layout.removeWidget(row)
            row.deleteLater()

    def _on_row_changed(self):
        if self._sync_enabled:
            self.save_to_db()
            self.groups_changed.emit()

    def get_groups(self) -> list[dict]:
        return [r.get_data() for r in self.row_widgets if r.get_data()["url"] or r.get_data()["name"]]

    def get_urls(self) -> list[str]:
        return [r.get_data()["url"] for r in self.row_widgets if r.get_data()["url"]]

    def set_groups(self, groups: list[dict]):
        self._sync_enabled = False
        self.clear_rows()
        for g in groups:
            self.add_row(name=g.get("name", ""), url=g.get("url", ""), group_id=g.get("group_id", ""), last_scraped_at=g.get("last_scraped_at", ""), auto_save=False)
        if not groups:
            self.add_row(auto_save=False)
        self._sync_enabled = True

    def save_to_db(self):
        groups = self.get_groups()
        database.save_all_groups(groups)

    def setEnabled(self, enabled: bool):
        super().setEnabled(enabled)
        self.add_btn.setEnabled(enabled)
        self.expand_btn.setEnabled(enabled)
        self.help_btn.setEnabled(enabled)
        self.fetch_cookie_btn.setEnabled(enabled)
        for r in self.row_widgets:
            r.set_inputs_enabled(enabled)


# ==============================================================================
# Dialog: Post Detail & Comments Simulation (PostDetailDialog)
# ==============================================================================
class PostDetailDialog(QDialog):
    """Dialog hiển thị chi tiết bài viết mô phỏng Facebook (nội dung, ảnh/video, comment và reply lồng nhau)"""
    def __init__(self, post_data, parent=None):
        super().__init__(parent)
        self.post_data = post_data or {}
        post_id = str(self.post_data.get("post_id", "N/A"))
        self.setWindowTitle(f"Chi tiết bài viết — ID: {post_id}")
        self.resize(850, 680)
        self.setStyleSheet("""
            QDialog {
                background-color: #F3F4F6;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # 1. Header Card
        header_card = QFrame()
        header_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(12, 10, 12, 10)

        info_layout = QVBoxLayout()
        group_name = self.post_data.get("group_name") or self.post_data.get("page_name") or "Facebook Group/Page"
        group_label = QLabel(f"📂 <b>{group_name}</b>")
        group_label.setStyleSheet("font-size: 15px; color: #1E3A8A;")
        info_layout.addWidget(group_label)

        # Time formatting
        creation_time = self.post_data.get("creation_time")
        created_at_str = self.post_data.get("created_at", "")
        time_display = ""
        if creation_time:
            try:
                dt = datetime.fromtimestamp(int(creation_time))
                time_display = dt.strftime("%d/%m/%Y %H:%M:%S")
            except Exception:
                time_display = str(creation_time)
        elif created_at_str:
            time_display = str(created_at_str)

        meta_text = f"🆔 Post ID: <code>{post_id}</code>"
        if time_display:
            meta_text += f" | 🕒 {time_display}"
        
        meta_label = QLabel(meta_text)
        meta_label.setStyleSheet("font-size: 12px; color: #6B7280;")
        info_layout.addWidget(meta_label)
        h_layout.addLayout(info_layout)
        h_layout.addStretch()

        # Open in browser button
        permalink = self.post_data.get("permalink") or f"https://www.facebook.com/{post_id}"
        open_fb_btn = QPushButton("🔗 Mở trên Facebook")
        open_fb_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 14px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        open_fb_btn.clicked.connect(lambda: webbrowser.open(permalink))
        h_layout.addWidget(open_fb_btn)
        layout.addWidget(header_card)

        # AI Analysis Card (if available in SQLite)
        ai_info = database.get_ai_analysis_by_post_id(post_id)
        if ai_info:
            ai_card = QFrame()
            ai_card.setStyleSheet("""
                QFrame {
                    background-color: #F5F3FF;
                    border: 1px solid #DDD6FE;
                    border-radius: 8px;
                    padding: 10px;
                }
            """)
            ai_card_layout = QVBoxLayout(ai_card)
            ai_card_layout.setContentsMargins(12, 10, 12, 10)
            ai_card_layout.setSpacing(6)

            ai_top = QHBoxLayout()
            model_tag = ai_info.get("model_used") or "AI"
            ai_title = QLabel(f"🤖 <b>Kết quả Đánh giá AI</b> (Model: <code>{model_tag}</code>)")
            ai_title.setStyleSheet("font-size: 13px; color: #5B21B6;")
            ai_top.addWidget(ai_title)
            ai_top.addStretch()

            if ai_info.get("should_notify"):
                notify_badge = QLabel("🔔 KHỚP THÔNG BÁO")
                notify_badge.setStyleSheet("background-color: #DCFCE7; color: #166534; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;")
                ai_top.addWidget(notify_badge)
            else:
                skip_badge = QLabel("⚪ BỎ QUA")
                skip_badge.setStyleSheet("background-color: #F1F5F9; color: #64748B; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;")
                ai_top.addWidget(skip_badge)

            ai_card_layout.addLayout(ai_top)


            target_name = ai_info.get("target_name") or ai_info.get("device_name") or "N/A"
            dev_price = ai_info.get("price") or ai_info.get("price_or_budget") or "Thỏa thuận / Không rõ"
            actor_role = ai_info.get("actor_role") or ai_info.get("seller_type") or "N/A"
            matched_snippet = ai_info.get("matched_snippet") or ai_info.get("seller_snippet") or ""
            reason = ai_info.get("reason") or ""

            details_text = f"🎯 <b>Mục tiêu:</b> {target_name} | 💰 <b>Giá/Lương:</b> {dev_price} | 📍 <b>Vai trò:</b> {actor_role}"
            if matched_snippet:
                details_text += f"<br>💬 <b>Trích đoạn:</b> <i>\"{matched_snippet}\"</i>"
            if reason:
                details_text += f"<br>💡 <b>Lý do AI:</b> <i>{reason}</i>"


            ai_content_lbl = QLabel(details_text)
            ai_content_lbl.setWordWrap(True)
            ai_content_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            ai_content_lbl.setStyleSheet("font-size: 12px; color: #374151;")
            ai_card_layout.addWidget(ai_content_lbl)

            layout.addWidget(ai_card)

        # 2. Main Scroll Area for Post Content & Comments
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: #FFFFFF;
            }
        """)

        content_widget = QWidget()
        content_widget.setStyleSheet("background-color: #FFFFFF;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(16, 16, 16, 16)
        content_layout.setSpacing(14)

        # Post Message Content
        msg_label = QLabel("📝 <b>Nội dung bài viết:</b>")
        msg_label.setStyleSheet("font-size: 13px; font-weight: bold; color: #374151;")
        content_layout.addWidget(msg_label)

        msg_box = QTextEdit()
        msg_box.setReadOnly(True)
        msg_box.setPlainText(self.post_data.get("message", "(Không có nội dung văn bản)"))
        msg_box.setMaximumHeight(150)
        msg_box.setStyleSheet("""
            QTextEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                color: #1F2937;
            }
        """)
        content_layout.addWidget(msg_box)

        # Photos / Media (if any)
        photos = self.post_data.get("photos", [])
        videos = self.post_data.get("videos", [])
        if photos or videos:
            media_box = QFrame()
            media_box.setStyleSheet("background-color: #EFF6FF; border: 1px dashed #93C5FD; border-radius: 6px; padding: 8px;")
            mb_layout = QVBoxLayout(media_box)
            mb_layout.setContentsMargins(8, 6, 8, 6)
            media_info = QLabel(f"📷 <b>Đính kèm:</b> {len(photos)} ảnh, {len(videos)} video")
            media_info.setStyleSheet("font-size: 12px; color: #1E40AF;")
            mb_layout.addWidget(media_info)
            for idx, p in enumerate(photos, 1):
                p_url = p.get("url") if isinstance(p, dict) else str(p)
                if p_url:
                    lbl = QLabel(f"  • Ảnh #{idx}: <a href='{p_url}'>{p_url[:80]}...</a>")
                    lbl.setOpenExternalLinks(True)
                    lbl.setStyleSheet("font-size: 11px; color: #2563EB;")
                    mb_layout.addWidget(lbl)
            content_layout.addWidget(media_box)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("color: #E5E7EB;")
        content_layout.addWidget(divider)

        # Comments Section
        comments = self.post_data.get("comments", [])
        cmt_header = QLabel(f"💬 <b>Danh sách Bình luận & Phản hồi ({len(comments)} comments)</b>")
        cmt_header.setStyleSheet("font-size: 14px; font-weight: bold; color: #111827; margin-top: 4px;")
        content_layout.addWidget(cmt_header)

        if not comments:
            empty_cmt = QLabel("<i>Chưa có bình luận nào được lưu cho bài viết này.</i>")
            empty_cmt.setStyleSheet("color: #9CA3AF; font-size: 12px; padding: 10px;")
            content_layout.addWidget(empty_cmt)
        else:
            for c_idx, cmt in enumerate(comments, 1):
                c_card = QFrame()
                c_card.setStyleSheet("""
                    QFrame {
                        background-color: #F8FAFC;
                        border: 1px solid #E2E8F0;
                        border-radius: 8px;
                    }
                """)
                cc_layout = QVBoxLayout(c_card)
                cc_layout.setContentsMargins(12, 10, 12, 10)
                cc_layout.setSpacing(6)

                # Comment Top Row: ID & Reactions
                c_top = QHBoxLayout()
                c_id_lbl = QLabel(f"<b># {c_idx}</b> | ID: <code>{cmt.get('comment_id', 'N/A')}</code>")
                c_id_lbl.setStyleSheet("font-size: 12px; color: #475569;")
                c_top.addWidget(c_id_lbl)
                c_top.addStretch()

                reactions = str(cmt.get("reaction_count") or "0")
                if reactions and reactions != "0":
                    react_badge = QLabel(f"❤️ {reactions}")
                    react_badge.setStyleSheet("background-color: #FEE2E2; color: #DC2626; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;")
                    c_top.addWidget(react_badge)
                cc_layout.addLayout(c_top)

                # Comment Text
                c_text = cmt.get("text", "") or "<i>(Bình luận không có chữ)</i>"
                c_text_lbl = QLabel(c_text)
                c_text_lbl.setWordWrap(True)
                c_text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                c_text_lbl.setStyleSheet("font-size: 13px; color: #1E293B; padding: 4px 0;")
                cc_layout.addWidget(c_text_lbl)

                # Nested Replies
                replies = cmt.get("replies", [])
                if replies:
                    replies_frame = QFrame()
                    replies_frame.setStyleSheet("""
                        QFrame {
                            background-color: #EDF2F7;
                            border-left: 3px solid #3B82F6;
                            border-radius: 4px;
                            margin-left: 16px;
                            margin-top: 4px;
                        }
                    """)
                    rf_layout = QVBoxLayout(replies_frame)
                    rf_layout.setContentsMargins(10, 8, 10, 8)
                    rf_layout.setSpacing(6)

                    rf_title = QLabel(f"↳ <b>{len(replies)} phản hồi:</b>")
                    rf_title.setStyleSheet("font-size: 11px; color: #2563EB; font-weight: bold;")
                    rf_layout.addWidget(rf_title)

                    for r_idx, rep in enumerate(replies, 1):
                        r_item = QFrame()
                        r_item.setStyleSheet("background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px;")
                        ri_layout = QVBoxLayout(r_item)
                        ri_layout.setContentsMargins(8, 6, 8, 6)

                        r_top = QHBoxLayout()
                        r_id = QLabel(f"ID: <code>{rep.get('reply_id', 'N/A')}</code>")
                        r_id.setStyleSheet("font-size: 11px; color: #64748B;")
                        r_top.addWidget(r_id)
                        r_top.addStretch()

                        r_react = str(rep.get("reaction_count") or "0")
                        if r_react and r_react != "0":
                            rb = QLabel(f"❤️ {r_react}")
                            rb.setStyleSheet("background-color: #FEE2E2; color: #DC2626; padding: 1px 6px; border-radius: 8px; font-size: 10px;")
                            r_top.addWidget(rb)
                        ri_layout.addLayout(r_top)

                        r_text = rep.get("text", "") or "<i>(Phản hồi không có chữ)</i>"
                        r_lbl = QLabel(r_text)
                        r_lbl.setWordWrap(True)
                        r_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
                        r_lbl.setStyleSheet("font-size: 12px; color: #334155;")
                        ri_layout.addWidget(r_lbl)

                        rf_layout.addWidget(r_item)
                    cc_layout.addWidget(replies_frame)

                content_layout.addWidget(c_card)

        content_layout.addStretch()
        scroll.setWidget(content_widget)
        layout.addWidget(scroll)

        # 3. Bottom Button Row
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        close_btn = QPushButton("Đóng")
        close_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 8px 20px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #4B5563; }
        """)
        close_btn.clicked.connect(self.accept)
        bottom_layout.addWidget(close_btn)
        layout.addLayout(bottom_layout)


# ==============================================================================
# Dialog: LogViewerDialog (Phóng to xem toàn bộ Logs)
# ==============================================================================
class LogViewerDialog(QDialog):
    """Cửa sổ phóng to xem toàn bộ Nhật ký hoạt động với tìm kiếm, sao chép và realtime streaming"""
    clear_requested = pyqtSignal()

    def __init__(self, initial_text: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Nhật ký hoạt động chi tiết (Logs Viewer)")
        self.resize(920, 620)
        self.setMinimumSize(600, 400)
        self.init_ui(initial_text)

    def init_ui(self, initial_text: str):
        layout = QVBoxLayout()
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        self.setLayout(layout)

        # Top Bar: Search & Controls
        top_layout = QHBoxLayout()
        
        search_label = QLabel("🔍 Tìm kiếm:")
        search_label.setStyleSheet("font-weight: bold; color: #374151; font-size: 12px;")
        top_layout.addWidget(search_label)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Nhập từ khóa tìm kiếm trong logs...")
        self.search_input.setStyleSheet("padding: 5px 8px; font-size: 12px; border: 1px solid #D1D5DB; border-radius: 4px;")
        self.search_input.returnPressed.connect(self.search_next)
        self.search_input.textChanged.connect(self.on_search_text_changed)
        top_layout.addWidget(self.search_input, stretch=2)

        find_next_btn = QPushButton("Tiếp theo ⬇")
        find_next_btn.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        find_next_btn.clicked.connect(self.search_next)
        top_layout.addWidget(find_next_btn)

        find_prev_btn = QPushButton("Trước đó ⬆")
        find_prev_btn.setStyleSheet("padding: 5px 10px; font-size: 12px;")
        find_prev_btn.clicked.connect(self.search_prev)
        top_layout.addWidget(find_prev_btn)

        top_layout.addSpacing(15)

        self.auto_scroll_cb = QCheckBox("Tự động cuộn")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.setStyleSheet("font-weight: bold; color: #1E40AF;")
        top_layout.addWidget(self.auto_scroll_cb)

        layout.addLayout(top_layout)

        # Center TextEdit
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setPlainText(initial_text)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #111827;
                color: #F3F4F6;
                font-family: Consolas, "Courier New", monospace;
                font-size: 13px;
                line-height: 1.4;
                border: 1px solid #374151;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        # Scroll to bottom initially
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        layout.addWidget(self.log_text)

        # Bottom Bar: Status + Action buttons
        bottom_layout = QHBoxLayout()

        self.status_label = QLabel(self._get_stats_text())
        self.status_label.setStyleSheet("color: #6B7280; font-size: 12px;")
        bottom_layout.addWidget(self.status_label)

        bottom_layout.addStretch()

        copy_btn = QPushButton("📋 Sao chép toàn bộ")
        copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        copy_btn.clicked.connect(self.copy_all_logs)
        bottom_layout.addWidget(copy_btn)

        clear_btn = QPushButton("🗑 Xóa Log")
        clear_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #DC2626; }
        """)
        clear_btn.clicked.connect(self.clear_log)
        bottom_layout.addWidget(clear_btn)

        close_btn = QPushButton("Đóng")
        close_btn.setStyleSheet("padding: 6px 16px; font-size: 12px;")
        close_btn.clicked.connect(self.close)
        bottom_layout.addWidget(close_btn)

        layout.addLayout(bottom_layout)

    def _get_stats_text(self) -> str:
        lines = len(self.log_text.toPlainText().splitlines())
        chars = len(self.log_text.toPlainText())
        return f"Tổng cộng: {lines} dòng ({chars:,} ký tự)"

    def append_log(self, message: str):
        self.log_text.append(message)
        if self.auto_scroll_cb.isChecked():
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
        self.status_label.setText(self._get_stats_text())

    def clear_log(self):
        self.log_text.clear()
        self.status_label.setText(self._get_stats_text())
        self.clear_requested.emit()

    def copy_all_logs(self):
        text = self.log_text.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            self.status_label.setText("✅ Đã sao chép toàn bộ nhật ký vào clipboard!")
        else:
            self.status_label.setText("⚠️ Log đang trống.")

    def on_search_text_changed(self, text: str):
        if not text:
            cursor = self.log_text.textCursor()
            cursor.clearSelection()
            self.log_text.setTextCursor(cursor)

    def search_next(self):
        query = self.search_input.text()
        if not query:
            return
        found = self.log_text.find(query)
        if not found:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self.log_text.setTextCursor(cursor)
            found = self.log_text.find(query)
            if not found:
                self.status_label.setText(f"❌ Không tìm thấy: '{query}'")
            else:
                self.status_label.setText(f"🔍 Đã tìm thấy (vòng lại từ đầu): '{query}'")
        else:
            self.status_label.setText(f"🔍 Đang chọn kết quả cho: '{query}'")

    def search_prev(self):
        query = self.search_input.text()
        if not query:
            return
        found = self.log_text.find(query, QTextDocument.FindFlag.FindBackward)
        if not found:
            cursor = self.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_text.setTextCursor(cursor)
            found = self.log_text.find(query, QTextDocument.FindFlag.FindBackward)
            if not found:
                self.status_label.setText(f"❌ Không tìm thấy: '{query}'")
            else:
                self.status_label.setText(f"🔍 Đã tìm thấy (vòng lại từ cuối): '{query}'")
        else:
            self.status_label.setText(f"🔍 Đang chọn kết quả cho: '{query}'")


# ==============================================================================
# ==============================================================================
# Main Application Window: FacebookNotificationUI (4 Tabs)
# ==============================================================================
class FacebookNotificationUI(QMainWindow):
    """Main PyQt6 Window with 4 Tabs: Group Posts, Dữ liệu cào, Lịch sử phân tích, & Cấu hình"""
    
    def __init__(self):
        super().__init__()
        self.scraper_thread = None
        self.log_viewer_dialog = None
        self.cookie_string = ""
        self.cookie_raw_json = ""
        self.cookies = {}
        self.fb_dtsg = ""
        
        # Tab 2: Dữ liệu cào (Paging & Data & Selections)
        self.history_posts_data = []
        self.history_current_page = 1
        self.history_page_size = 50
        self.history_total_count = 0
        self.history_total_pages = 1
        self.selected_history_post_ids = set()

        # Tab 3: Lịch sử phân tích AI (Paging & Data & Selections)
        self.ai_analyses_data = []
        self.ai_current_page = 1
        self.ai_page_size = 50
        self.ai_total_count = 0
        self.ai_total_pages = 1
        self.selected_ai_analysis_ids = set()

        self.comment_update_worker = None

        # Background Telegram Dispatcher Thread (Quét DB gửi Telegram tự động)
        self.telegram_dispatcher = TelegramDispatcherThread(check_interval=5)
        self.telegram_dispatcher.log_signal.connect(self.log)
        self.telegram_dispatcher.notification_sent_signal.connect(self.on_telegram_notification_sent)
        self.telegram_dispatcher.start()

        # Background AI Dispatcher Thread (Quét DB phân tích AI tự động độc lập)
        self.ai_dispatcher = AIAnalysisWorker(check_interval=3)
        self.ai_dispatcher.log_signal.connect(self.log)
        self.ai_dispatcher.analysis_completed_signal.connect(self.on_ai_analysis_completed)
        self.ai_dispatcher.start()

        self.init_ui()
        self.load_saved_settings()
        self.refresh_group_autocomplete_options()

    def closeEvent(self, event):
        """Dừng các background worker khi đóng ứng dụng"""
        if hasattr(self, 'telegram_dispatcher') and self.telegram_dispatcher and self.telegram_dispatcher.isRunning():
            self.telegram_dispatcher.stop()
            self.telegram_dispatcher.wait(2000)
        if hasattr(self, 'ai_dispatcher') and self.ai_dispatcher and self.ai_dispatcher.isRunning():
            self.ai_dispatcher.stop()
            self.ai_dispatcher.wait(2000)
        super().closeEvent(event)

    def on_telegram_notification_sent(self, item: dict):
        """Xử lý phản hồi khi Telegram Dispatcher gửi thành công thông báo"""
        if hasattr(self, 'tabs') and self.tabs.currentIndex() == 2:
            self.load_ai_analysis_data()

    def on_ai_analysis_completed(self, item: dict):
        """Xử lý phản hồi khi AI Worker phân tích xong một bài viết"""
        if hasattr(self, 'tabs') and self.tabs.currentIndex() == 2:
            self.load_ai_analysis_data()
        if hasattr(self, 'telegram_dispatcher') and self.telegram_dispatcher:
            self.telegram_dispatcher.trigger_check_now()
    
    def init_ui(self):
        self.setWindowTitle(f"📘 Facebook Scraper & AI Notification System v{APP_VERSION}")
        self.setGeometry(100, 100, 1100, 820)
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout()
        central_widget.setLayout(main_layout)
        
        # Header Title
        title = QLabel(f"📘 Facebook Scraper & AI Notification System <span style='font-size: 13px; color: #2563EB; font-weight: bold;'>v{APP_VERSION}</span>")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("color: #1E3A8A; margin-bottom: 4px;")
        main_layout.addWidget(title)
        
        # 4 Tabs Widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("""
            QTabBar::tab {
                font-size: 13px;
                font-weight: bold;
                padding: 8px 18px;
            }
        """)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        main_layout.addWidget(self.tabs)
        
        # Create Tab 1 (Group Posts), Tab 2 (Dữ liệu cào), Tab 3 (Lịch sử phân tích), & Tab 4 (Cấu hình)
        self.group_posts_tab = self.create_group_posts_tab()
        self.history_tab = self.create_history_tab()
        self.ai_analysis_tab = self.create_ai_analysis_tab()
        self.config_tab = self.create_config_tab()
        
        self.tabs.addTab(self.group_posts_tab, "📁 Group Posts")
        self.tabs.addTab(self.history_tab, "📜 Dữ liệu cào")
        self.tabs.addTab(self.ai_analysis_tab, "🤖 Lịch sử phân tích")
        self.tabs.addTab(self.config_tab, "⚙️ Cấu hình")

    # --------------------------------------------------------------------------
    # Tab 1: Group Posts
    # --------------------------------------------------------------------------
    def create_group_posts_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)
        
        # Top Action Bar: Cookie & Guide buttons
        top_bar_layout = QHBoxLayout()

        self.cookie_btn = QPushButton("🔑 Cấu hình Authentication (Cookie & Token)")
        self.cookie_btn.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.cookie_btn.clicked.connect(self.configure_cookies)
        top_bar_layout.addWidget(self.cookie_btn, stretch=3)

        self.guide_btn = QPushButton("📖 Hướng Dẫn Sử Dụng (HTML)")
        self.guide_btn.setToolTip("Mở toàn bộ tài liệu hướng dẫn sử dụng chi tiết trong trình duyệt web")
        self.guide_btn.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 12px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        self.guide_btn.clicked.connect(self.open_user_guide)
        top_bar_layout.addWidget(self.guide_btn, stretch=2)

        layout.addLayout(top_bar_layout)
        
        # Input group
        input_group = QGroupBox("Cài đặt quét Nhóm Facebook")
        input_layout = QVBoxLayout()
        input_group.setLayout(input_layout)
        
        # Dynamic Group List Widget (persisted in SQLite facebook_groups)
        self.group_list_widget = GroupListWidget()
        self.group_list_widget.fetch_cookie_groups_requested.connect(lambda: self.fetch_groups_from_cookie())
        input_layout.addWidget(self.group_list_widget)
        
        # Keywords tag input widget
        input_layout.addWidget(QLabel("Từ khóa lọc (Keywords — dạng Tag):"))
        self.tag_widget = TagWidget()
        self.tag_widget.tags_changed.connect(self.save_keywords_to_db)
        input_layout.addWidget(self.tag_widget)
        
        # Controls row 1: Post count & Min comments
        spin_layout = QHBoxLayout()
        spin_layout.addWidget(QLabel("Số lượng bài viết/nhóm:"))
        self.group_post_count = QSpinBox()
        self.group_post_count.setMinimum(1)
        self.group_post_count.setMaximum(10000)
        self.group_post_count.setValue(5)
        self.group_post_count.setMinimumWidth(100)
        spin_layout.addWidget(self.group_post_count)
        
        spin_layout.addSpacing(20)
        spin_layout.addWidget(QLabel("Bình luận tối thiểu (0 = tất cả):"))
        self.group_min_comments = QSpinBox()
        self.group_min_comments.setMinimum(0)
        self.group_min_comments.setMaximum(10000)
        self.group_min_comments.setValue(0)
        self.group_min_comments.setMinimumWidth(100)
        spin_layout.addWidget(self.group_min_comments)
        spin_layout.addStretch()
        input_layout.addLayout(spin_layout)

        # Controls row 2: Infinite Loop & Interval
        loop_layout = QHBoxLayout()
        self.infinite_loop_cb = QCheckBox("Lặp vô hạn (Infinite Loop)")
        self.infinite_loop_cb.setStyleSheet("font-weight: bold; color: #1E3A8A;")
        self.infinite_loop_cb.toggled.connect(self.toggle_infinite_loop)
        loop_layout.addWidget(self.infinite_loop_cb)

        loop_layout.addSpacing(15)
        self.loop_interval_label = QLabel("Thời gian nghỉ giữa các lần quét (giây):")
        self.loop_interval_label.setEnabled(False)
        loop_layout.addWidget(self.loop_interval_label)

        self.loop_interval_spin = QSpinBox()
        self.loop_interval_spin.setMinimum(5)
        self.loop_interval_spin.setMaximum(86400)
        self.loop_interval_spin.setValue(60)
        self.loop_interval_spin.setMinimumWidth(100)
        self.loop_interval_spin.setEnabled(False)
        loop_layout.addWidget(self.loop_interval_spin)
        loop_layout.addStretch()
        input_layout.addLayout(loop_layout)
        
        layout.addWidget(input_group)
        
        # Action Buttons Row: Start and STOP
        action_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 Bắt đầu quét")
        self.start_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.start_btn.clicked.connect(self.start_scraping)
        action_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("🛑 DỪNG")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.stop_btn.clicked.connect(self.stop_scraping)
        action_layout.addWidget(self.stop_btn)

        layout.addLayout(action_layout)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("QProgressBar { height: 18px; border-radius: 4px; text-align: center; }")
        layout.addWidget(self.progress_bar)

        # Activity Logs inside Group Tab
        log_group = QGroupBox("📋 Nhật ký hoạt động (Logs)")
        log_layout = QVBoxLayout()
        log_layout.setContentsMargins(8, 8, 8, 8)
        log_layout.setSpacing(4)
        log_group.setLayout(log_layout)
        
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMinimumHeight(65)
        self.log_text.setStyleSheet("background-color: #111827; color: #F3F4F6; font-family: Consolas, monospace; font-size: 11px; border-radius: 4px;")
        log_layout.addWidget(self.log_text)
        
        log_btn_layout = QHBoxLayout()
        log_hint = QLabel("<i>⚡ Nhật ký thu gọn. Bấm 'Phóng to' để xem toàn bộ và tìm kiếm.</i>")
        log_hint.setStyleSheet("color: #6B7280; font-size: 11px;")
        log_btn_layout.addWidget(log_hint)
        log_btn_layout.addStretch()

        self.expand_log_btn = QPushButton("⛶ Phóng to")
        self.expand_log_btn.setToolTip("Mở cửa sổ xem log chi tiết toàn màn hình")
        self.expand_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #4338CA;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                border: 1px solid #C7D2FE;
            }
            QPushButton:hover { background-color: #E0E7FF; }
        """)
        self.expand_log_btn.clicked.connect(self.open_log_viewer_dialog)
        log_btn_layout.addWidget(self.expand_log_btn)

        clear_log_btn = QPushButton("🗑 Xóa Log")
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #991B1B;
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 11px;
                border: 1px solid #FECACA;
            }
            QPushButton:hover { background-color: #FCA5A5; }
        """)
        clear_log_btn.clicked.connect(self.clear_log)
        log_btn_layout.addWidget(clear_log_btn)
        log_layout.addLayout(log_btn_layout)

        layout.addWidget(log_group, 1)
        return tab

    # --------------------------------------------------------------------------
    # Tab 2: Dữ liệu cào (Scraped Posts History & GridView)
    # --------------------------------------------------------------------------
    def create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # Top Control Bar (Search + Refresh)
        top_bar = QHBoxLayout()
        
        self.history_search_input = QLineEdit()
        self.history_search_input.setPlaceholderText("🔍 Tìm kiếm chung (nội dung, tên nhóm/trang, post ID)...")
        self.history_search_input.setStyleSheet("padding: 8px; font-size: 13px; border-radius: 4px; border: 1px solid #D1D5DB;")
        self.history_search_input.returnPressed.connect(self.on_filter_changed)
        top_bar.addWidget(self.history_search_input, stretch=3)

        search_btn = QPushButton("🔍 Tìm")
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        search_btn.clicked.connect(self.on_filter_changed)
        top_bar.addWidget(search_btn)

        refresh_btn = QPushButton("🔄 Làm mới")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        refresh_btn.clicked.connect(self.clear_all_filters)
        top_bar.addWidget(refresh_btn)

        layout.addLayout(top_bar)

        # Column Filter Bar
        filter_group = QGroupBox("🎯 Bộ lọc Dữ liệu cào theo từng cột")
        filter_layout = QHBoxLayout()
        filter_group.setLayout(filter_layout)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        filter_layout.setSpacing(8)

        # 1. Post ID filter
        filter_layout.addWidget(QLabel("Post ID:"))
        self.filter_post_id = QLineEdit()
        self.filter_post_id.setPlaceholderText("ID bài viết...")
        self.filter_post_id.setStyleSheet("padding: 4px; font-size: 12px;")
        self.filter_post_id.textChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_post_id, stretch=1)

        # 2. Group/Page Autocomplete Dropdown (Select2-like)
        filter_layout.addWidget(QLabel("Nhóm/Trang:"))
        self.filter_group_combo = QComboBox()
        self.filter_group_combo.setEditable(True)
        self.filter_group_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.filter_group_combo.setStyleSheet("padding: 4px; font-size: 12px;")
        if self.filter_group_combo.completer():
            self.filter_group_combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.filter_group_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        if self.filter_group_combo.lineEdit():
            self.filter_group_combo.lineEdit().setPlaceholderText("Tất cả hoặc gõ tìm nhóm...")
        self.filter_group_combo.currentTextChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_group_combo, stretch=2)

        # 3. Message text filter
        filter_layout.addWidget(QLabel("Nội dung:"))
        self.filter_message = QLineEdit()
        self.filter_message.setPlaceholderText("Nội dung bài viết...")
        self.filter_message.setStyleSheet("padding: 4px; font-size: 12px;")
        self.filter_message.textChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_message, stretch=2)

        # 4. Min comments filter
        filter_layout.addWidget(QLabel("Min Cmt:"))
        self.filter_min_comments = QSpinBox()
        self.filter_min_comments.setMinimum(0)
        self.filter_min_comments.setMaximum(10000)
        self.filter_min_comments.setValue(0)
        self.filter_min_comments.valueChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_min_comments)

        # 5. Time filter
        filter_layout.addWidget(QLabel("Thời gian:"))
        self.filter_time = QLineEdit()
        self.filter_time.setPlaceholderText("dd/mm/yyyy...")
        self.filter_time.setStyleSheet("padding: 4px; font-size: 12px;")
        self.filter_time.textChanged.connect(self.on_filter_changed)
        filter_layout.addWidget(self.filter_time, stretch=1)

        # Clear filter button
        clear_filter_btn = QPushButton("🧹 Xóa lọc")
        clear_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4B5563; }
        """)
        clear_filter_btn.clicked.connect(self.clear_all_filters)
        filter_layout.addWidget(clear_filter_btn)

        layout.addWidget(filter_group)

        # Instruction note
        hint_label = QLabel("💡 <i>Gợi ý: Bấm đúp chuột hoặc click vào dòng để xem chi tiết bài viết, bình luận & phản hồi. Bấm nút <b>'🔗 Mở FB'</b> để mở bài viết trên trình duyệt.</i>")
        hint_label.setStyleSheet("color: #4B5563; font-size: 12px; margin-bottom: 2px;")
        layout.addWidget(hint_label)

        # Batch Action Toolbar
        action_toolbar = QHBoxLayout()
        action_toolbar.setContentsMargins(0, 4, 0, 4)
        action_toolbar.setSpacing(10)

        self.history_select_all_cb = QCheckBox("Chọn tất cả trang này")
        self.history_select_all_cb.setStyleSheet("font-weight: bold; font-size: 12px; color: #1E3A8A;")
        self.history_select_all_cb.toggled.connect(self.on_history_select_all_toggled)
        action_toolbar.addWidget(self.history_select_all_cb)

        action_toolbar.addSpacing(5)

        self.btn_delete_selected_history = QPushButton("🗑️ Xóa đã chọn (0)")
        self.btn_delete_selected_history.setEnabled(False)
        self.btn_delete_selected_history.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #991B1B;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
                border: 1px solid #FECACA;
            }
            QPushButton:hover:enabled { background-color: #FCA5A5; }
            QPushButton:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
                border: 1px solid #E5E7EB;
            }
        """)
        self.btn_delete_selected_history.clicked.connect(self.delete_selected_history_posts)
        action_toolbar.addWidget(self.btn_delete_selected_history)

        self.btn_delete_all_history = QPushButton("💥 Xóa tất cả")
        self.btn_delete_all_history.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #B91C1C; }
        """)
        self.btn_delete_all_history.clicked.connect(self.delete_all_history_posts)
        action_toolbar.addWidget(self.btn_delete_all_history)

        action_toolbar.addSpacing(15)

        self.btn_update_selected_comments = QPushButton("🔄 Cập nhật bình luận đã chọn (0)")
        self.btn_update_selected_comments.setEnabled(False)
        self.btn_update_selected_comments.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover:enabled { background-color: #1D4ED8; }
            QPushButton:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
                border: 1px solid #E5E7EB;
            }
        """)
        self.btn_update_selected_comments.clicked.connect(self.update_selected_comments)
        action_toolbar.addWidget(self.btn_update_selected_comments)

        self.btn_update_24h_comments = QPushButton("⏱️ Cập nhật bình luận 24h vừa qua")
        self.btn_update_24h_comments.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.btn_update_24h_comments.clicked.connect(self.update_24h_comments)
        action_toolbar.addWidget(self.btn_update_24h_comments)

        action_toolbar.addStretch()
        layout.addLayout(action_toolbar)

        # Table Widget (Gridview)
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(8)
        self.history_table.setHorizontalHeaderLabels([
            "☑️", "STT", "Post ID", "Nhóm / Trang", "Nội dung bài viết", "Bình luận", "Thời gian", "Hành động"
        ])
        
        header = self.history_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.history_table.setColumnWidth(0, 42)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        self.history_table.setColumnWidth(7, 160)

        self.history_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.history_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.history_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #F9FAFB;
                gridline-color: #E5E7EB;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #F3F4F6;
                color: #1F2937;
                font-weight: bold;
                font-size: 12px;
                padding: 6px;
                border: 1px solid #E5E7EB;
            }
            QTableWidget::item:selected {
                background-color: #DBEAFE;
                color: #1E3A8A;
            }
        """)
        self.history_table.cellDoubleClicked.connect(self.on_history_row_double_clicked)
        self.history_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.history_table.customContextMenuRequested.connect(self.show_history_context_menu)

        layout.addWidget(self.history_table)

        # Bottom Paging Bar
        paging_bar = QHBoxLayout()
        paging_bar.setContentsMargins(4, 4, 4, 4)

        self.first_page_btn = QPushButton("⏮ Đầu")
        self.first_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.first_page_btn.clicked.connect(self.go_first_page)
        paging_bar.addWidget(self.first_page_btn)

        self.prev_page_btn = QPushButton("◀ Trước")
        self.prev_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.prev_page_btn.clicked.connect(self.go_prev_page)
        paging_bar.addWidget(self.prev_page_btn)

        paging_bar.addWidget(QLabel("Trang"))

        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setValue(1)
        self.page_spin.setFixedWidth(60)
        self.page_spin.valueChanged.connect(self.on_page_spin_changed)
        paging_bar.addWidget(self.page_spin)

        self.total_pages_label = QLabel("/ 1")
        self.total_pages_label.setStyleSheet("font-weight: bold; margin-right: 8px;")
        paging_bar.addWidget(self.total_pages_label)

        self.next_page_btn = QPushButton("Sau ▶")
        self.next_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.next_page_btn.clicked.connect(self.go_next_page)
        paging_bar.addWidget(self.next_page_btn)

        self.last_page_btn = QPushButton("Cuối ⏭")
        self.last_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.last_page_btn.clicked.connect(self.go_last_page)
        paging_bar.addWidget(self.last_page_btn)

        paging_bar.addSpacing(20)
        paging_bar.addWidget(QLabel("Hiển thị/trang:"))

        self.page_size_combo = QComboBox()
        self.page_size_combo.addItems(["20", "50", "100", "200"])
        self.page_size_combo.setCurrentText("50")
        self.page_size_combo.currentTextChanged.connect(self.on_page_size_changed)
        paging_bar.addWidget(self.page_size_combo)

        paging_bar.addStretch()

        self.history_total_label = QLabel("📊 Tổng số: 0 bài viết")
        self.history_total_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #1E3A8A;")
        paging_bar.addWidget(self.history_total_label)

        layout.addLayout(paging_bar)
        return tab

    def on_history_checkbox_toggled(self, post_id: str, is_checked: bool):
        """Xử lý khi người dùng tích/bỏ tích checkbox từng bài viết"""
        if is_checked:
            self.selected_history_post_ids.add(str(post_id))
        else:
            self.selected_history_post_ids.discard(str(post_id))
        self.update_history_buttons_state()

    def on_history_select_all_toggled(self, is_checked: bool):
        """Xử lý khi tích chọn tất cả bài viết trên trang hiện tại"""
        for row in range(self.history_table.rowCount()):
            cell = self.history_table.cellWidget(row, 0)
            if cell:
                cb = cell.findChild(QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(is_checked)
                    cb.blockSignals(False)
            stt_item = self.history_table.item(row, 1)
            if stt_item:
                pid = stt_item.data(Qt.ItemDataRole.UserRole)
                if pid:
                    if is_checked:
                        self.selected_history_post_ids.add(str(pid))
                    else:
                        self.selected_history_post_ids.discard(str(pid))
        self.update_history_buttons_state()

    def update_history_buttons_state(self):
        """Cập nhật số lượng và trạng thái sáng/tối của các nút tác vụ Tab Dữ liệu cào"""
        count = len(self.selected_history_post_ids)
        is_running = (self.scraper_thread and self.scraper_thread.isRunning()) or (hasattr(self, 'comment_update_worker') and self.comment_update_worker and self.comment_update_worker.isRunning())
        if hasattr(self, 'btn_delete_selected_history'):
            self.btn_delete_selected_history.setText(f"🗑️ Xóa đã chọn ({count})")
            self.btn_delete_selected_history.setEnabled(count > 0 and not is_running)
        if hasattr(self, 'btn_update_selected_comments'):
            self.btn_update_selected_comments.setText(f"🔄 Cập nhật bình luận đã chọn ({count})")
            self.btn_update_selected_comments.setEnabled(count > 0 and not is_running)

    def delete_single_post(self, post_id: str):
        """Xác nhận và xóa lẻ một bài viết khỏi database"""
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa bài viết",
            f"Bạn có chắc chắn muốn xóa bài viết ID: {post_id} và toàn bộ bình luận/phân tích liên quan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok = database.delete_post_by_id(str(post_id))
            if ok:
                self.log(f"🗑 Đã xóa bài viết ID: {post_id}.")
                self.selected_history_post_ids.discard(str(post_id))
                self.update_history_buttons_state()
                self.load_history_data()
                self.load_ai_analysis_data()
            else:
                QMessageBox.warning(self, "Lỗi", f"Không thể xóa bài viết ID: {post_id}")

    def delete_selected_history_posts(self):
        """Xác nhận và xóa những bài viết đã chọn khỏi database"""
        if not self.selected_history_post_ids:
            return
        count = len(self.selected_history_post_ids)
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa các bài viết đã chọn",
            f"Bạn có chắc chắn muốn xóa {count} bài viết đã chọn và toàn bộ dữ liệu liên quan?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = database.delete_posts_by_ids(list(self.selected_history_post_ids))
            self.log(f"🗑 Đã xóa {deleted_count} bài viết đã chọn.")
            self.selected_history_post_ids.clear()
            if hasattr(self, 'history_select_all_cb'):
                self.history_select_all_cb.blockSignals(True)
                self.history_select_all_cb.setChecked(False)
                self.history_select_all_cb.blockSignals(False)
            self.update_history_buttons_state()
            self.load_history_data()
            self.load_ai_analysis_data()

    def delete_all_history_posts(self):
        """Xác nhận và xóa trắng toàn bộ dữ liệu bài viết đã cào"""
        reply = QMessageBox.question(
            self,
            "Xác nhận XÓA TẤT CẢ dữ liệu cào",
            "⚠️ CẢNH BÁO: Hành động này sẽ XÓA TRẮNG toàn bộ bài viết, bình luận, reply, media và lịch sử phân tích trong cơ sở dữ liệu!\n\nBạn có chắc chắn muốn tiếp tục?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = database.delete_all_posts()
            self.log(f"💥 Đã xóa trắng toàn bộ dữ liệu cào ({deleted_count} bài viết).")
            self.selected_history_post_ids.clear()
            if hasattr(self, 'history_select_all_cb'):
                self.history_select_all_cb.blockSignals(True)
                self.history_select_all_cb.setChecked(False)
                self.history_select_all_cb.blockSignals(False)
            self.update_history_buttons_state()
            self.load_history_data()
            self.load_ai_analysis_data()

    def update_selected_comments(self):
        """Cập nhật bình luận của các bài viết đã được tích chọn"""
        if not self.selected_history_post_ids:
            return
        post_ids = list(self.selected_history_post_ids)
        self.start_comment_update_worker(post_ids)

    def update_24h_comments(self):
        """Cập nhật bình luận của tất cả các bài viết đăng trong vòng 24h qua"""
        posts_24h = database.get_posts_within_last_24h()
        if not posts_24h:
            QMessageBox.information(self, "Thông báo", "Không tìm thấy bài viết nào trong dữ liệu được đăng trong vòng 24 giờ qua.")
            return

        reply = QMessageBox.question(
            self,
            "Cập nhật bình luận 24h vừa qua",
            f"Tìm thấy {len(posts_24h)} bài viết đăng trong vòng 24 giờ qua.\n\nBạn có muốn bắt đầu cập nhật bình luận cho các bài viết này?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )
        if reply == QMessageBox.StandardButton.Yes:
            post_ids = [str(p["post_id"]) for p in posts_24h]
            self.start_comment_update_worker(post_ids)

    def start_comment_update_worker(self, post_ids: list[str]):
        """Khởi chạy luồng nền cập nhật bình luận và chuyển sang AI Worker"""
        if (self.scraper_thread and self.scraper_thread.isRunning()) or (hasattr(self, 'comment_update_worker') and self.comment_update_worker and self.comment_update_worker.isRunning()):
            QMessageBox.warning(self, "Đang xử lý", "Hiện đang có tiến trình cào/cập nhật khác đang chạy. Vui lòng đợi hoặc dừng tiến trình trước.")
            return

        tg_config = {
            "enabled": self.tg_enabled_cb.isChecked() if hasattr(self, 'tg_enabled_cb') else False,
            "token": self.tg_token_input.text().strip() if hasattr(self, 'tg_token_input') else "",
            "chat_id": self.tg_chat_id_input.text().strip() if hasattr(self, 'tg_chat_id_input') else "",
            "notify_on_finish": self.tg_notify_finish_cb.isChecked() if hasattr(self, 'tg_notify_finish_cb') else False,
            "notify_on_keyword": self.tg_notify_keyword_cb.isChecked() if hasattr(self, 'tg_notify_keyword_cb') else False
        }

        provider = self.get_current_ai_provider()
        models = self.get_active_ai_models()
        default_model = "gemini-2.0-flash" if provider == "google_ai" else "gpt-4o-mini"
        ai_config = {
            "enabled": self.ai_enabled_cb.isChecked() if hasattr(self, 'ai_enabled_cb') else False,
            "provider": provider,
            "base_url": self.get_resolved_ai_base_url(),
            "api_key": self.ai_api_key_input.text().strip() if hasattr(self, 'ai_api_key_input') else "",
            "models": models if models else [default_model],
            "prompt": self.ai_prompt_input.toPlainText().strip() if hasattr(self, 'ai_prompt_input') else ""
        }

        keywords = self.tag_widget.get_tags() if hasattr(self, 'tag_widget') else []

        self.set_scraping_state(running=True)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)

        from src.ui.workers.comment_update_worker import CommentUpdateWorker
        self.comment_update_worker = CommentUpdateWorker(
            post_ids=post_ids,
            cookies=self.cookies,
            fb_dtsg=self.fb_dtsg,
            telegram_config=tg_config,
            ai_config=ai_config,
            keywords=keywords
        )
        self.comment_update_worker.log_signal.connect(self.log)
        self.comment_update_worker.progress_signal.connect(self.update_progress)
        self.comment_update_worker.post_status_signal.connect(self.on_post_comment_updating_status)
        self.comment_update_worker.finished_signal.connect(self.comment_update_finished)
        self.comment_update_worker.start()

    def on_post_comment_updating_status(self, post_id: str, status: str, comment_count: int):
        """Hiển thị icon xoay và trạng thái đang cập nhật cho bài viết cụ thể trên bảng Dữ liệu cào"""
        if not hasattr(self, 'history_table'):
            return

        for row in range(self.history_table.rowCount()):
            stt_item = self.history_table.item(row, 1)
            id_item = self.history_table.item(row, 2)
            pid = id_item.text().strip() if id_item else ""
            if not pid and stt_item:
                pid = str(stt_item.data(Qt.ItemDataRole.UserRole) or "")

            if pid == str(post_id):
                cmt_item = self.history_table.item(row, 5)
                if status in ("updating", "updating_comments"):
                    if stt_item:
                        orig = stt_item.data(Qt.ItemDataRole.UserRole + 1)
                        if orig is None:
                            stt_item.setData(Qt.ItemDataRole.UserRole + 1, stt_item.text())
                        stt_item.setText("🔄 " + str(stt_item.data(Qt.ItemDataRole.UserRole + 1)))
                    if cmt_item:
                        cmt_item.setText("🔄 Đang tải...")
                        cmt_item.setForeground(QColor("#2563EB"))
                    for col in range(self.history_table.columnCount()):
                        it = self.history_table.item(row, col)
                        if it:
                            it.setBackground(QColor("#E0F2FE"))
                elif status == "analyzing_ai":
                    if stt_item:
                        orig = stt_item.data(Qt.ItemDataRole.UserRole + 1)
                        if orig is None:
                            stt_item.setData(Qt.ItemDataRole.UserRole + 1, stt_item.text())
                        stt_item.setText("🤖 " + str(stt_item.data(Qt.ItemDataRole.UserRole + 1)))
                    if cmt_item:
                        cmt_item.setText("🤖 Đang phân tích AI...")
                        cmt_item.setForeground(QColor("#7C3AED"))
                    for col in range(self.history_table.columnCount()):
                        it = self.history_table.item(row, col)
                        if it:
                            it.setBackground(QColor("#EDE9FE"))
                elif status == "done":
                    if stt_item:
                        orig = stt_item.data(Qt.ItemDataRole.UserRole + 1)
                        stt_item.setText(str(orig) if orig else stt_item.text().replace("🔄 ", "").replace("🤖 ", ""))
                    if cmt_item:
                        cmt_item.setText(str(comment_count))
                        cmt_item.setForeground(QColor("#15803D"))
                    bg_color = QColor("#FFFFFF") if row % 2 == 0 else QColor("#F9FAFB")
                    for col in range(self.history_table.columnCount()):
                        it = self.history_table.item(row, col)
                        if it:
                            it.setBackground(bg_color)
                elif status == "error":
                    if stt_item:
                        orig = stt_item.data(Qt.ItemDataRole.UserRole + 1)
                        stt_item.setText(str(orig) if orig else stt_item.text().replace("🔄 ", "").replace("🤖 ", ""))
                    if cmt_item:
                        cmt_item.setText("❌ Lỗi")
                        cmt_item.setForeground(QColor("#DC2626"))
                    for col in range(self.history_table.columnCount()):
                        it = self.history_table.item(row, col)
                        if it:
                            it.setBackground(QColor("#FEE2E2"))

                self.history_table.viewport().update()
                break

    def comment_update_finished(self, success, message):
        """Xử lý khi luồng cập nhật bình luận hoàn tất"""
        self.set_scraping_state(running=False)
        if hasattr(self, 'progress_bar'):
            self.progress_bar.setVisible(False)

        if success:
            self.log(f"✅ {message}")
            QMessageBox.information(self, "Thông báo", message)
        else:
            self.log(f"❌ {message}")
            QMessageBox.critical(self, "Lỗi", message)

        self.load_history_data()
        self.load_ai_analysis_data()

    def on_filter_changed(self):
        self.history_current_page = 1
        self.load_history_data()

    def clear_all_filters(self):
        if hasattr(self, 'history_search_input'):
            self.history_search_input.blockSignals(True)
            self.history_search_input.clear()
            self.history_search_input.blockSignals(False)

        if hasattr(self, 'filter_post_id'):
            self.filter_post_id.blockSignals(True)
            self.filter_post_id.clear()
            self.filter_post_id.blockSignals(False)

        if hasattr(self, 'filter_group_combo'):
            self.filter_group_combo.blockSignals(True)
            self.filter_group_combo.setEditText("")
            self.filter_group_combo.blockSignals(False)

        if hasattr(self, 'filter_message'):
            self.filter_message.blockSignals(True)
            self.filter_message.clear()
            self.filter_message.blockSignals(False)

        if hasattr(self, 'filter_min_comments'):
            self.filter_min_comments.blockSignals(True)
            self.filter_min_comments.setValue(0)
            self.filter_min_comments.blockSignals(False)

        if hasattr(self, 'filter_time'):
            self.filter_time.blockSignals(True)
            self.filter_time.clear()
            self.filter_time.blockSignals(False)

        self.history_current_page = 1
        self.load_history_data()

    def go_first_page(self):
        if self.history_current_page != 1:
            self.history_current_page = 1
            self.load_history_data()

    def go_prev_page(self):
        if self.history_current_page > 1:
            self.history_current_page -= 1
            self.load_history_data()

    def go_next_page(self):
        if self.history_current_page < self.history_total_pages:
            self.history_current_page += 1
            self.load_history_data()

    def go_last_page(self):
        if self.history_current_page != self.history_total_pages:
            self.history_current_page = self.history_total_pages
            self.load_history_data()

    def on_page_spin_changed(self, val):
        if val != self.history_current_page:
            self.history_current_page = val
            self.load_history_data()

    def on_page_size_changed(self, text):
        try:
            self.history_page_size = int(text)
            self.history_current_page = 1
            self.load_history_data()
        except Exception:
            pass

    def load_history_data(self):
        search_query = self.history_search_input.text().strip() if hasattr(self, 'history_search_input') else ""
        filters = {}
        if hasattr(self, 'filter_post_id') and self.filter_post_id.text().strip():
            filters["post_id"] = self.filter_post_id.text().strip()
        if hasattr(self, 'filter_group_combo') and self.filter_group_combo.currentText().strip():
            filters["group_name"] = self.filter_group_combo.currentText().strip()
        if hasattr(self, 'filter_message') and self.filter_message.text().strip():
            filters["message"] = self.filter_message.text().strip()
        if hasattr(self, 'filter_min_comments') and self.filter_min_comments.value() > 0:
            filters["min_comments"] = self.filter_min_comments.value()
        if hasattr(self, 'filter_time') and self.filter_time.text().strip():
            filters["time_str"] = self.filter_time.text().strip()

        total = database.get_posts_count(search_query=search_query, filters=filters)
        self.history_total_count = total
        self.history_total_pages = max(1, math.ceil(total / self.history_page_size))

        if self.history_current_page > self.history_total_pages:
            self.history_current_page = self.history_total_pages
        if self.history_current_page < 1:
            self.history_current_page = 1

        if hasattr(self, 'page_spin'):
            self.page_spin.blockSignals(True)
            self.page_spin.setMaximum(self.history_total_pages)
            self.page_spin.setValue(self.history_current_page)
            self.page_spin.blockSignals(False)

        if hasattr(self, 'total_pages_label'):
            self.total_pages_label.setText(f"/ {self.history_total_pages}")

        if hasattr(self, 'first_page_btn'):
            self.first_page_btn.setEnabled(self.history_current_page > 1)
            self.prev_page_btn.setEnabled(self.history_current_page > 1)
            self.next_page_btn.setEnabled(self.history_current_page < self.history_total_pages)
            self.last_page_btn.setEnabled(self.history_current_page < self.history_total_pages)

        if hasattr(self, 'history_total_label'):
            self.history_total_label.setText(f"📊 Tổng số: {total} bài viết | Trang {self.history_current_page}/{self.history_total_pages}")

        offset = (self.history_current_page - 1) * self.history_page_size
        posts = database.get_all_posts_summary(limit=self.history_page_size, offset=offset, search_query=search_query, filters=filters)
        self.history_posts_data = posts
        
        self.history_table.setRowCount(0)

        all_page_selected = bool(posts)

        for row_idx, post in enumerate(posts):
            self.history_table.insertRow(row_idx)
            self.history_table.setRowHeight(row_idx, 38)

            post_id = str(post.get("post_id", ""))
            group_name = post.get("group_name") or post.get("page_name") or "N/A"
            message = post.get("message") or ""
            clean_message = message.replace('\n', ' ').strip()
            if len(clean_message) > 120:
                clean_message = clean_message[:120] + "..."
            if not clean_message:
                clean_message = "(Không có text)"

            comment_count = post.get("actual_comments_count", 0) or post.get("comment_count", 0)
            
            creation_time = post.get("creation_time")
            created_at_str = post.get("created_at", "")
            time_display = ""
            if creation_time:
                try:
                    dt = datetime.fromtimestamp(int(creation_time))
                    time_display = dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    time_display = str(creation_time)
            elif created_at_str:
                time_display = str(created_at_str)[:16]

            permalink = post.get("permalink") or f"https://www.facebook.com/{post_id}"

            is_checked = post_id in self.selected_history_post_ids
            if not is_checked:
                all_page_selected = False

            # Col 0: Checkbox
            cb_container = QWidget()
            cb_layout = QHBoxLayout(cb_container)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(is_checked)
            cb.toggled.connect(lambda checked, pid=post_id: self.on_history_checkbox_toggled(pid, checked))
            cb_layout.addWidget(cb)
            self.history_table.setCellWidget(row_idx, 0, cb_container)

            # Col 1: STT
            item_stt = QTableWidgetItem(str(offset + row_idx + 1))
            item_stt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_stt.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 2: Post ID
            item_id = QTableWidgetItem(post_id)
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_id.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 3: Group Name
            item_group = QTableWidgetItem(group_name)
            item_group.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 4: Message
            item_msg = QTableWidgetItem(clean_message)
            item_msg.setToolTip(message)
            item_msg.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 5: Comment Count
            item_cmt = QTableWidgetItem(str(comment_count))
            item_cmt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_cmt.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 6: Time
            item_time = QTableWidgetItem(time_display)
            item_time.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_time.setData(Qt.ItemDataRole.UserRole, post_id)

            self.history_table.setItem(row_idx, 1, item_stt)
            self.history_table.setItem(row_idx, 2, item_id)
            self.history_table.setItem(row_idx, 3, item_group)
            self.history_table.setItem(row_idx, 4, item_msg)
            self.history_table.setItem(row_idx, 5, item_cmt)
            self.history_table.setItem(row_idx, 6, item_time)

            # Col 7: Actions ("🔗 Mở FB" & "🗑 Xóa")
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(4)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            open_btn = QPushButton("🔗 Mở FB")
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 6px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #1D4ED8; }
            """)
            open_btn.clicked.connect(lambda checked, url=permalink: webbrowser.open(url))
            btn_layout.addWidget(open_btn)

            del_btn = QPushButton("🗑 Xóa")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FEE2E2;
                    color: #991B1B;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 6px;
                    border-radius: 4px;
                    border: 1px solid #FECACA;
                }
                QPushButton:hover { background-color: #FCA5A5; }
            """)
            del_btn.clicked.connect(lambda checked, pid=post_id: self.delete_single_post(pid))
            btn_layout.addWidget(del_btn)

            self.history_table.setCellWidget(row_idx, 7, btn_container)

        if hasattr(self, 'history_select_all_cb'):
            self.history_select_all_cb.blockSignals(True)
            self.history_select_all_cb.setChecked(all_page_selected and bool(posts))
            self.history_select_all_cb.blockSignals(False)

        self.update_history_buttons_state()

    def on_history_row_double_clicked(self, row, column):
        if column in (0, 7):
            return
        item = self.history_table.item(row, 1)
        if not item:
            return
        post_id = item.data(Qt.ItemDataRole.UserRole)
        if post_id:
            self.show_post_detail(post_id)

    def show_history_context_menu(self, pos):
        item = self.history_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        stt_item = self.history_table.item(row, 1)
        if not stt_item:
            return
        post_id = stt_item.data(Qt.ItemDataRole.UserRole)
        if not post_id:
            return

        menu = QMenu(self)
        view_action = menu.addAction("🔍 Xem chi tiết bài viết & bình luận")
        open_action = menu.addAction("🔗 Mở trên Facebook (Trình duyệt)")
        copy_id_action = menu.addAction("📋 Sao chép Post ID")
        copy_text_action = menu.addAction("📋 Sao chép nội dung bài viết")
        menu.addSeparator()
        del_action = menu.addAction("🗑 Xóa bài viết này")

        action = menu.exec(self.history_table.viewport().mapToGlobal(pos))
        if action == view_action:
            self.show_post_detail(post_id)
        elif action == open_action:
            post_data = database.get_post_by_id(str(post_id)) or {}
            permalink = post_data.get("permalink") or f"https://www.facebook.com/{post_id}"
            webbrowser.open(permalink)
        elif action == copy_id_action:
            QApplication.clipboard().setText(str(post_id))
        elif action == copy_text_action:
            post_data = database.get_post_by_id(str(post_id)) or {}
            msg = post_data.get("message") or ""
            QApplication.clipboard().setText(msg)
        elif action == del_action:
            self.delete_single_post(post_id)

    # --------------------------------------------------------------------------
    # Tab 3: Lịch sử phân tích AI (AI Analysis History)
    # --------------------------------------------------------------------------
    def create_ai_analysis_tab(self):
        tab = QWidget()
        layout = QVBoxLayout()
        tab.setLayout(layout)

        # Top Control Bar (Search + Refresh)
        top_bar = QHBoxLayout()
        
        self.ai_search_input = QLineEdit()
        self.ai_search_input.setPlaceholderText("🔍 Tìm kiếm phân tích AI (nội dung, tên nhóm, post ID, thiết bị, từ khóa)...")
        self.ai_search_input.setStyleSheet("padding: 8px; font-size: 13px; border-radius: 4px; border: 1px solid #D1D5DB;")
        self.ai_search_input.returnPressed.connect(self.on_ai_filter_changed)
        top_bar.addWidget(self.ai_search_input, stretch=3)

        search_btn = QPushButton("🔍 Tìm")
        search_btn.setStyleSheet("""
            QPushButton {
                background-color: #8B5CF6;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #7C3AED; }
        """)
        search_btn.clicked.connect(self.on_ai_filter_changed)
        top_bar.addWidget(search_btn)

        refresh_btn = QPushButton("🔄 Làm mới")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        refresh_btn.clicked.connect(self.clear_all_ai_filters)
        top_bar.addWidget(refresh_btn)

        layout.addLayout(top_bar)

        # Column Filter Bar
        filter_group = QGroupBox("🎯 Bộ lọc Lịch sử Phân tích AI")
        filter_layout = QHBoxLayout()
        filter_group.setLayout(filter_layout)
        filter_layout.setContentsMargins(8, 6, 8, 6)
        filter_layout.setSpacing(8)

        # 1. Post ID filter
        filter_layout.addWidget(QLabel("Post ID:"))
        self.ai_filter_post_id = QLineEdit()
        self.ai_filter_post_id.setPlaceholderText("ID bài...")
        self.ai_filter_post_id.setStyleSheet("padding: 4px; font-size: 12px;")
        self.ai_filter_post_id.textChanged.connect(self.on_ai_filter_changed)
        filter_layout.addWidget(self.ai_filter_post_id, stretch=1)

        # 2. Group/Page Autocomplete Dropdown
        filter_layout.addWidget(QLabel("Nhóm/Trang:"))
        self.ai_filter_group_combo = QComboBox()
        self.ai_filter_group_combo.setEditable(True)
        self.ai_filter_group_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.ai_filter_group_combo.setStyleSheet("padding: 4px; font-size: 12px;")
        if self.ai_filter_group_combo.completer():
            self.ai_filter_group_combo.completer().setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            self.ai_filter_group_combo.completer().setFilterMode(Qt.MatchFlag.MatchContains)
        if self.ai_filter_group_combo.lineEdit():
            self.ai_filter_group_combo.lineEdit().setPlaceholderText("Tất cả hoặc gõ tìm nhóm...")
        self.ai_filter_group_combo.currentTextChanged.connect(self.on_ai_filter_changed)
        filter_layout.addWidget(self.ai_filter_group_combo, stretch=2)

        # 3. Keyword filter
        filter_layout.addWidget(QLabel("Từ khóa:"))
        self.ai_filter_keyword = QLineEdit()
        self.ai_filter_keyword.setPlaceholderText("Từ khóa khớp...")
        self.ai_filter_keyword.setStyleSheet("padding: 4px; font-size: 12px;")
        self.ai_filter_keyword.textChanged.connect(self.on_ai_filter_changed)
        filter_layout.addWidget(self.ai_filter_keyword, stretch=1)

        # 4. Target / Topic filter
        filter_layout.addWidget(QLabel("Mục tiêu:"))
        self.ai_filter_device = QLineEdit()
        self.ai_filter_device.setPlaceholderText("Tên sp / phòng / việc...")
        self.ai_filter_device.setStyleSheet("padding: 4px; font-size: 12px;")
        self.ai_filter_device.textChanged.connect(self.on_ai_filter_changed)
        filter_layout.addWidget(self.ai_filter_device, stretch=1)

        # 5. Model filter
        filter_layout.addWidget(QLabel("Model AI:"))
        self.ai_filter_model = QLineEdit()
        self.ai_filter_model.setPlaceholderText("Model...")
        self.ai_filter_model.setStyleSheet("padding: 4px; font-size: 12px;")
        self.ai_filter_model.textChanged.connect(self.on_ai_filter_changed)
        filter_layout.addWidget(self.ai_filter_model, stretch=1)

        # 6. Time filter
        filter_layout.addWidget(QLabel("Thời gian:"))
        self.ai_filter_time = QLineEdit()
        self.ai_filter_time.setPlaceholderText("dd/mm/yyyy...")
        self.ai_filter_time.setStyleSheet("padding: 4px; font-size: 12px;")
        self.ai_filter_time.textChanged.connect(self.on_ai_filter_changed)
        filter_layout.addWidget(self.ai_filter_time, stretch=1)

        # Clear filter button
        clear_filter_btn = QPushButton("🧹 Xóa lọc")
        clear_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #6B7280;
                color: white;
                font-size: 11px;
                font-weight: bold;
                padding: 4px 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4B5563; }
        """)
        clear_filter_btn.clicked.connect(self.clear_all_ai_filters)
        filter_layout.addWidget(clear_filter_btn)

        layout.addWidget(filter_group)

        # Instruction note
        hint_label = QLabel("💡 <i>Danh sách hiển thị các bài viết được AI phân tích có <b>should_notify = True</b> (khớp nhu cầu mua bán / nhà trọ / việc làm). Bấm đúp chuột để xem chi tiết.</i>")
        hint_label.setStyleSheet("color: #4B5563; font-size: 12px; margin-bottom: 2px;")
        layout.addWidget(hint_label)

        # Batch Action Toolbar
        ai_action_toolbar = QHBoxLayout()
        ai_action_toolbar.setContentsMargins(0, 4, 0, 4)
        ai_action_toolbar.setSpacing(10)

        self.ai_select_all_cb = QCheckBox("Chọn tất cả trang này")
        self.ai_select_all_cb.setStyleSheet("font-weight: bold; font-size: 12px; color: #5B21B6;")
        self.ai_select_all_cb.toggled.connect(self.on_ai_select_all_toggled)
        ai_action_toolbar.addWidget(self.ai_select_all_cb)

        ai_action_toolbar.addSpacing(5)

        self.btn_delete_selected_ai = QPushButton("🗑️ Xóa đã chọn (0)")
        self.btn_delete_selected_ai.setEnabled(False)
        self.btn_delete_selected_ai.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #991B1B;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
                border: 1px solid #FECACA;
            }
            QPushButton:hover:enabled { background-color: #FCA5A5; }
            QPushButton:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
                border: 1px solid #E5E7EB;
            }
        """)
        self.btn_delete_selected_ai.clicked.connect(self.delete_selected_ai_analyses)
        ai_action_toolbar.addWidget(self.btn_delete_selected_ai)

        self.btn_resend_telegram = QPushButton("🔔 Gửi lại Telegram (0)")
        self.btn_resend_telegram.setEnabled(False)
        self.btn_resend_telegram.setStyleSheet("""
            QPushButton {
                background-color: #EFF6FF;
                color: #1D4ED8;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
                border: 1px solid #BFDBFE;
            }
            QPushButton:hover:enabled { background-color: #DBEAFE; }
            QPushButton:disabled {
                background-color: #F3F4F6;
                color: #9CA3AF;
                border: 1px solid #E5E7EB;
            }
        """)
        self.btn_resend_telegram.clicked.connect(self.resend_telegram_for_selected)
        ai_action_toolbar.addWidget(self.btn_resend_telegram)

        self.btn_delete_all_ai = QPushButton("💥 Xóa tất cả")
        self.btn_delete_all_ai.setStyleSheet("""
            QPushButton {
                background-color: #DC2626;
                color: white;
                font-weight: bold;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #B91C1C; }
        """)
        self.btn_delete_all_ai.clicked.connect(self.delete_all_ai_analyses)
        ai_action_toolbar.addWidget(self.btn_delete_all_ai)

        ai_action_toolbar.addStretch()
        layout.addLayout(ai_action_toolbar)

        # Table Widget (Gridview)
        self.ai_analysis_table = QTableWidget()
        self.ai_analysis_table.setColumnCount(12)
        self.ai_analysis_table.setHorizontalHeaderLabels([
            "☑️", "STT", "Post ID", "Nhóm / Trang", "Từ khóa", "Model AI", "Mục tiêu / Nhu cầu", "Giá / Ngân sách", "Telegram", "Vai trò & Trích đoạn", "Đánh giá AI", "Hành động"
        ])

        
        header = self.ai_analysis_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.ai_analysis_table.setColumnWidth(0, 42)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(8, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(9, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(10, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(11, QHeaderView.ResizeMode.Fixed)
        self.ai_analysis_table.setColumnWidth(11, 215)

        self.ai_analysis_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.ai_analysis_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ai_analysis_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.ai_analysis_table.setAlternatingRowColors(True)
        self.ai_analysis_table.setStyleSheet("""
            QTableWidget {
                background-color: #FFFFFF;
                alternate-background-color: #F9FAFB;
                gridline-color: #E5E7EB;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #EDE9FE;
                color: #5B21B6;
                font-weight: bold;
                font-size: 12px;
                padding: 6px;
                border: 1px solid #DDD6FE;
            }
            QTableWidget::item:selected {
                background-color: #DDD6FE;
                color: #4C1D95;
            }
        """)
        self.ai_analysis_table.cellDoubleClicked.connect(self.on_ai_analysis_row_double_clicked)
        self.ai_analysis_table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.ai_analysis_table.customContextMenuRequested.connect(self.show_ai_analysis_context_menu)

        layout.addWidget(self.ai_analysis_table)

        # Bottom Paging Bar
        paging_bar = QHBoxLayout()
        paging_bar.setContentsMargins(4, 4, 4, 4)

        self.ai_first_page_btn = QPushButton("⏮ Đầu")
        self.ai_first_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.ai_first_page_btn.clicked.connect(self.go_first_ai_page)
        paging_bar.addWidget(self.ai_first_page_btn)

        self.ai_prev_page_btn = QPushButton("◀ Trước")
        self.ai_prev_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.ai_prev_page_btn.clicked.connect(self.go_prev_ai_page)
        paging_bar.addWidget(self.ai_prev_page_btn)

        paging_bar.addWidget(QLabel("Trang"))

        self.ai_page_spin = QSpinBox()
        self.ai_page_spin.setMinimum(1)
        self.ai_page_spin.setMaximum(1)
        self.ai_page_spin.setValue(1)
        self.ai_page_spin.setFixedWidth(60)
        self.ai_page_spin.valueChanged.connect(self.on_ai_page_spin_changed)
        paging_bar.addWidget(self.ai_page_spin)

        self.ai_total_pages_label = QLabel("/ 1")
        self.ai_total_pages_label.setStyleSheet("font-weight: bold; margin-right: 8px;")
        paging_bar.addWidget(self.ai_total_pages_label)

        self.ai_next_page_btn = QPushButton("Sau ▶")
        self.ai_next_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.ai_next_page_btn.clicked.connect(self.go_next_ai_page)
        paging_bar.addWidget(self.ai_next_page_btn)

        self.ai_last_page_btn = QPushButton("Cuối ⏭")
        self.ai_last_page_btn.setStyleSheet("padding: 4px 8px; font-size: 12px;")
        self.ai_last_page_btn.clicked.connect(self.go_last_ai_page)
        paging_bar.addWidget(self.ai_last_page_btn)

        paging_bar.addSpacing(20)
        paging_bar.addWidget(QLabel("Hiển thị/trang:"))

        self.ai_page_size_combo = QComboBox()
        self.ai_page_size_combo.addItems(["20", "50", "100", "200"])
        self.ai_page_size_combo.setCurrentText("50")
        self.ai_page_size_combo.currentTextChanged.connect(self.on_ai_page_size_changed)
        paging_bar.addWidget(self.ai_page_size_combo)

        paging_bar.addStretch()

        self.ai_total_label = QLabel("📊 Tổng số: 0 phân tích")
        self.ai_total_label.setStyleSheet("font-weight: bold; font-size: 13px; color: #5B21B6;")
        paging_bar.addWidget(self.ai_total_label)

        layout.addLayout(paging_bar)
        return tab

    def on_ai_checkbox_toggled(self, analysis_id: int, is_checked: bool):
        """Xử lý khi người dùng tích/bỏ tích checkbox từng bản ghi phân tích AI"""
        if is_checked:
            self.selected_ai_analysis_ids.add(int(analysis_id))
        else:
            self.selected_ai_analysis_ids.discard(int(analysis_id))
        self.update_ai_buttons_state()

    def on_ai_select_all_toggled(self, is_checked: bool):
        """Xử lý khi tích chọn tất cả bản ghi phân tích AI trên trang hiện tại"""
        for row in range(self.ai_analysis_table.rowCount()):
            cell = self.ai_analysis_table.cellWidget(row, 0)
            if cell:
                cb = cell.findChild(QCheckBox)
                if cb:
                    cb.blockSignals(True)
                    cb.setChecked(is_checked)
                    cb.blockSignals(False)
            if row < len(self.ai_analyses_data):
                aid = self.ai_analyses_data[row].get("id")
                if aid:
                    if is_checked:
                        self.selected_ai_analysis_ids.add(int(aid))
                    else:
                        self.selected_ai_analysis_ids.discard(int(aid))
        self.update_ai_buttons_state()

    def update_ai_buttons_state(self):
        """Cập nhật số lượng và trạng thái sáng/tối của các nút tác vụ Tab Lịch sử phân tích"""
        count = len(self.selected_ai_analysis_ids)
        if hasattr(self, 'btn_delete_selected_ai'):
            self.btn_delete_selected_ai.setText(f"🗑️ Xóa đã chọn ({count})")
            self.btn_delete_selected_ai.setEnabled(count > 0)
        if hasattr(self, 'btn_resend_telegram'):
            self.btn_resend_telegram.setText(f"🔔 Gửi lại Telegram ({count})")
            self.btn_resend_telegram.setEnabled(count > 0)

    def resend_telegram_for_selected(self):
        """Đặt lại trạng thái telegram_sent = 0 cho các bản ghi đã chọn và kích hoạt gửi ngay"""
        if not self.selected_ai_analysis_ids:
            return
        count = len(self.selected_ai_analysis_ids)
        for aid in list(self.selected_ai_analysis_ids):
            database.mark_telegram_analysis_sent(aid, status=0)
        self.log(f"🔔 [Telegram Dispatcher] Đã đưa {count} bài viết vào hàng đợi gửi Telegram. Đang tiến hành gửi...")
        if hasattr(self, 'telegram_dispatcher') and self.telegram_dispatcher:
            self.telegram_dispatcher.trigger_check_now()
        self.load_ai_analysis_data()
        QMessageBox.information(
            self,
            "Gửi lại Telegram",
            f"🎉 Đã đưa {count} bài viết vào hàng đợi gửi Telegram!\n\nBackground Thread đang tự động gửi đến Telegram Bot của bạn."
        )

    def delete_selected_ai_analyses(self):
        """Xác nhận và xóa các bản ghi phân tích AI đã chọn"""
        if not self.selected_ai_analysis_ids:
            return
        count = len(self.selected_ai_analysis_ids)
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa các bản ghi đã chọn",
            f"Bạn có chắc chắn muốn xóa {count} bản ghi phân tích AI đã chọn khỏi cơ sở dữ liệu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = database.delete_ai_analyses_by_ids(list(self.selected_ai_analysis_ids))
            self.log(f"🗑 Đã xóa {deleted_count} bản ghi phân tích AI đã chọn.")
            self.selected_ai_analysis_ids.clear()
            if hasattr(self, 'ai_select_all_cb'):
                self.ai_select_all_cb.blockSignals(True)
                self.ai_select_all_cb.setChecked(False)
                self.ai_select_all_cb.blockSignals(False)
            self.update_ai_buttons_state()
            self.load_ai_analysis_data()

    def delete_all_ai_analyses(self):
        """Xác nhận và xóa trắng toàn bộ lịch sử phân tích AI"""
        reply = QMessageBox.question(
            self,
            "Xác nhận XÓA TẤT CẢ lịch sử phân tích",
            "⚠️ CẢNH BÁO: Bạn có chắc chắn muốn XÓA TRẮNG toàn bộ lịch sử phân tích AI trong cơ sở dữ liệu?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            deleted_count = database.delete_all_ai_analyses()
            self.log(f"💥 Đã xóa trắng toàn bộ lịch sử phân tích AI ({deleted_count} bản ghi).")
            self.selected_ai_analysis_ids.clear()
            if hasattr(self, 'ai_select_all_cb'):
                self.ai_select_all_cb.blockSignals(True)
                self.ai_select_all_cb.setChecked(False)
                self.ai_select_all_cb.blockSignals(False)
            self.update_ai_buttons_state()
            self.load_ai_analysis_data()

    def on_ai_filter_changed(self):
        self.ai_current_page = 1
        self.load_ai_analysis_data()

    def clear_all_ai_filters(self):
        if hasattr(self, 'ai_search_input'):
            self.ai_search_input.blockSignals(True)
            self.ai_search_input.clear()
            self.ai_search_input.blockSignals(False)

        if hasattr(self, 'ai_filter_post_id'):
            self.ai_filter_post_id.blockSignals(True)
            self.ai_filter_post_id.clear()
            self.ai_filter_post_id.blockSignals(False)

        if hasattr(self, 'ai_filter_group_combo'):
            self.ai_filter_group_combo.blockSignals(True)
            self.ai_filter_group_combo.setEditText("")
            self.ai_filter_group_combo.blockSignals(False)

        if hasattr(self, 'ai_filter_keyword'):
            self.ai_filter_keyword.blockSignals(True)
            self.ai_filter_keyword.clear()
            self.ai_filter_keyword.blockSignals(False)

        if hasattr(self, 'ai_filter_device'):
            self.ai_filter_device.blockSignals(True)
            self.ai_filter_device.clear()
            self.ai_filter_device.blockSignals(False)

        if hasattr(self, 'ai_filter_model'):
            self.ai_filter_model.blockSignals(True)
            self.ai_filter_model.clear()
            self.ai_filter_model.blockSignals(False)

        if hasattr(self, 'ai_filter_time'):
            self.ai_filter_time.blockSignals(True)
            self.ai_filter_time.clear()
            self.ai_filter_time.blockSignals(False)

        self.ai_current_page = 1
        self.load_ai_analysis_data()

    def go_first_ai_page(self):
        if self.ai_current_page != 1:
            self.ai_current_page = 1
            self.load_ai_analysis_data()

    def go_prev_ai_page(self):
        if self.ai_current_page > 1:
            self.ai_current_page -= 1
            self.load_ai_analysis_data()

    def go_next_ai_page(self):
        if self.ai_current_page < self.ai_total_pages:
            self.ai_current_page += 1
            self.load_ai_analysis_data()

    def go_last_ai_page(self):
        if self.ai_current_page != self.ai_total_pages:
            self.ai_current_page = self.ai_total_pages
            self.load_ai_analysis_data()

    def on_ai_page_spin_changed(self, val):
        if val != self.ai_current_page:
            self.ai_current_page = val
            self.load_ai_analysis_data()

    def on_ai_page_size_changed(self, text):
        try:
            self.ai_page_size = int(text)
            self.ai_current_page = 1
            self.load_ai_analysis_data()
        except Exception:
            pass

    def load_ai_analysis_data(self):
        search_query = self.ai_search_input.text().strip() if hasattr(self, 'ai_search_input') else ""
        filters = {"should_notify": 1}
        if hasattr(self, 'ai_filter_post_id') and self.ai_filter_post_id.text().strip():
            filters["post_id"] = self.ai_filter_post_id.text().strip()
        if hasattr(self, 'ai_filter_group_combo') and self.ai_filter_group_combo.currentText().strip():
            filters["group_name"] = self.ai_filter_group_combo.currentText().strip()
        if hasattr(self, 'ai_filter_keyword') and self.ai_filter_keyword.text().strip():
            filters["matched_keyword"] = self.ai_filter_keyword.text().strip()
        if hasattr(self, 'ai_filter_device') and self.ai_filter_device.text().strip():
            filters["device_name"] = self.ai_filter_device.text().strip()
        if hasattr(self, 'ai_filter_model') and self.ai_filter_model.text().strip():
            filters["model_used"] = self.ai_filter_model.text().strip()
        if hasattr(self, 'ai_filter_time') and self.ai_filter_time.text().strip():
            filters["time_str"] = self.ai_filter_time.text().strip()

        total = database.get_ai_analyses_count(search_query=search_query, filters=filters)
        self.ai_total_count = total
        self.ai_total_pages = max(1, math.ceil(total / self.ai_page_size))

        if self.ai_current_page > self.ai_total_pages:
            self.ai_current_page = self.ai_total_pages
        if self.ai_current_page < 1:
            self.ai_current_page = 1

        if hasattr(self, 'ai_page_spin'):
            self.ai_page_spin.blockSignals(True)
            self.ai_page_spin.setMaximum(self.ai_total_pages)
            self.ai_page_spin.setValue(self.ai_current_page)
            self.ai_page_spin.blockSignals(False)

        if hasattr(self, 'ai_total_pages_label'):
            self.ai_total_pages_label.setText(f"/ {self.ai_total_pages}")

        if hasattr(self, 'ai_first_page_btn'):
            self.ai_first_page_btn.setEnabled(self.ai_current_page > 1)
            self.ai_prev_page_btn.setEnabled(self.ai_current_page > 1)
            self.ai_next_page_btn.setEnabled(self.ai_current_page < self.ai_total_pages)
            self.ai_last_page_btn.setEnabled(self.ai_current_page < self.ai_total_pages)

        if hasattr(self, 'ai_total_label'):
            self.ai_total_label.setText(f"📊 Tổng số: {total} bài phân tích bán hàng | Trang {self.ai_current_page}/{self.ai_total_pages}")

        offset = (self.ai_current_page - 1) * self.ai_page_size
        analyses = database.get_all_ai_analyses(limit=self.ai_page_size, offset=offset, search_query=search_query, filters=filters)
        self.ai_analyses_data = analyses
        
        self.ai_analysis_table.setRowCount(0)

        all_page_selected = bool(analyses)

        for row_idx, item in enumerate(analyses):
            self.ai_analysis_table.insertRow(row_idx)
            self.ai_analysis_table.setRowHeight(row_idx, 38)

            post_id = str(item.get("post_id", ""))
            group_name = item.get("group_name") or "N/A"
            matched_kw = item.get("matched_keyword") or ""
            model_used = item.get("model_used") or "N/A"
            target_name = item.get("target_name") or item.get("device_name") or "N/A"
            price = item.get("price") or item.get("price_or_budget") or "Thỏa thuận"
            actor_role = item.get("actor_role") or item.get("seller_type") or "N/A"
            matched_snippet = item.get("matched_snippet") or item.get("seller_snippet") or ""
            reason = item.get("reason") or ""
            permalink = item.get("permalink") or f"https://www.facebook.com/{post_id}"
            analysis_id = item.get("id")

            snippet_display = f"[{actor_role}] {matched_snippet}" if matched_snippet else actor_role

            is_checked = (analysis_id is not None and analysis_id in self.selected_ai_analysis_ids)
            if not is_checked:
                all_page_selected = False

            # Col 0: Checkbox
            cb_container = QWidget()
            cb_layout = QHBoxLayout(cb_container)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cb = QCheckBox()
            cb.setChecked(is_checked)
            cb.toggled.connect(lambda checked, aid=analysis_id: self.on_ai_checkbox_toggled(aid, checked))
            cb_layout.addWidget(cb)
            self.ai_analysis_table.setCellWidget(row_idx, 0, cb_container)

            # Col 1: STT
            item_stt = QTableWidgetItem(str(offset + row_idx + 1))
            item_stt.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_stt.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 2: Post ID
            item_id = QTableWidgetItem(post_id)
            item_id.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_id.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 3: Nhóm / Trang
            item_group = QTableWidgetItem(group_name)
            item_group.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 4: Từ khóa khớp
            item_kw = QTableWidgetItem(matched_kw)
            item_kw.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_kw.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 5: Model AI
            item_model = QTableWidgetItem(model_used)
            item_model.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_model.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 6: Mục tiêu / Nhu cầu
            item_dev = QTableWidgetItem(target_name)
            item_dev.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 7: Giá / Ngân sách
            item_price = QTableWidgetItem(price)
            item_price.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_price.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 8: Trạng thái Telegram
            tg_val = item.get("telegram_sent", 0)
            if tg_val == 1:
                item_tg = QTableWidgetItem("✅ Đã gửi")
                item_tg.setToolTip("Đã gửi cảnh báo Telegram thành công")
            elif tg_val == -1:
                item_tg = QTableWidgetItem("❌ Lỗi")
                item_tg.setToolTip("Gửi Telegram thất bại. Chọn dòng và bấm 'Gửi lại Telegram' để gửi lại.")
            else:
                item_tg = QTableWidgetItem("⏳ Chờ gửi")
                item_tg.setToolTip("Đang trong hàng đợi chờ Background Dispatcher Thread gửi.")
            item_tg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            item_tg.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 9: Vai trò & Trích đoạn
            item_snip = QTableWidgetItem(snippet_display)
            item_snip.setToolTip(matched_snippet)
            item_snip.setData(Qt.ItemDataRole.UserRole, post_id)

            # Col 10: Đánh giá AI
            item_reason = QTableWidgetItem(reason)
            item_reason.setToolTip(reason)
            item_reason.setData(Qt.ItemDataRole.UserRole, post_id)


            self.ai_analysis_table.setItem(row_idx, 1, item_stt)
            self.ai_analysis_table.setItem(row_idx, 2, item_id)
            self.ai_analysis_table.setItem(row_idx, 3, item_group)
            self.ai_analysis_table.setItem(row_idx, 4, item_kw)
            self.ai_analysis_table.setItem(row_idx, 5, item_model)
            self.ai_analysis_table.setItem(row_idx, 6, item_dev)
            self.ai_analysis_table.setItem(row_idx, 7, item_price)
            self.ai_analysis_table.setItem(row_idx, 8, item_tg)
            self.ai_analysis_table.setItem(row_idx, 9, item_snip)
            self.ai_analysis_table.setItem(row_idx, 10, item_reason)

            # Actions container: "🔍 Chi tiết", "🔗 Mở FB", & "🗑 Xóa"
            btn_container = QWidget()
            btn_layout = QHBoxLayout(btn_container)
            btn_layout.setContentsMargins(2, 2, 2, 2)
            btn_layout.setSpacing(4)
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

            self.ai_analysis_table.setCellWidget(row_idx, 11, btn_container)

            view_btn = QPushButton("🔍 Chi tiết")
            view_btn.setStyleSheet("""
                QPushButton {
                    background-color: #8B5CF6;
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 5px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #7C3AED; }
            """)
            view_btn.clicked.connect(lambda checked, pid=post_id: self.show_post_detail(pid))
            btn_layout.addWidget(view_btn)

            open_btn = QPushButton("🔗 Mở FB")
            open_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2563EB;
                    color: white;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 5px;
                    border-radius: 4px;
                }
                QPushButton:hover { background-color: #1D4ED8; }
            """)
            open_btn.clicked.connect(lambda checked, url=permalink: webbrowser.open(url))
            btn_layout.addWidget(open_btn)

            del_btn = QPushButton("🗑 Xóa")
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FEE2E2;
                    color: #991B1B;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 4px 5px;
                    border-radius: 4px;
                    border: 1px solid #FECACA;
                }
                QPushButton:hover { background-color: #FCA5A5; }
            """)
            del_btn.clicked.connect(lambda checked, aid=analysis_id, pid=post_id: self.delete_ai_analysis_record(aid, pid))
            btn_layout.addWidget(del_btn)

        if hasattr(self, 'ai_select_all_cb'):
            self.ai_select_all_cb.blockSignals(True)
            self.ai_select_all_cb.setChecked(all_page_selected and bool(analyses))
            self.ai_select_all_cb.blockSignals(False)

        self.update_ai_buttons_state()

    def delete_ai_analysis_record(self, analysis_id: int, post_id: str):
        """Xác nhận và xóa một bản ghi phân tích AI khỏi SQLite"""
        reply = QMessageBox.question(
            self,
            "Xác nhận xóa bản ghi",
            f"Bạn có chắc chắn muốn xóa bản ghi phân tích AI của bài viết ID: {post_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            ok = database.delete_ai_analysis_by_id(analysis_id)
            if ok:
                self.log(f"🗑 Đã xóa bản ghi phân tích AI bài viết {post_id} (ID: {analysis_id}).")
                if analysis_id in self.selected_ai_analysis_ids:
                    self.selected_ai_analysis_ids.discard(analysis_id)
                self.update_ai_buttons_state()
                self.load_ai_analysis_data()
            else:
                QMessageBox.warning(self, "Lỗi", f"Không thể xóa bản ghi phân tích ID: {analysis_id}")

    def show_ai_analysis_context_menu(self, pos):
        item = self.ai_analysis_table.itemAt(pos)
        if not item:
            return
        row = item.row()
        stt_item = self.ai_analysis_table.item(row, 1)
        if not stt_item:
            return
        post_id = stt_item.data(Qt.ItemDataRole.UserRole)
        if not post_id:
            return

        analysis_item = self.ai_analyses_data[row] if row < len(self.ai_analyses_data) else {}
        analysis_id = analysis_item.get("id")

        menu = QMenu(self)
        view_action = menu.addAction("🔍 Xem chi tiết bài viết & bình luận")
        open_action = menu.addAction("🔗 Mở trên Facebook (Trình duyệt)")
        copy_id_action = menu.addAction("📋 Sao chép Post ID")
        menu.addSeparator()
        del_action = menu.addAction("🗑 Xóa bản ghi phân tích này")

        action = menu.exec(self.ai_analysis_table.viewport().mapToGlobal(pos))
        if action == view_action:
            self.show_post_detail(post_id)
        elif action == open_action:
            permalink = analysis_item.get("permalink") or f"https://www.facebook.com/{post_id}"
            webbrowser.open(permalink)
        elif action == copy_id_action:
            QApplication.clipboard().setText(str(post_id))
        elif action == del_action and analysis_id:
            self.delete_ai_analysis_record(analysis_id, post_id)

    def on_ai_analysis_row_double_clicked(self, row, column):
        if column in (0, 10):
            return
        item = self.ai_analysis_table.item(row, 1)
        if not item:
            return
        post_id = item.data(Qt.ItemDataRole.UserRole)
        if post_id:
            self.show_post_detail(post_id)

    def refresh_group_autocomplete_options(self):
        """Cập nhật danh sách gợi ý nhóm/trang trong các dropdown autocomplete"""
        distinct_names = database.get_distinct_group_names()
        
        # Cho Tab Dữ liệu cào
        if hasattr(self, 'filter_group_combo'):
            curr_text = self.filter_group_combo.currentText()
            self.filter_group_combo.blockSignals(True)
            self.filter_group_combo.clear()
            self.filter_group_combo.addItem("")
            for name in distinct_names:
                self.filter_group_combo.addItem(name)
            self.filter_group_combo.setEditText(curr_text)
            self.filter_group_combo.blockSignals(False)

        # Cho Tab Lịch sử phân tích
        if hasattr(self, 'ai_filter_group_combo'):
            curr_ai_text = self.ai_filter_group_combo.currentText()
            self.ai_filter_group_combo.blockSignals(True)
            self.ai_filter_group_combo.clear()
            self.ai_filter_group_combo.addItem("")
            for name in distinct_names:
                self.ai_filter_group_combo.addItem(name)
            self.ai_filter_group_combo.setEditText(curr_ai_text)
            self.ai_filter_group_combo.blockSignals(False)

    def show_post_detail(self, post_id):
        post_data = database.get_post_by_id(str(post_id))
        if not post_data:
            QMessageBox.warning(self, "Thông báo", f"Không tìm thấy chi tiết bài viết ID: {post_id}")
            return
        dialog = PostDetailDialog(post_data, self)
        dialog.exec()

    def on_tab_changed(self, index):
        if index == 1:
            self.refresh_group_autocomplete_options()
            self.load_history_data()
        elif index == 2:
            self.refresh_group_autocomplete_options()
            self.load_ai_analysis_data()

    # --------------------------------------------------------------------------
    # Tab 4: Configuration (Telegram & AI Multi-Model Tagging)
    # --------------------------------------------------------------------------
    def create_config_tab(self):
        tab = QWidget()
        tab_vbox = QVBoxLayout(tab)
        tab_vbox.setContentsMargins(0, 0, 0, 0)

        # Scroll Area for responsive 50-50 layout
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        content_widget = QWidget()
        main_layout = QVBoxLayout(content_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(12)

        # 2 Columns (50% / 50%) layout
        two_col_layout = QHBoxLayout()
        two_col_layout.setSpacing(14)

        # ======================================================================
        # LEFT COLUMN (50%): Telegram & Network/Proxy
        # ======================================================================
        left_col = QVBoxLayout()
        left_col.setSpacing(12)

        # 1. Telegram Group
        tg_group = QGroupBox("📱 Cấu hình Telegram Bot")
        tg_layout = QVBoxLayout()
        tg_group.setLayout(tg_layout)

        self.tg_enabled_cb = QCheckBox("Bật thông báo qua Telegram")
        self.tg_enabled_cb.setStyleSheet("font-weight: bold; color: #1E3A8A;")
        self.tg_enabled_cb.toggled.connect(self.toggle_telegram_fields)
        tg_layout.addWidget(self.tg_enabled_cb)

        tg_grid = QGridLayout()
        tg_grid.addWidget(QLabel("Bot Token:"), 0, 0)
        
        token_row = QHBoxLayout()
        self.tg_token_input = QLineEdit()
        self.tg_token_input.setPlaceholderText("VD: 123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
        token_row.addWidget(self.tg_token_input)

        btn_token_help = QPushButton("?")
        btn_token_help.setFixedSize(22, 22)
        btn_token_help.setToolTip("Xem hướng dẫn cách lấy Telegram Bot Token")
        btn_token_help.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #4F46E5;
                font-weight: bold;
                font-size: 12px;
                border-radius: 11px;
                border: 1px solid #C7D2FE;
            }
            QPushButton:hover { background-color: #E0E7FF; }
        """)
        btn_token_help.clicked.connect(self.show_telegram_guide_dialog)
        token_row.addWidget(btn_token_help)
        tg_grid.addLayout(token_row, 0, 1)

        tg_grid.addWidget(QLabel("Chat ID:"), 1, 0)
        chat_id_row = QHBoxLayout()
        self.tg_chat_id_input = QLineEdit()
        self.tg_chat_id_input.setPlaceholderText("VD: -1001234567890 hoặc 123456789")
        chat_id_row.addWidget(self.tg_chat_id_input)

        btn_chat_id_help = QPushButton("?")
        btn_chat_id_help.setFixedSize(22, 22)
        btn_chat_id_help.setToolTip("Xem hướng dẫn cách lấy Chat ID (Cá nhân hoặc Nhóm)")
        btn_chat_id_help.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #4F46E5;
                font-weight: bold;
                font-size: 12px;
                border-radius: 11px;
                border: 1px solid #C7D2FE;
            }
            QPushButton:hover { background-color: #E0E7FF; }
        """)
        btn_chat_id_help.clicked.connect(self.show_telegram_guide_dialog)
        chat_id_row.addWidget(btn_chat_id_help)
        tg_grid.addLayout(chat_id_row, 1, 1)

        tg_layout.addLayout(tg_grid)

        # Telegram triggers
        self.tg_notify_finish_cb = QCheckBox("Gửi thông báo khi hoàn thành đợt quét")
        self.tg_notify_finish_cb.setChecked(True)
        tg_layout.addWidget(self.tg_notify_finish_cb)

        self.tg_notify_keyword_cb = QCheckBox("Gửi thông báo ngay khi phát hiện bài viết khớp từ khóa / AI xác nhận")
        self.tg_notify_keyword_cb.setChecked(True)
        tg_layout.addWidget(self.tg_notify_keyword_cb)

        # Test Telegram button
        self.test_tg_btn = QPushButton("🔔 Gửi tin nhắn kiểm tra kết nối Telegram")
        self.test_tg_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                font-weight: bold;
                padding: 7px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #2563EB; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.test_tg_btn.clicked.connect(self.test_telegram_connection)
        tg_layout.addWidget(self.test_tg_btn)

        left_col.addWidget(tg_group)

        # 2. Network & Proxy Group
        proxy_group = QGroupBox("🌐 Cấu hình Mạng & Proxy (Tùy chọn)")
        proxy_layout = QVBoxLayout()
        proxy_group.setLayout(proxy_layout)

        proxy_desc = QLabel("💡 Hỗ trợ: username:pass@ip:port hoặc ip:port (Để trống nếu chạy trực tiếp bằng mạng máy tính).")
        proxy_desc.setWordWrap(True)
        proxy_desc.setStyleSheet("font-size: 11px; color: #4B5563; line-height: 1.4;")
        proxy_layout.addWidget(proxy_desc)

        proxy_grid = QGridLayout()
        proxy_grid.addWidget(QLabel("Proxy:"), 0, 0)
        self.proxy_input = QLineEdit()
        self.proxy_input.setPlaceholderText("VD: admin:123456@103.150.12.34:8080 hoặc 103.150.12.34:8080")
        proxy_grid.addWidget(self.proxy_input, 0, 1)
        proxy_layout.addLayout(proxy_grid)

        left_col.addWidget(proxy_group)

        # 3. Diagnostics & Dev Support Group
        diag_group = QGroupBox("🩺 Chẩn đoán & Hỗ trợ Kỹ thuật")
        diag_layout = QVBoxLayout()
        diag_group.setLayout(diag_layout)

        diag_desc = QLabel(
            "Xuất dữ liệu bài viết, bình luận, lịch sử AI và logs ra tệp <code>.diagnose</code> để gửi cho Developer phân tích lỗi.<br>"
            "<span style='color: #059669; font-weight: bold;'>🔒 Bảo mật 100%:</span> "
            "Bảng cài đặt chứa Token Telegram, API Key AI, Cookie và Proxy hoàn toàn <b>KHÔNG</b> được xuất."
        )
        diag_desc.setWordWrap(True)
        diag_desc.setStyleSheet("font-size: 11px; color: #4B5563; line-height: 1.4;")
        diag_layout.addWidget(diag_desc)

        self.btn_export_diagnose = QPushButton("🩺 Gửi phân tích cho Dev (Xuất file .diagnose)")
        self.btn_export_diagnose.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.btn_export_diagnose.clicked.connect(self.export_diagnose_action)
        diag_layout.addWidget(self.btn_export_diagnose)
        left_col.addWidget(diag_group)

        # 4. OTA Software Update Group
        ota_group = QGroupBox("🔄 Cập nhật phần mềm (OTA Update)")
        ota_layout = QVBoxLayout()
        ota_group.setLayout(ota_layout)

        ota_ver_label = QLabel(f"Phiên bản hiện tại: <span style='color: #2563EB; font-weight: bold;'>v{APP_VERSION}</span>")
        ota_ver_label.setStyleSheet("font-size: 12px;")
        ota_layout.addWidget(ota_ver_label)

        self.ota_auto_check_cb = QCheckBox("Tự động kiểm tra bản cập nhật khi mở ứng dụng")
        self.ota_auto_check_cb.setChecked(True)
        ota_layout.addWidget(self.ota_auto_check_cb)

        self.btn_check_ota = QPushButton("🔍 Kiểm tra bản cập nhật mới")
        self.btn_check_ota.setStyleSheet("""
            QPushButton {
                background-color: #0284C7;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 7px 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #0369A1; }
        """)
        self.btn_check_ota.clicked.connect(lambda: self.check_for_updates_action(manual=True))
        ota_layout.addWidget(self.btn_check_ota)
        left_col.addWidget(ota_group)

        left_col.addStretch()

        two_col_layout.addLayout(left_col, 1)

        # ======================================================================
        # RIGHT COLUMN (50%): AI Analysis & Prompt Configuration
        # ======================================================================
        right_col = QVBoxLayout()
        right_col.setSpacing(12)

        ai_group = QGroupBox("🤖 Cấu hình AI Phân tích nội dung (Multi-Model Fallback)")
        ai_layout = QVBoxLayout()
        ai_group.setLayout(ai_layout)

        self.ai_enabled_cb = QCheckBox("Bật AI phân tích bài viết & bình luận")
        self.ai_enabled_cb.setStyleSheet("font-weight: bold; color: #1E3A8A;")
        self.ai_enabled_cb.toggled.connect(self.toggle_ai_fields)
        ai_layout.addWidget(self.ai_enabled_cb)

        # Provider Selector Row
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("<b>Nhà cung cấp AI:</b>"))
        self.ai_provider_combo = QComboBox()
        self.ai_provider_combo.addItem("✨ Google AI Studio (Gemini)", "google_ai")
        self.ai_provider_combo.addItem("🧠 OpenAI / OpenAI Tương thích", "openai")
        self.ai_provider_combo.setStyleSheet("padding: 5px; font-weight: bold; font-size: 12px;")
        self.ai_provider_combo.currentIndexChanged.connect(self.on_ai_provider_changed)
        provider_layout.addWidget(self.ai_provider_combo, stretch=1)
        ai_layout.addLayout(provider_layout)

        # Google AI Studio Guide & Link Banner
        self.google_ai_guide_widget = QWidget()
        google_guide_layout = QVBoxLayout(self.google_ai_guide_widget)
        google_guide_layout.setContentsMargins(0, 4, 0, 4)
        google_guide_layout.setSpacing(4)

        btn_open_google_studio = QPushButton("🔑 Mở Google AI Studio để lấy API Key miễn phí (aistudio.google.com)")
        btn_open_google_studio.setStyleSheet("""
            QPushButton {
                background-color: #E0F2FE;
                color: #0369A1;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                border-radius: 4px;
                border: 1px solid #BAE6FD;
            }
            QPushButton:hover { background-color: #BAE6FD; }
        """)
        btn_open_google_studio.clicked.connect(lambda: webbrowser.open("https://aistudio.google.com/app/apikey"))
        google_guide_layout.addWidget(btn_open_google_studio)

        google_note = QLabel("💡 <i>Hướng dẫn: Vào Google AI Studio ➔ Bấm 'Get API key' ➔ 'Create API key' ➔ Dán Key vào ô bên dưới.<br>• Model Gemini (như Gemini 2.5 Flash) sẽ tự động được tắt suy luận (thinking_budget: 0) để phản hồi JSON nhanh nhất.</i>")
        google_note.setStyleSheet("font-size: 11px; color: #0369A1;")
        google_note.setWordWrap(True)
        google_guide_layout.addWidget(google_note)

        ai_layout.addWidget(self.google_ai_guide_widget)

        # AI Grid (Base URL + API Key)
        # AI Grid (Base URL + API Key)
        self.ai_grid = QGridLayout()
        
        self.ai_base_url_label = QLabel("Base URL:")
        self.ai_base_url_input = QLineEdit()
        self.ai_base_url_input.setPlaceholderText("https://api.openai.com/v1 (Để trống mặc định dùng OpenAI chính hãng)")
        self.ai_grid.addWidget(self.ai_base_url_label, 0, 0)
        self.ai_grid.addWidget(self.ai_base_url_input, 0, 1)

        self.ai_api_key_label = QLabel("API Key:")
        self.ai_api_key_input = QLineEdit()
        self.ai_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.ai_api_key_input.setPlaceholderText("AIzaSy... (Gemini API Key)")
        self.ai_api_key_input.textChanged.connect(self.on_ai_api_key_text_changed)
        self.ai_grid.addWidget(self.ai_api_key_label, 1, 0)
        self.ai_grid.addWidget(self.ai_api_key_input, 1, 1)

        self.ai_timeout_label = QLabel("Timeout AI (giây):")
        
        timeout_container = QWidget()
        timeout_layout = QHBoxLayout(timeout_container)
        timeout_layout.setContentsMargins(0, 0, 0, 0)
        timeout_layout.setSpacing(8)

        self.ai_timeout_input = QLineEdit()
        self.ai_timeout_input.setValidator(QIntValidator(1, 9999))
        self.ai_timeout_input.setText("20")
        self.ai_timeout_input.setPlaceholderText("20")
        self.ai_timeout_input.setFixedWidth(70)
        self.ai_timeout_input.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ai_timeout_input.setToolTip("Thời gian tối đa chờ phản hồi từ AI cho mỗi bài viết (giây). Nhập số nguyên từ 1 đến 9999.")
        self.ai_timeout_input.setStyleSheet("""
            QLineEdit {
                padding: 4px 8px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-weight: bold;
                background: white;
                color: #0F172A;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
            }
        """)

        timeout_layout.addWidget(self.ai_timeout_input)
        timeout_layout.addStretch()

        self.ai_grid.addWidget(self.ai_timeout_label, 2, 0)
        self.ai_grid.addWidget(timeout_container, 2, 1)

        ai_layout.addLayout(self.ai_grid)

        # 1. Google AI Studio Models Checkbox Widget
        self.gemini_model_selector = GeminiModelSelectorWidget()
        self.gemini_model_selector.btn_refresh.clicked.connect(self.on_fetch_gemini_models_clicked)
        ai_layout.addWidget(self.gemini_model_selector)

        # 2. OpenAI Models Checkbox Selector Widget
        self.openai_model_selector = OpenAIModelSelectorWidget()
        self.openai_model_selector.btn_refresh.clicked.connect(self.fetch_openai_models_action)
        self.openai_model_selector.btn_test_models.clicked.connect(self.test_ai_models_live_action)
        self.ai_model_tag_widget = self.openai_model_selector  # alias for backwards compatibility
        self.openai_models_container = self.openai_model_selector  # alias for backwards compatibility
        self.btn_fetch_openai_models = self.openai_model_selector.btn_refresh
        self.btn_test_models = self.openai_model_selector.btn_test_models
        ai_layout.addWidget(self.openai_model_selector)

        # System Prompt Section with Presets & Guide Button
        prompt_header_layout = QHBoxLayout()
        prompt_header_layout.addWidget(QLabel("<b>System Prompt:</b>"))
        prompt_header_layout.addStretch()

        btn_preset_seller = QPushButton("🛒 Mẫu Mua Bán")
        btn_preset_seller.setToolTip("Áp dụng mẫu Prompt chuyên tìm người rao bán / thanh lý sản phẩm, dịch vụ")
        btn_preset_seller.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #4338CA;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #C7D2FE;
            }
            QPushButton:hover { background-color: #E0E7FF; }
        """)
        btn_preset_seller.clicked.connect(lambda: self.apply_prompt_preset(database.DEFAULT_AI_PROMPT))
        prompt_header_layout.addWidget(btn_preset_seller)

        btn_preset_buyer = QPushButton("🏷 Mẫu Tìm Mua")
        btn_preset_buyer.setToolTip("Áp dụng mẫu Prompt chuyên tìm người cần mua / tìm kiếm sản phẩm, dịch vụ")
        btn_preset_buyer.setStyleSheet("""
            QPushButton {
                background-color: #FEF3C7;
                color: #92400E;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #FDE68A;
            }
            QPushButton:hover { background-color: #FDE68A; }
        """)
        btn_preset_buyer.clicked.connect(lambda: self.apply_prompt_preset(database.DEFAULT_BUYER_AI_PROMPT))
        prompt_header_layout.addWidget(btn_preset_buyer)

        btn_preset_rental = QPushButton("🏢 Mẫu Phòng Trọ / BĐS")
        btn_preset_rental.setToolTip("Áp dụng mẫu Prompt chuyên tìm người cho thuê hoặc tìm thuê phòng trọ, căn hộ, mặt bằng")
        btn_preset_rental.setStyleSheet("""
            QPushButton {
                background-color: #F0FDF4;
                color: #166534;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #BBF7D0;
            }
            QPushButton:hover { background-color: #DCFCE7; }
        """)
        btn_preset_rental.clicked.connect(lambda: self.apply_prompt_preset(database.DEFAULT_RENTAL_AI_PROMPT))
        prompt_header_layout.addWidget(btn_preset_rental)

        btn_preset_job = QPushButton("💼 Mẫu Việc Làm / Tuyển Dụng")
        btn_preset_job.setToolTip("Áp dụng mẫu Prompt chuyên tìm tin tuyển dụng nhân viên hoặc người tìm việc làm / freelance")
        btn_preset_job.setStyleSheet("""
            QPushButton {
                background-color: #FDF2F8;
                color: #9D174D;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #FBCFE8;
            }
            QPushButton:hover { background-color: #FCE7F3; }
        """)
        btn_preset_job.clicked.connect(lambda: self.apply_prompt_preset(database.DEFAULT_JOB_AI_PROMPT))
        prompt_header_layout.addWidget(btn_preset_job)

        btn_prompt_guide = QPushButton("💡 Hướng dẫn tạo Prompt mới")
        btn_prompt_guide.setToolTip("Xem hướng dẫn và copy mẫu Meta-Prompt gửi cho ChatGPT / Claude / Gemini / DeepSeek để tạo Prompt theo ý muốn")
        btn_prompt_guide.setStyleSheet("""
            QPushButton {
                background-color: #ECFDF5;
                color: #047857;
                font-size: 11px;
                font-weight: bold;
                padding: 3px 8px;
                border-radius: 4px;
                border: 1px solid #A7F3D0;
            }
            QPushButton:hover { background-color: #D1FAE5; }
        """)
        btn_prompt_guide.clicked.connect(self.show_prompt_guide_dialog)
        prompt_header_layout.addWidget(btn_prompt_guide)

        ai_layout.addLayout(prompt_header_layout)


        self.ai_prompt_input = QTextEdit()
        self.ai_prompt_input.setMinimumHeight(140)
        self.ai_prompt_input.setMaximumHeight(220)
        self.ai_prompt_input.setPlaceholderText("Hướng dẫn prompt cho AI...")
        self.ai_prompt_input.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; padding: 6px;")
        ai_layout.addWidget(self.ai_prompt_input)

        # Test Sample Post AI button
        self.test_ai_btn = QPushButton("🤖 Gửi thử nghiệm phân tích bài mẫu")
        self.test_ai_btn.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: white;
                font-weight: bold;
                padding: 6px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4F46E5; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.test_ai_btn.clicked.connect(self.test_ai_connection)
        ai_layout.addWidget(self.test_ai_btn)

        right_col.addWidget(ai_group)
        two_col_layout.addLayout(right_col, 1)

        main_layout.addLayout(two_col_layout)

        # Save Button (Full width at bottom)
        save_cfg_btn = QPushButton("💾 Lưu Cấu hình vào SQLite")
        save_cfg_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
        """)
        save_cfg_btn.clicked.connect(lambda: self.save_all_settings_to_db(silent=False))
        main_layout.addWidget(save_cfg_btn)

        scroll_area.setWidget(content_widget)
        tab_vbox.addWidget(scroll_area)
        return tab

    def get_current_ai_provider(self) -> str:
        """Lấy nhà cung cấp AI hiện tại: 'google_ai' hoặc 'openai'"""
        if hasattr(self, 'ai_provider_combo') and self.ai_provider_combo:
            data = self.ai_provider_combo.currentData()
            if data:
                return data
        return "google_ai"

    def get_resolved_ai_base_url(self) -> str:
        """Lấy Base URL đã được chuẩn hóa theo Provider"""
        provider = self.get_current_ai_provider()
        user_url = self.ai_base_url_input.text().strip() if hasattr(self, 'ai_base_url_input') else ""
        return ai_analyzer.normalize_ai_base_url(user_url, provider=provider)

    def get_active_ai_models(self) -> list[str]:
        """Lấy danh sách các model AI được tích chọn/kích hoạt theo Provider"""
        provider = self.get_current_ai_provider()
        if provider == "google_ai":
            if hasattr(self, 'gemini_model_selector') and self.gemini_model_selector:
                return self.gemini_model_selector.get_active_models()
            return ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"]
        else:
            if hasattr(self, 'ai_model_tag_widget') and self.ai_model_tag_widget:
                return self.ai_model_tag_widget.get_active_models()
            return ["gpt-4o-mini"]

    def on_ai_provider_changed(self):
        """Xử lý khi thay đổi nhà cung cấp AI giữa Google AI Studio và OpenAI"""
        provider = self.get_current_ai_provider()
        is_google = (provider == "google_ai")

        if hasattr(self, 'google_ai_guide_widget'):
            self.google_ai_guide_widget.setVisible(is_google)

        if hasattr(self, 'ai_base_url_label') and hasattr(self, 'ai_base_url_input'):
            self.ai_base_url_label.setVisible(not is_google)
            self.ai_base_url_input.setVisible(not is_google)

        if hasattr(self, 'gemini_model_selector'):
            self.gemini_model_selector.setVisible(is_google)

        if hasattr(self, 'openai_models_container'):
            self.openai_models_container.setVisible(not is_google)

        if hasattr(self, 'ai_api_key_input'):
            if is_google:
                self.ai_api_key_input.setPlaceholderText("AIzaSy... (Nhập Gemini API Key từ Google AI Studio)")
                key = self.ai_api_key_input.text().strip()
                if key and len(key) >= 20 and hasattr(self, 'gemini_model_selector'):
                    self.gemini_model_selector.fetch_models_from_key(key)
            else:
                self.ai_api_key_input.setPlaceholderText("sk-... (Nhập OpenAI API Key)")

    def on_fetch_gemini_models_clicked(self):
        """Nút bấm thủ công để tải lại danh sách Models Gemini từ API Key"""
        key = self.ai_api_key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Chưa có API Key", "Vui lòng nhập API Key của Google AI Studio trước khi tải danh sách models.")
            return
        self.gemini_model_selector.fetch_models_from_key(key)

    def fetch_openai_models_action(self):
        """Khởi chạy worker tải danh sách model trực tiếp từ OpenAI / Base URL API"""
        base_url = self.get_resolved_ai_base_url()
        api_key = self.ai_api_key_input.text().strip()

        if hasattr(self, 'btn_fetch_openai_models'):
            self.btn_fetch_openai_models.setEnabled(False)
            self.btn_fetch_openai_models.setText("⏳ Đang tải...")
        self.log(f"🔄 Đang gửi yêu cầu lấy danh sách models từ API ({base_url})...")

        self.openai_fetch_worker = FetchOpenAIModelsWorker(base_url, api_key)

        def on_finished(ok: bool, models: list, msg: str):
            if hasattr(self, 'btn_fetch_openai_models'):
                self.btn_fetch_openai_models.setEnabled(True)
                self.btn_fetch_openai_models.setText("🔄 Tải Models từ API")
            if ok and models:
                self.ai_model_tag_widget.set_models_data(models)
                active = self.ai_model_tag_widget.get_active_models()
                default_m = "gpt-4o-mini"
                database.set_setting("ai_models", ", ".join(active) if active else default_m)
                database.set_setting("ai_models_data", json.dumps(self.ai_model_tag_widget.get_all_models_data(), ensure_ascii=False))
                self.log(f"✅ {msg}")
                QMessageBox.information(
                    self,
                    "Tải Models thành công",
                    f"✅ {msg}\n\nĐã nạp {len(models)} models vào danh sách. Các model Thinking/suy luận đã được tự động đánh dấu loại trừ."
                )
            else:
                self.log(f"⚠️ {msg}")
                QMessageBox.warning(
                    self,
                    "Không tải được Models",
                    f"⚠️ {msg}\n\nVui lòng kiểm tra lại Base URL và API Key."
                )

        self.openai_fetch_worker.finished_signal.connect(on_finished)
        self.openai_fetch_worker.start()

    def on_ai_api_key_text_changed(self, text: str):
        """Tự động phân tích và tải danh sách model khi người dùng dán API Key hợp lệ"""
        provider = self.get_current_ai_provider()
        clean_key = text.strip()
        if provider == "google_ai" and clean_key.startswith("AIzaSy") and len(clean_key) >= 30:
            if hasattr(self, 'gemini_model_selector'):
                self.gemini_model_selector.fetch_models_from_key(clean_key)
        elif provider == "openai" and clean_key.startswith("sk-") and len(clean_key) >= 35:
            # Nếu danh sách model OpenAI đang rỗng, tự động fetch
            if hasattr(self, 'ai_model_tag_widget') and not self.ai_model_tag_widget.get_all_models_data():
                self.fetch_openai_models_action()

    def show_telegram_guide_dialog(self):
        """Mở hộp thoại hướng dẫn lấy Bot Token và Chat ID Telegram"""
        dialog = TelegramGuideDialog(self)
        dialog.exec()

    def show_prompt_guide_dialog(self):
        """Mở hộp thoại hướng dẫn tạo và tùy biến Prompt mới cho AI"""
        dialog = PromptGuideDialog(self)
        dialog.exec()

    def get_ai_timeout(self) -> int:
        """Lấy giá trị timeout AI dạng số nguyên (mặc định 20 giây, 1 - 9999s)"""
        if hasattr(self, 'ai_timeout_input'):
            val = self.ai_timeout_input.text().strip()
            if val.isdigit():
                return max(1, min(9999, int(val)))
        return 20

    def test_ai_models_live_action(self):
        """
        Kiểm tra thực tế qua API từng model bất đồng bộ bằng QThread:
        - Cho phép bấm nút '⏹ Dừng test' để dừng kiểm tra bất kỳ lúc nào.
        - Cập nhật hiệu ứng xoay / đang test trực tiếp trên từng ô checkbox.
        - Hoàn toàn không làm đơ/treo giao diện.
        - Tự động cập nhật trạng thái hợp lệ/loại trừ lên giao diện và lưu SQLite.
        """
        # Nếu đang chạy test -> Bấm để DỪNG
        if hasattr(self, 'ai_test_worker') and self.ai_test_worker and self.ai_test_worker.isRunning():
            self.ai_test_worker.stop()
            self.btn_test_models.setText("⏳ Đang dừng...")
            self.btn_test_models.setEnabled(False)
            self.log("🛑 Người dùng yêu cầu dừng kiểm tra models...")
            return

        provider = self.get_current_ai_provider()
        base_url = self.get_resolved_ai_base_url()
        api_key = self.ai_api_key_input.text().strip()
        models = self.get_active_ai_models()

        if not api_key:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập API Key trước khi kiểm tra.")
            return

        if not models:
            QMessageBox.warning(self, "Chưa có Model", "Vui lòng chọn ít nhất một Model AI để kiểm tra.")
            return

        self.btn_test_models.setEnabled(True)
        self.btn_test_models.setText(f"⏹ Dừng test (0/{len(models)})")
        self.btn_test_models.setToolTip("Bấm để dừng quá trình kiểm tra models ngay lập tức")
        self.btn_test_models.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: white;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
            }
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.log(f"🧪 Đang thực hiện kiểm tra thực tế {len(models)} model AI qua {provider.upper()} ({base_url})...")

        timeout = self.get_ai_timeout()

        self.ai_test_worker = TestAIModelsWorker(
            base_url=base_url,
            api_key=api_key,
            models=models,
            timeout=timeout,
            provider=provider
        )

        def on_model_started(model_name: str):
            if provider == "openai" and hasattr(self, 'openai_model_selector'):
                self.openai_model_selector.set_model_testing_state(model_name)

        def on_progress(current: int, total: int, model_name: str):
            self.btn_test_models.setText(f"⏹ Dừng test ({current}/{total})")
            if provider == "openai" and hasattr(self, 'openai_model_selector'):
                self.openai_model_selector.set_model_testing_state(model_name, current, total)

        def on_single_tested(res: dict):
            if provider == "openai" and hasattr(self, 'openai_model_selector'):
                self.openai_model_selector.set_single_model_result(res)

        def on_all_finished(results: list):
            self.btn_test_models.setEnabled(True)
            self.btn_test_models.setText("🧪 Test AI & Kiểm tra Models")
            self.btn_test_models.setToolTip("Gửi request thực tế qua API tới từng model: Loại trừ model bị lỗi hoặc không trả về JSON thuần")
            self.btn_test_models.setStyleSheet("""
                QPushButton {
                    background-color: #8B5CF6;
                    color: white;
                    font-size: 10px;
                    font-weight: bold;
                    padding: 2px 8px;
                    border-radius: 3px;
                }
                QPushButton:hover { background-color: #7C3AED; }
                QPushButton:disabled { background-color: #9CA3AF; }
            """)

            if provider == "openai" and hasattr(self, 'openai_model_selector'):
                self.openai_model_selector.update_with_test_results(results)

            valid_models = [r["name"] for r in results if r.get("is_valid")]
            invalid_models = [r for r in results if not r.get("is_valid")]

            # Tự động lưu cấu hình model sau khi test
            default_m = "gemini-2.0-flash" if provider == "google_ai" else "gpt-4o-mini"
            active_str = ", ".join(valid_models) if valid_models else default_m
            database.set_setting("ai_models", active_str)
            if provider == "openai" and hasattr(self, 'openai_model_selector'):
                database.set_setting("ai_models_data", json.dumps(self.openai_model_selector.get_all_models_data(), ensure_ascii=False))

            report_msg = (
                f"📊 <b>Kết quả kiểm tra thực tế ({len(results)} model qua {provider.upper()}):</b><br><br>"
                f"✅ <b>Hợp lệ ({len(valid_models)} model):</b> {', '.join(valid_models) if valid_models else 'Không có'}<br><br>"
            )
            if invalid_models:
                report_msg += "❌ <b>Bị loại trừ / Lỗi:</b><br>"
                for inv in invalid_models:
                    report_msg += f"• <code>{inv['name']}</code>: <i>{inv['message']}</i><br>"

            self.log(f"✅ Hoàn tất kiểm tra models: {len(valid_models)} hợp lệ, {len(invalid_models)} bị loại trừ.")
            QMessageBox.information(self, "Kết quả kiểm tra Model AI", report_msg)

        self.ai_test_worker.model_testing_started.connect(on_model_started)
        self.ai_test_worker.progress_signal.connect(on_progress)
        self.ai_test_worker.model_tested_single.connect(on_single_tested)
        self.ai_test_worker.log_signal.connect(self.log)
        self.ai_test_worker.finished_all_signal.connect(on_all_finished)
        self.ai_test_worker.start()

    def apply_prompt_preset(self, preset_prompt: str):
        """Áp dụng mẫu prompt có sẵn vào ô nhập liệu"""
        self.ai_prompt_input.setPlainText(preset_prompt)
        self.log("📋 Đã áp dụng mẫu System Prompt mới vào ô cấu hình.")

    # --------------------------------------------------------------------------
    # Settings Management (SQLite Persistence)
    # --------------------------------------------------------------------------
    def load_saved_settings(self):
        """Nạp toàn bộ cấu hình đã lưu từ SQLite khi khởi động"""
        settings = database.get_all_settings()
        
        # Tab 1: Group URLs & Settings from facebook_groups table
        groups = database.get_all_groups()
        self.group_list_widget.set_groups(groups)

        self.group_post_count.setValue(int(settings.get("post_count", 5)))
        self.group_min_comments.setValue(int(settings.get("min_comments", 0)))
        
        inf_on = settings.get("infinite_loop", "0") == "1"
        self.infinite_loop_cb.setChecked(inf_on)
        self.loop_interval_spin.setValue(int(settings.get("loop_interval", 60)))
        self.toggle_infinite_loop(inf_on)

        # Tab 1: Keywords
        saved_kw = settings.get("keywords", "")
        if saved_kw:
            try:
                kw_list = json.loads(saved_kw)
                if isinstance(kw_list, list):
                    self.tag_widget.set_tags(kw_list)
            except Exception:
                pass

        # Auth cookies
        self.cookie_raw_json = settings.get("cookie_raw_json", "")
        self.cookie_string = settings.get("cookie_string", "")
        self.cookies = parse_cookies(self.cookie_string)
        self.fb_dtsg = settings.get("fb_dtsg", "")

        # Tab 4: Telegram Settings
        tg_on = settings.get("telegram_enabled", "0") == "1"
        self.tg_enabled_cb.setChecked(tg_on)
        self.tg_token_input.setText(settings.get("telegram_token", ""))
        self.tg_chat_id_input.setText(settings.get("telegram_chat_id", ""))
        self.tg_notify_finish_cb.setChecked(settings.get("notify_on_finish", "0") == "1")
        self.tg_notify_keyword_cb.setChecked(settings.get("notify_on_keyword", "0") == "1")
        self.toggle_telegram_fields(tg_on)

        # Tab 4: AI Settings
        ai_on = settings.get("ai_enabled", "0") == "1"
        self.ai_enabled_cb.setChecked(ai_on)

        saved_provider = settings.get("ai_provider", "google_ai")
        idx = self.ai_provider_combo.findData(saved_provider)
        if idx >= 0:
            self.ai_provider_combo.setCurrentIndex(idx)
        else:
            self.ai_provider_combo.setCurrentIndex(0)

        self.ai_base_url_input.setText(settings.get("ai_base_url", ""))
        saved_api_key = settings.get("ai_api_key", "")
        self.ai_api_key_input.setText(saved_api_key)

        saved_ai_timeout = settings.get("ai_timeout", "20")
        if hasattr(self, 'ai_timeout_input'):
            self.ai_timeout_input.setText(str(saved_ai_timeout) if saved_ai_timeout else "20")
        
        # Load Gemini selected models
        saved_gemini = settings.get("ai_gemini_models", "")
        if saved_gemini:
            g_list = [m.strip() for m in saved_gemini.split(",") if m.strip()]
            self.gemini_model_selector.set_selected_models(g_list)
        elif saved_provider == "google_ai" and settings.get("ai_models"):
            g_list = [m.strip() for m in settings.get("ai_models", "").split(",") if m.strip()]
            self.gemini_model_selector.set_selected_models(g_list)

        # Load OpenAI models
        models_data_str = settings.get("ai_models_data", "")
        if models_data_str:
            try:
                models_data = json.loads(models_data_str)
                if isinstance(models_data, list):
                    self.ai_model_tag_widget.set_models_data(models_data)
            except Exception:
                pass
        else:
            default_models = "gpt-4o-mini, gpt-4o"
            models_str = settings.get("ai_models") or settings.get("ai_model") or default_models
            models_list = [m.strip() for m in models_str.split(",") if m.strip() and not m.strip().startswith("gemini-")]
            self.ai_model_tag_widget.set_tags(models_list if models_list else ["gpt-4o-mini", "gpt-4o"])

        self.on_ai_provider_changed()

        # Tab 4: Proxy Settings (Single Proxy input with backward compatibility)
        proxy_val = settings.get("proxy", "") or settings.get("static_proxy", "") or settings.get("rotating_proxy", "")
        self.proxy_input.setText(proxy_val)

        # Tab 4: OTA update settings
        if hasattr(self, 'ota_auto_check_cb'):
            self.ota_auto_check_cb.setChecked(settings.get("ota_auto_check", "1") == "1")

        saved_prompt = settings.get("ai_prompt", "").strip()
        if not saved_prompt or "Bạn là chuyên gia phân tích bài đăng Facebook." in saved_prompt or "Bạn là chuyên gia phân tích dữ liệu Facebook." in saved_prompt:
            saved_prompt = database.DEFAULT_AI_PROMPT
        self.ai_prompt_input.setPlainText(saved_prompt)
        self.toggle_ai_fields(ai_on)

        # Cập nhật cấu hình cho AI Dispatcher ngầm
        if hasattr(self, 'ai_dispatcher') and self.ai_dispatcher:
            provider = self.get_current_ai_provider()
            active_models = self.get_active_ai_models()
            default_model = "gemini-2.0-flash" if provider == "google_ai" else "gpt-4o-mini"
            timeout_val = self.get_ai_timeout()
            ai_cfg = {
                "enabled": ai_on,
                "provider": provider,
                "base_url": self.get_resolved_ai_base_url(),
                "api_key": self.ai_api_key_input.text().strip(),
                "models": active_models if active_models else [default_model],
                "prompt": saved_prompt,
                "timeout": timeout_val
            }
            tg_cfg = {
                "enabled": tg_on,
                "token": self.tg_token_input.text().strip(),
                "chat_id": self.tg_chat_id_input.text().strip(),
                "notify_on_finish": self.tg_notify_finish_cb.isChecked(),
                "notify_on_keyword": self.tg_notify_keyword_cb.isChecked()
            }
            self.ai_dispatcher.update_config(ai_cfg, tg_cfg)

    def save_group_urls_to_db(self):
        self.group_list_widget.save_to_db()

    def save_keywords_to_db(self):
        tags = self.tag_widget.get_tags()
        database.set_setting("keywords", json.dumps(tags, ensure_ascii=False))

    def save_all_settings_to_db(self, silent=False):
        """Lưu tất cả cấu hình từ giao diện vào SQLite"""
        self.group_list_widget.save_to_db()
        tags = self.tag_widget.get_tags()
        provider = self.get_current_ai_provider()
        active_models = self.get_active_ai_models()
        all_models_data = self.ai_model_tag_widget.get_all_models_data()
        default_model = "gemini-2.0-flash" if provider == "google_ai" else "gpt-4o-mini"
        ai_models_str = ", ".join(active_models) if active_models else default_model
        first_model = active_models[0] if active_models else default_model
        normalized_proxy = self.proxy_input.text().strip()
        timeout_val = self.get_ai_timeout()
        ota_auto = "1" if (hasattr(self, 'ota_auto_check_cb') and self.ota_auto_check_cb.isChecked()) else "0"

        data = {
            "keywords": json.dumps(tags, ensure_ascii=False),
            "post_count": str(self.group_post_count.value()),
            "min_comments": str(self.group_min_comments.value()),
            "infinite_loop": "1" if self.infinite_loop_cb.isChecked() else "0",
            "loop_interval": str(self.loop_interval_spin.value()),
            "telegram_enabled": "1" if self.tg_enabled_cb.isChecked() else "0",
            "telegram_token": self.tg_token_input.text().strip(),
            "telegram_chat_id": self.tg_chat_id_input.text().strip(),
            "notify_on_finish": "1" if self.tg_notify_finish_cb.isChecked() else "0",
            "notify_on_keyword": "1" if self.tg_notify_keyword_cb.isChecked() else "0",
            "ai_enabled": "1" if self.ai_enabled_cb.isChecked() else "0",
            "ai_provider": provider,
            "ai_base_url": self.ai_base_url_input.text().strip(),
            "ai_api_key": self.ai_api_key_input.text().strip(),
            "ai_timeout": str(timeout_val),
            "ai_model": first_model,
            "ai_models": ai_models_str,
            "ai_gemini_models": ", ".join(self.gemini_model_selector.get_active_models()),
            "ai_models_data": json.dumps(all_models_data, ensure_ascii=False),
            "ai_prompt": self.ai_prompt_input.toPlainText().strip(),
            "proxy": normalized_proxy,
            "static_proxy": normalized_proxy,
            "rotating_proxy": normalized_proxy,
            "cookie_string": self.cookie_string,
            "fb_dtsg": self.fb_dtsg,
            "ota_auto_check": ota_auto
        }
        database.save_settings_batch(data)
        self.refresh_group_autocomplete_options()

        # Hot-reload cấu hình ngay lập tức cho tiến trình AI Worker đang chạy (nếu có)
        ai_cfg = {
            "enabled": self.ai_enabled_cb.isChecked(),
            "provider": provider,
            "base_url": self.get_resolved_ai_base_url(),
            "api_key": self.ai_api_key_input.text().strip(),
            "models": active_models if active_models else [default_model],
            "prompt": self.ai_prompt_input.toPlainText().strip(),
            "timeout": timeout_val
        }
        tg_cfg = {
            "enabled": self.tg_enabled_cb.isChecked(),
            "token": self.tg_token_input.text().strip(),
            "chat_id": self.tg_chat_id_input.text().strip(),
            "notify_on_finish": self.tg_notify_finish_cb.isChecked(),
            "notify_on_keyword": self.tg_notify_keyword_cb.isChecked()
        }
        if hasattr(self, 'scraper_thread') and self.scraper_thread and self.scraper_thread.isRunning():
            if hasattr(self.scraper_thread, 'ai_worker') and self.scraper_thread.ai_worker:
                self.scraper_thread.ai_worker.update_config(ai_cfg, tg_cfg)
                self.log("⚡ [Hot-reload] Đã cập nhật Prompt và cấu hình AI mới ngay cho tiến trình đang quét!")
        if hasattr(self, 'ai_dispatcher') and self.ai_dispatcher:
            self.ai_dispatcher.update_config(ai_cfg, tg_cfg)

        if not silent:
            QMessageBox.information(self, "Thành công", "✅ Đã lưu toàn bộ cấu hình vào SQLite!")

    def export_diagnose_action(self):
        """Xuất dữ liệu SQLite ra tệp .diagnose (loại trừ bảng settings) để gửi cho Dev"""
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"facebook_scraper_diagnose_{now_str}.diagnose"
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Lưu tệp chẩn đoán (.diagnose) gửi cho Dev",
            default_name,
            "Diagnose File (*.diagnose);;SQL Dump (*.sql);;All Files (*)"
        )
        if not save_path:
            return

        ok, msg, total_records = database.export_diagnostics_sql(save_path)
        if ok:
            self.log(f"✅ {msg}")
            QMessageBox.information(
                self,
                "Xuất chẩn đoán thành công",
                f"🎉 <b>Đã xuất dữ liệu chẩn đoán thành công!</b><br><br>"
                f"• Tổng số bản ghi: <b>{total_records}</b><br>"
                f"• File đã lưu tại:<br><code>{save_path}</code><br><br>"
                f"🔒 <i>Lưu ý bảo mật: Toàn bộ bảng cài đặt chứa Token Telegram, API Key AI, Cookie và Proxy đã được loại trừ 100% để đảm bảo an toàn riêng tư. Bạn có thể yên tâm gửi tệp này cho Developer.</i>"
            )
        else:
            self.log(f"❌ {msg}")
            QMessageBox.critical(self, "Lỗi xuất chẩn đoán", msg)

    def check_for_updates_action(self, manual: bool = True):
        """Kiểm tra bản cập nhật mới từ GitHub và hiển thị UpdateDialog"""
        try:
            has_update, update_info, msg = check_github_update(current_version=APP_VERSION)
            if has_update:
                self.log(f"🔔 [OTA Update] {msg}")
                dialog = UpdateDialog(update_info, parent=self)
                dialog.exec()
            else:
                if manual:
                    QMessageBox.information(
                        self,
                        "Kiểm tra cập nhật",
                        f"✅ <b>Bạn đang sử dụng phiên bản mới nhất!</b><br><br>"
                        f"• Phiên bản hiện tại: <code>v{APP_VERSION}</code><br>"
                        f"• Phiên bản mới nhất trên GitHub: <code>v{update_info.get('latest_version', APP_VERSION)}</code>"
                    )
                else:
                    self.log(f"ℹ️ [OTA Update] {msg}")
        except Exception as e:
            if manual:
                QMessageBox.warning(self, "Lỗi kiểm tra cập nhật", f"Không thể kiểm tra cập nhật: {e}")
            self.log(f"⚠️ [OTA Update] Lỗi kiểm tra cập nhật: {e}")
            QMessageBox.information(self, "Thành công", "✅ Đã lưu toàn bộ cấu hình vào SQLite thành công!")
        self.log("💾 Đã lưu cấu hình vào SQLite.")

    def toggle_infinite_loop(self, checked):
        self.loop_interval_label.setEnabled(checked)
        self.loop_interval_spin.setEnabled(checked)

    def toggle_telegram_fields(self, checked):
        self.tg_token_input.setEnabled(checked)
        self.tg_chat_id_input.setEnabled(checked)
        self.tg_notify_finish_cb.setEnabled(checked)
        self.tg_notify_keyword_cb.setEnabled(checked)
        self.test_tg_btn.setEnabled(checked)

    def toggle_ai_fields(self, checked):
        if hasattr(self, 'ai_provider_combo'):
            self.ai_provider_combo.setEnabled(checked)
        if hasattr(self, 'google_ai_guide_widget'):
            self.google_ai_guide_widget.setEnabled(checked)
        if hasattr(self, 'gemini_model_selector'):
            self.gemini_model_selector.setEnabled(checked)
        if hasattr(self, 'openai_models_container'):
            self.openai_models_container.setEnabled(checked)
        self.ai_base_url_input.setEnabled(checked)
        self.ai_api_key_input.setEnabled(checked)
        if hasattr(self, 'ai_timeout_label'):
            self.ai_timeout_label.setEnabled(checked)
        if hasattr(self, 'ai_timeout_input'):
            self.ai_timeout_input.setEnabled(checked)
        self.ai_model_tag_widget.setEnabled(checked)
        self.ai_prompt_input.setEnabled(checked)
        if hasattr(self, 'btn_fetch_openai_models'):
            self.btn_fetch_openai_models.setEnabled(checked)
        if hasattr(self, 'btn_test_models'):
            self.btn_test_models.setEnabled(checked)
        if hasattr(self, 'test_ai_btn'):
            self.test_ai_btn.setEnabled(checked)

    def test_ai_connection(self):
        provider = self.get_current_ai_provider()
        base_url = self.get_resolved_ai_base_url()
        api_key = self.ai_api_key_input.text().strip()
        models = self.get_active_ai_models()
        prompt = self.ai_prompt_input.toPlainText().strip()
        timeout = self.get_ai_timeout()

        if not api_key:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập API Key trước khi kiểm tra.")
            return

        if not models:
            QMessageBox.warning(self, "Không có Model hợp lệ", "Không có model nào được chọn. Vui lòng chọn ít nhất một model.")
            return

        self.log(f"🤖 Đang gửi yêu cầu kiểm tra kết nối AI bài mẫu ({provider.upper()} | {base_url} | Models: {models} | Timeout: {timeout}s)...")
        ok, msg, res = ai_analyzer.test_ai_connection(base_url, api_key, models, prompt, provider=provider, timeout=timeout)
        if ok:
            QMessageBox.information(self, "Kết nối AI thành công", msg)
            self.log("✅ Kiểm tra kết nối AI thành công.")
        else:
            QMessageBox.critical(self, "Lỗi kết nối AI", msg)
            self.log(f"❌ Lỗi kết nối AI: {msg}")

    def test_telegram_connection(self):
        token = self.tg_token_input.text().strip()
        chat_id = self.tg_chat_id_input.text().strip()
        if not token or not chat_id:
            QMessageBox.warning(self, "Thiếu thông tin", "Vui lòng nhập Token và Chat ID trước khi kiểm tra.")
            return

        self.log("🔔 Đang gửi tin nhắn kiểm tra kết nối Telegram...")
        ok, msg = telegram_notifier.test_connection(token, chat_id)
        if ok:
            QMessageBox.information(self, "Kết nối thành công", "✅ Đã gửi tin nhắn test thành công tới Telegram!")
            self.log("✅ Gửi tin nhắn test Telegram thành công.")
        else:
            QMessageBox.critical(self, "Lỗi kết nối", f"❌ Không thể kết nối tới Telegram:\n{msg}")
            self.log(f"❌ Lỗi gửi tin nhắn test Telegram: {msg}")


    def configure_cookies(self):
        dialog = CookieDialog(self, self.cookie_string, self.fb_dtsg, self.cookie_raw_json)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.cookie_string = dialog.get_cookies()
            self.cookie_raw_json = dialog.get_raw_json()
            self.cookies = parse_cookies(self.cookie_string)
            self.fb_dtsg = dialog.get_dtsg()

            database.set_setting("cookie_string", self.cookie_string)
            database.set_setting("cookie_raw_json", self.cookie_raw_json)
            database.set_setting("fb_dtsg", self.fb_dtsg)

            if self.cookies:
                self.log(f"✅ Đã cấu hình {len(self.cookies)} cookies và token fb_dtsg.")
                QMessageBox.information(self, "Hoàn tất", f"Đã cấu hình {len(self.cookies)} cookies thành công!")
                
                # Tự động tải nhóm nếu được chọn
                if dialog.should_fetch_groups():
                    self.fetch_groups_from_cookie(self.cookies, self.fb_dtsg, use_browser=dialog.should_use_browser())
            else:
                self.log("⚠️ Đã xóa cấu hình authentication.")

    def fetch_groups_from_cookie(self, cookies=None, fb_dtsg=None, callback=None, use_browser: bool = False):
        """Khởi chạy worker tải danh sách nhóm Facebook từ Cookie và mở GroupSelectDialog"""
        cookies_to_use = cookies or self.cookies or parse_cookies(self.cookie_string)
        dtsg_to_use = fb_dtsg if fb_dtsg is not None else self.fb_dtsg
        
        if not cookies_to_use:
            reply = QMessageBox.question(
                self,
                "Chưa có Cookie",
                "Bạn chưa cấu hình Cookie Facebook. Bạn có muốn mở hộp thoại cấu hình Cookie ngay bây giờ không?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                self.configure_cookies()
            return

        # Hiển thị progress dialog trong lúc tải
        loading_text = "Đang mở trình duyệt tự động để tải toàn bộ danh sách nhóm..." if use_browser else "Đang kết nối tới Facebook để lấy danh sách nhóm..."
        progress_dlg = QProgressDialog(loading_text, "Hủy", 0, 0, self)
        progress_dlg.setWindowTitle("⏳ Đang tải nhóm Facebook...")
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setAutoClose(True)
        progress_dlg.setAutoReset(True)
        progress_dlg.show()
        
        mode_desc = "Trình duyệt tự động (Selenium)" if use_browser else "HTTP API & mbasic"
        self.log(f"🌐 Đang khởi chạy tiến trình lấy danh sách nhóm từ Cookie ({mode_desc})...")

        # Tạo worker thread
        self.group_fetch_worker = GroupFetchWorker(
            cookies=cookies_to_use,
            fb_dtsg=dtsg_to_use,
            max_pages=40,
            proxy=select_proxy(has_cookies=True),
            use_browser=use_browser,
            parent=self
        )
        
        progress_dlg.canceled.connect(self.group_fetch_worker.stop)

        def on_progress(msg):
            progress_dlg.setLabelText(msg)
            self.log(f"   {msg}")

        def on_finished(groups, err_msg):
            progress_dlg.close()
            if err_msg:
                self.log(f"❌ Lỗi tải danh sách nhóm: {err_msg}")
                QMessageBox.warning(self, "Lỗi tải nhóm", f"Không thể lấy danh sách nhóm từ Facebook:\n{err_msg}")
                return

            if not groups:
                self.log("⚠️ Không tìm thấy nhóm nào từ Cookie này (hoặc Cookie đã hết hạn).")
                QMessageBox.information(
                    self,
                    "Không tìm thấy nhóm",
                    "Không tìm thấy nhóm nào từ Cookie này.\n\n"
                    "Lưu ý: Đảm bảo tài khoản Facebook của bạn đã tham gia các nhóm và Cookie còn hiệu lực."
                )
                return

            self.log(f"🎉 Đã tìm thấy {len(groups)} nhóm từ Cookie! Đang mở hộp thoại chọn nhóm...")
            
            # Mở GroupSelectDialog
            existing_urls = self.group_list_widget.get_urls() if hasattr(self, 'group_list_widget') else []
            select_dlg = GroupSelectDialog(groups=groups, current_existing_urls=existing_urls, parent=self)
            if select_dlg.exec() == QDialog.DialogCode.Accepted:
                selected_groups = select_dlg.get_selected_groups()
                mode = select_dlg.get_import_mode()
                
                if callback:
                    callback(selected_groups, mode)
                else:
                    if mode == "replace":
                        self.group_list_widget.set_groups(selected_groups)
                    else:
                        # Append mode: Giữ lại nhóm cũ, bổ sung nhóm mới không trùng URL
                        current_groups = self.group_list_widget.get_groups()
                        current_urls = {g.get("url") for g in current_groups if g.get("url")}
                        
                        added_count = 0
                        for g in selected_groups:
                            if g.get("url") not in current_urls:
                                current_groups.append(g)
                                current_urls.add(g.get("url"))
                                added_count += 1
                        
                        self.group_list_widget.set_groups(current_groups)
                        
                    self.group_list_widget.save_to_db()
                
                self.log(f"✅ Đã nhập thành công {len(selected_groups)} nhóm vào danh sách theo dõi.")
                QMessageBox.information(
                    self,
                    "Thành công",
                    f"Đã nhập {len(selected_groups)} nhóm Facebook vào danh sách thành công!"
                )

        self.group_fetch_worker.status_signal.connect(on_progress)
        self.group_fetch_worker.finished_signal.connect(on_finished)
        self.group_fetch_worker.start()

    def open_user_guide(self):
        """Mở tài liệu hướng dẫn HTML trong trình duyệt mặc định"""
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.getcwd()
        meipass_dir = getattr(sys, '_MEIPASS', '')
        possible_paths = [
            os.path.abspath(os.path.join(exe_dir, "guides", "index.html")),
            os.path.abspath(os.path.join(exe_dir, "_internal", "guides", "index.html")),
            os.path.abspath(os.path.join(meipass_dir, "guides", "index.html")) if meipass_dir else "",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "guides", "index.html")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "guides", "index.html")),
            os.path.abspath("guides/index.html")
        ]
        guide_file = next((p for p in possible_paths if p and os.path.exists(p)), None)
        if guide_file:
            self.log(f"📖 Đang mở hướng dẫn sử dụng: {guide_file}")
            webbrowser.open(f"file:///{guide_file.replace(os.sep, '/')}")
        else:
            QMessageBox.warning(self, "Không tìm thấy file", "Chưa tìm thấy file tài liệu hướng dẫn `guides/index.html`.")


    # --------------------------------------------------------------------------
    # Scraping Execution
    # --------------------------------------------------------------------------
    def start_scraping(self):
        groups = self.group_list_widget.get_groups()
        urls = self.group_list_widget.get_urls()
        if not urls:
            QMessageBox.warning(self, "Cảnh báo", "Vui lòng nhập ít nhất một URL nhóm Facebook!")
            return

        # Auto-save current settings before running
        self.save_all_settings_to_db(silent=True)

        count = self.group_post_count.value()
        min_comments = self.group_min_comments.value()
        keywords = self.tag_widget.get_tags()
        infinite_loop = self.infinite_loop_cb.isChecked()
        loop_interval = self.loop_interval_spin.value()

        params = {
            'groups': groups,
            'urls': urls,
            'count': count,
            'min_comments': min_comments,
            'keywords': keywords,
            'infinite_loop': infinite_loop,
            'loop_interval': loop_interval
        }

        tg_config = {
            "enabled": self.tg_enabled_cb.isChecked(),
            "token": self.tg_token_input.text().strip(),
            "chat_id": self.tg_chat_id_input.text().strip(),
            "notify_on_finish": self.tg_notify_finish_cb.isChecked(),
            "notify_on_keyword": self.tg_notify_keyword_cb.isChecked()
        }

        provider = self.get_current_ai_provider()
        models = self.get_active_ai_models()
        default_model = "gemini-2.0-flash" if provider == "google_ai" else "gpt-4o-mini"
        timeout_val = self.get_ai_timeout()
        ai_config = {
            "enabled": self.ai_enabled_cb.isChecked(),
            "provider": provider,
            "base_url": self.get_resolved_ai_base_url(),
            "api_key": self.ai_api_key_input.text().strip(),
            "models": models if models else [default_model],
            "prompt": self.ai_prompt_input.toPlainText().strip(),
            "timeout": timeout_val
        }

        # UI state
        self.set_scraping_state(running=True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)

        self.scraper_thread = ScraperThread(params, self.cookies, self.fb_dtsg, tg_config, ai_config)
        self.scraper_thread.log_signal.connect(self.log)
        self.scraper_thread.progress_signal.connect(self.update_progress)
        self.scraper_thread.finished_signal.connect(self.scraping_finished)
        self.scraper_thread.start()

    def set_scraping_state(self, running: bool):
        """Cập nhật trạng thái giao diện khi đang quét hoặc dừng quét"""
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)

        if hasattr(self, 'cookie_btn'):
            self.cookie_btn.setEnabled(not running)

        # Khóa/mở các ô nhập liệu trên Tab 1 để tránh sửa tham số khi đang quét
        self.group_list_widget.setEnabled(not running)
        self.tag_widget.setEnabled(not running)
        self.group_post_count.setEnabled(not running)
        self.group_min_comments.setEnabled(not running)
        self.infinite_loop_cb.setEnabled(not running)
        if running:
            self.loop_interval_spin.setEnabled(False)
        else:
            self.loop_interval_spin.setEnabled(self.infinite_loop_cb.isChecked())

        # Khóa/mở các nút tác vụ trên Tab Dữ liệu cào & Lịch sử phân tích
        if hasattr(self, 'btn_delete_all_history'):
            self.btn_delete_all_history.setEnabled(not running)
        if hasattr(self, 'btn_update_24h_comments'):
            self.btn_update_24h_comments.setEnabled(not running)
            if running:
                self.btn_update_24h_comments.setText("⏳ Đang cập nhật bình luận...")
            else:
                self.btn_update_24h_comments.setText("⏱️ Cập nhật bình luận 24h vừa qua")
        if hasattr(self, 'btn_delete_all_ai'):
            self.btn_delete_all_ai.setEnabled(not running)

        if running:
            if hasattr(self, 'btn_delete_selected_history'):
                self.btn_delete_selected_history.setEnabled(False)
            if hasattr(self, 'btn_update_selected_comments'):
                self.btn_update_selected_comments.setEnabled(False)
            if hasattr(self, 'btn_delete_selected_ai'):
                self.btn_delete_selected_ai.setEnabled(False)
        else:
            self.update_history_buttons_state()
            self.update_ai_buttons_state()

    def stop_scraping(self):
        if self.scraper_thread and self.scraper_thread.isRunning():
            self.stop_btn.setEnabled(False)
            self.log("🛑 Đang gửi yêu cầu dừng quét...")
            self.scraper_thread.stop()
        if hasattr(self, 'comment_update_worker') and self.comment_update_worker and self.comment_update_worker.isRunning():
            self.stop_btn.setEnabled(False)
            self.log("🛑 Đang gửi yêu cầu dừng cập nhật bình luận...")
            self.comment_update_worker.stop()

    def scraping_finished(self, success, message):
        self.set_scraping_state(running=False)
        self.progress_bar.setVisible(False)

        if success:
            self.log(f"✅ {message}")
            QMessageBox.information(self, "Thông báo", message)
        else:
            self.log(f"❌ {message}")
            QMessageBox.critical(self, "Lỗi", message)

    def update_progress(self, current, total):
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))

    def open_log_viewer_dialog(self):
        """Mở cửa sổ phóng to xem toàn bộ log chi tiết"""
        if not hasattr(self, 'log_viewer_dialog') or self.log_viewer_dialog is None:
            self.log_viewer_dialog = LogViewerDialog(self.log_text.toPlainText(), parent=self)
            self.log_viewer_dialog.clear_requested.connect(self.clear_log)
        else:
            self.log_viewer_dialog.log_text.setPlainText(self.log_text.toPlainText())
            cursor = self.log_viewer_dialog.log_text.textCursor()
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self.log_viewer_dialog.log_text.setTextCursor(cursor)
        self.log_viewer_dialog.show()
        self.log_viewer_dialog.raise_()
        self.log_viewer_dialog.activateWindow()

    def log(self, message):
        self.log_text.append(message)
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        if hasattr(self, 'log_viewer_dialog') and self.log_viewer_dialog and self.log_viewer_dialog.isVisible():
            self.log_viewer_dialog.append_log(message)
        database.add_log(message, level="INFO", module="APP")

    def clear_log(self):
        self.log_text.clear()
        if hasattr(self, 'log_viewer_dialog') and self.log_viewer_dialog and self.log_viewer_dialog.isVisible():
            self.log_viewer_dialog.log_text.clear()


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    window = FacebookNotificationUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()


# Alias for clean architecture entry point
FacebookScraperApp = FacebookNotificationUI
