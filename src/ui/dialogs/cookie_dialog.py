import re
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QTextEdit, QCheckBox, QFrame, QMessageBox
)
from src.core.group_fetcher import parse_cookies_from_any


class CookieDialog(QDialog):
    """
    Dialog nhập và phân tích Cookie Facebook định dạng JSON từ extension (Cookie-Editor / J2Team).
    """
    def __init__(self, parent=None, current_cookies="", current_dtsg="", current_raw_json=""):
        super().__init__(parent)
        self.setWindowTitle("🔑 Cấu hình Authentication (Cookie JSON Facebook)")
        self.setFixedWidth(600)
        self.cookies_str = current_cookies or ""
        self.dtsg_str = current_dtsg or ""
        self.raw_json = current_raw_json or ""  # JSON gốc user nhập
        self.fetch_groups_requested = False

        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Instructions banner
        desc = QLabel(
            "<b>📌 Hướng dẫn lấy Cookie JSON bằng extension Cookie-Editor:</b><br>"
            "<span style='color: #334155; font-size: 11px;'>"
            "1. Cài đặt tiện ích <b>Cookie-Editor</b> (hoặc <b>J2Team Cookies</b>) trên trình duyệt.<br>"
            "2. Mở tab Facebook (<code>https://www.facebook.com</code>) và đăng nhập tài khoản.<br>"
            "3. Bấm vào icon <b>Cookie-Editor</b> trên thanh tiện ích ➔ Chọn <b>Export</b> ➔ Chọn <b>Export as JSON</b>.<br>"
            "4. Dán nội dung JSON đã sao chép vào ô bên dưới rồi bấm <b>Lưu cấu hình</b>.</span>"
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("background-color: #F1F5F9; border: 1px solid #CBD5E1; padding: 10px 14px; border-radius: 6px; font-size: 12px; line-height: 1.4;")
        layout.addWidget(desc)

        self.cookie_input = QTextEdit()
        self.cookie_input.setPlaceholderText(
            "Dán chuỗi JSON Cookies từ extension vào đây (bắt đầu bằng [ hoặc {), ví dụ:\n"
            "[\n"
            '  {"name": "c_user", "value": "1000123456789"},\n'
            '  {"name": "xs", "value": "2%3Aabc...%3A2%3A123"},\n'
            '  {"name": "datr", "value": "xyz..."}\n'
            "]\n\n"
            "(Để xóa sạch Cookie đã lưu: Xóa trắng ô này rồi bấm 'Lưu cấu hình')"
        )
        self.cookie_input.setMinimumHeight(130)
        self.cookie_input.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        if self.raw_json:
            self.cookie_input.setPlainText(self.raw_json)
        elif self.cookies_str:
            self.cookie_input.setPlainText(self.cookies_str)
        layout.addWidget(self.cookie_input)

        # Token input
        dtsg_layout = QHBoxLayout()
        dtsg_lbl = QLabel("Token fb_dtsg (tùy chọn):")
        dtsg_lbl.setStyleSheet("font-size: 12px; font-weight: 500;")
        dtsg_layout.addWidget(dtsg_lbl)

        self.dtsg_input = QLineEdit()
        self.dtsg_input.setPlaceholderText("NAc... (tùy chọn, hệ thống tự động bóc tách nếu để trống)")
        self.dtsg_input.setText(self.dtsg_str)
        self.dtsg_input.setStyleSheet("font-size: 11px;")
        dtsg_layout.addWidget(self.dtsg_input, stretch=1)
        layout.addLayout(dtsg_layout)

        # Parse button
        self.parse_btn = QPushButton("🔍 Phân tích JSON Cookie (Parse)")
        self.parse_btn.setStyleSheet("""
            QPushButton {
                background-color: #7C3AED;
                color: white;
                font-weight: bold;
                padding: 7px 16px;
                border-radius: 5px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #6D28D9; }
        """)
        self.parse_btn.clicked.connect(self.on_parse_clicked)
        layout.addWidget(self.parse_btn)

        # Status Label
        self.status_label = QLabel("")
        self.status_label.setWordWrap(True)
        self.status_label.setStyleSheet("font-size: 11px; padding: 3px;")
        layout.addWidget(self.status_label)

        # Auto fetch checkbox
        self.auto_fetch_cb = QCheckBox("🌐 Tự động tải danh sách nhóm Facebook sau khi lưu")
        self.auto_fetch_cb.setChecked(True)
        self.auto_fetch_cb.setStyleSheet("font-size: 12px; color: #1E3A8A; font-weight: 500; margin-top: 4px;")
        layout.addWidget(self.auto_fetch_cb)

        self.use_browser_cb = QCheckBox("🚀 Sử dụng Trình duyệt tự động gắn Cookie để cuộn lấy 100% nhóm")
        self.use_browser_cb.setChecked(False)
        self.use_browser_cb.setStyleSheet("font-size: 12px; color: #4338CA; font-weight: 500;")
        layout.addWidget(self.use_browser_cb)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("color: #E2E8F0; margin: 4px 0;")
        layout.addWidget(divider)

        # Buttons
        btns_layout = QHBoxLayout()
        btns_layout.addStretch()

        cancel_btn = QPushButton("Hủy")
        cancel_btn.setStyleSheet("padding: 6px 14px; font-size: 12px;")
        cancel_btn.clicked.connect(self.reject)
        btns_layout.addWidget(cancel_btn)

        self.ok_btn = QPushButton("💾 Lưu cấu hình")
        self.ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                padding: 6px 18px;
                border-radius: 5px;
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
            self.status_label.setText("⚠️ Vui lòng dán chuỗi JSON Cookie từ extension trước.")
            self.status_label.setStyleSheet("color: #D97706; font-size: 11px; font-weight: bold;")
            return

        cleaned_text = raw_text
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned_text)
            cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

        if not (cleaned_text.startswith("[") or cleaned_text.startswith("{")):
            self.status_label.setText("❌ Nội dung không phải định dạng JSON (phải bắt đầu bằng [ hoặc {). Hãy mở Cookie-Editor ➔ Export as JSON.")
            self.status_label.setStyleSheet("color: #DC2626; font-size: 11px; font-weight: bold;")
            return

        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(raw_text)
        if not cookies_dict:
            self.status_label.setText("❌ Nội dung dán vào không phải JSON Cookie hợp lệ. Vui lòng mở Cookie-Editor ➔ Export as JSON rồi dán lại.")
            self.status_label.setStyleSheet("color: #DC2626; font-size: 11px; font-weight: bold;")
            return

        self.cookies_str = cookie_str
        if fb_dtsg:
            self.dtsg_str = fb_dtsg
            self.dtsg_input.setText(fb_dtsg)

        c_user = cookies_dict.get("c_user", "")
        xs = cookies_dict.get("xs", "")
        has_session = bool(c_user and xs)

        if has_session:
            status_text = (
                f"✅ Nhận diện thành công JSON Cookie: {len(cookies_dict)} cookies "
                f"(UID: {c_user}) | Session xs: ✓"
                f"{' | Token fb_dtsg: ✓' if self.dtsg_str else ''}"
            )
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("color: #059669; font-size: 11px; font-weight: bold;")
        else:
            status_text = (
                f"⚠️ Đã đọc được {len(cookies_dict)} cookies nhưng thiếu UID (c_user) hoặc Session (xs). "
                f"Hãy đảm bảo bạn đã đăng nhập Facebook trước khi Export JSON từ extension."
            )
            self.status_label.setText(status_text)
            self.status_label.setStyleSheet("color: #D97706; font-size: 11px; font-weight: bold;")

    def on_ok_clicked(self):
        raw_text = self.cookie_input.toPlainText().strip()
        if not raw_text:
            # Người dùng xóa trắng ô cookie -> reset hoàn toàn về rỗng
            self.cookies_str = ""
            self.raw_json = ""
            self.dtsg_str = self.dtsg_input.text().strip()
            self.accept()
            return

        # Kiểm tra bắt buộc phải là định dạng JSON
        cleaned_text = raw_text
        if cleaned_text.startswith("```"):
            cleaned_text = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned_text)
            cleaned_text = re.sub(r"\s*```$", "", cleaned_text).strip()

        if not (cleaned_text.startswith("[") or cleaned_text.startswith("{")):
            QMessageBox.warning(
                self,
                "Định dạng Cookie không hợp lệ",
                "⚠️ Nội dung nhập vào KHÔNG PHẢI định dạng JSON.\n\n"
                "Để đảm bảo chương trình hoạt động chính xác và không bị lỗi:\n"
                "1. Vui lòng cài tiện ích Cookie-Editor (hoặc J2Team) trên trình duyệt.\n"
                "2. Mở tab Facebook và đăng nhập tài khoản.\n"
                "3. Bấm Export ➔ Chọn 'Export as JSON' ➔ Dán lại vào đây."
            )
            return

        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(raw_text)
        if not cookies_dict:
            QMessageBox.warning(
                self,
                "Lỗi phân tích JSON Cookie",
                "❌ Không thể phân tích dữ liệu JSON này thành danh sách Cookies Facebook hợp lệ.\n\n"
                "Vui lòng kiểm tra lại nội dung JSON đã sao chép từ tiện ích mở rộng."
            )
            return

        self.cookies_str = cookie_str
        self.raw_json = raw_text  # Lưu JSON gốc
        if self.dtsg_input.text().strip():
            self.dtsg_str = self.dtsg_input.text().strip()
        elif fb_dtsg:
            self.dtsg_str = fb_dtsg
        else:
            self.dtsg_str = ""

        self.accept()

    def get_data(self):
        return {
            "cookie_string": self.cookies_str,
            "fb_dtsg": self.dtsg_str
        }

    def get_cookies(self):
        return self.cookies_str

    def get_raw_json(self):
        return self.raw_json

    def get_dtsg(self):
        return self.dtsg_str

    def should_fetch_groups(self) -> bool:
        return self.auto_fetch_cb.isChecked()

    def should_use_browser(self) -> bool:
        return self.use_browser_cb.isChecked()
