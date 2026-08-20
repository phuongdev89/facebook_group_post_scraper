from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QDialogButtonBox, QCheckBox, QFrame
)
from src.core.group_fetcher import parse_cookies_from_any


class CookieDialog(QDialog):
    """Dialog nhập chuỗi Cookie / cURL / Token và tùy chọn tự động tải nhóm Facebook"""
    def __init__(self, parent=None, current_cookies="", current_dtsg=""):
        super().__init__(parent)
        self.setWindowTitle("🔑 Cấu hình Authentication (Cookie & Token Facebook)")
        self.setFixedWidth(560)
        self.cookies_str = current_cookies
        self.dtsg_str = current_dtsg
        self.fetch_groups_requested = False

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Instructions
        desc = QLabel(
            "<b>Dán chuỗi Cookie hoặc lệnh cURL từ trình duyệt:</b><br>"
            "<span style='color: #4B5563; font-size: 11px;'>"
            "• Hỗ trợ dạng Cookie thô: <code>c_user=...; xs=...; datr=...</code><br>"
            "• Hỗ trợ lệnh cURL (DevTools ➔ Copy as cURL)<br>"
            "• Hệ thống tự động nhận diện và trích xuất Cookie & Token fb_dtsg</span>"
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText(
            "c_user=123456789; xs=2%3A...; datr=...;\n"
            "hoặc dán lệnh cURL: curl 'https://www.facebook.com/api/graphql/' -b '...' --data-raw 'fb_dtsg=...'"
        )
        self.cookie_input.setMinimumHeight(110)
        self.cookie_input.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        if self.cookies_str:
            self.cookie_input.setPlainText(self.cookies_str)
        layout.addWidget(self.cookie_input)

        # Token input
        dtsg_layout = QHBoxLayout()
        dtsg_lbl = QLabel("Token fb_dtsg (tùy chọn):")
        dtsg_lbl.setStyleSheet("font-size: 12px;")
        dtsg_layout.addWidget(dtsg_lbl)

        self.dtsg_input = QLineEdit()
        self.dtsg_input.setPlaceholderText("NAc... (tự động điền nếu có trong cURL)")
        self.dtsg_input.setText(self.dtsg_str)
        self.dtsg_input.setStyleSheet("font-size: 11px;")
        dtsg_layout.addWidget(self.dtsg_input, stretch=1)
        layout.addLayout(dtsg_layout)

        # Parse button
        self.parse_btn = QPushButton("🔍 Phân tích Cookie (Parse)")
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-weight: bold;
                padding: 6px 14px;
                border-radius: 4px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.parse_btn.clicked.connect(self.on_parse_clicked)
        layout.addWidget(self.parse_btn)

        # Status Label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 11px; padding: 2px;")
        layout.addWidget(self.status_label)

        # Checkbox auto fetch groups
        self.auto_fetch_cb = QCheckBox("🌐 Tự động tải danh sách nhóm Facebook sau khi lưu")
        self.auto_fetch_cb.setChecked(True)
        self.auto_fetch_cb.setStyleSheet("font-size: 12px; color: #1E3A8A; font-weight: 500;")
        layout.addWidget(self.auto_fetch_cb)

        # Buttons
        btns_layout = QHBoxLayout()
        btns_layout.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(cancel_btn)

        self.ok_btn = QPushButton("💾 Lưu cấu hình")
        self.ok_btn.setStyleSheet("""
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
        self.ok_btn.clicked.connect(self.on_ok_clicked)
        btns_layout.addWidget(self.ok_btn)

        layout.addLayout(btns_layout)

    def on_parse_clicked(self):
        raw_text = self.cookie_input.toPlainText().strip()
        if not raw_text:
            self.status_label.setText("⚠️ Vui lòng dán chuỗi Cookie hoặc lệnh cURL trước.")
            self.status_label.setStyleSheet("color: #D97706; font-size: 11px;")
            return

        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(raw_text)
        if not cookies_dict:
            self.status_label.setText("❌ Không tìm thấy Cookie hợp lệ trong nội dung đã dán.")
            self.status_label.setStyleSheet("color: #DC2626; font-size: 11px;")
            return

        self.cookies_str = cookie_str
        if fb_dtsg:
            self.dtsg_str = fb_dtsg
            self.dtsg_input.setText(fb_dtsg)

        c_user = cookies_dict.get("c_user", "")
        self.status_label.setText(
            f"✅ Parse thành công: {len(cookies_dict)} cookies "
            f"(UID: {c_user if c_user else 'OK'})"
            f"{' | fb_dtsg: ✓' if self.dtsg_str else ''}"
        )
        self.status_label.setStyleSheet("color: #059669; font-size: 11px; font-weight: bold;")

    def on_ok_clicked(self):
        # Auto parse if not parsed yet
        raw_text = self.cookie_input.toPlainText().strip()
        if raw_text:
            cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(raw_text)
            if cookie_str:
                self.cookies_str = cookie_str
            if fb_dtsg and not self.dtsg_input.text().strip():
                self.dtsg_str = fb_dtsg

        if self.dtsg_input.text().strip():
            self.dtsg_str = self.dtsg_input.text().strip()

        self.accept()

    def get_data(self):
        return {
            "cookie_string": self.cookies_str,
            "fb_dtsg": self.dtsg_str
        }

    def get_cookies(self):
        return self.cookies_str

    def get_dtsg(self):
        return self.dtsg_str

    def should_fetch_groups(self) -> bool:
        return self.auto_fetch_cb.isChecked()
