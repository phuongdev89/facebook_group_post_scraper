from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextBrowser, QDialogButtonBox)
from PyQt6.QtCore import Qt


class TelegramGuideDialog(QDialog):
    """
    Hộp thoại hướng dẫn chi tiết cách lấy Telegram Bot Token và Chat ID.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📖 Hướng dẫn lấy Telegram Bot Token & Chat ID")
        self.setMinimumSize(560, 480)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("📌 Hướng dẫn kết nối Telegram Bot")
        header.setStyleSheet("font-size: 15px; font-weight: bold; color: #1E3A8A;")
        layout.addWidget(header)

        browser = QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("""
            QTextBrowser {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 6px;
                padding: 10px;
                font-size: 13px;
                line-height: 1.5;
            }
        """)

        html_content = """
        <div style="font-family: Arial, sans-serif; color: #1E293B;">
            <h3 style="color: #2563EB; margin-top: 0;">1. Cách lấy Bot Token (qua @BotFather):</h3>
            <ol style="margin-left: -15px;">
                <li>Mở ứng dụng Telegram, tìm kiếm <b>@BotFather</b> (có tích xanh chính chủ).</li>
                <li>Bấm <b>Start</b> (hoặc gửi lệnh <code>/newbot</code>).</li>
                <li>Nhập <b>Tên hiển thị</b> cho bot (VD: <i>Facebook Notification Bot</i>).</li>
                <li>Nhập <b>Username</b> cho bot (phải kết thúc bằng chữ <code>bot</code>, VD: <i>my_fb_lead_bot</i>).</li>
                <li>BotFather sẽ gửi lại tin nhắn chúc mừng kèm chuỗi <b>HTTP API Token</b> có dạng:<br>
                    <code style="background-color: #E2E8F0; color: #DC2626; padding: 2px 4px; border-radius: 3px;">
                    1234567890:ABC-DEF1234ghIkl-zyx57W2v1u123ew11
                    </code>
                </li>
                <li>Copy toàn bộ chuỗi token này và dán vào ô <b>Bot Token</b>.</li>
            </ol>

            <hr style="border: 0; border-top: 1px solid #CBD5E1; margin: 12px 0;">

            <h3 style="color: #2563EB; margin-top: 0;">2. Cách lấy Chat ID:</h3>
            <p><b>A. Nhận tin nhắn cá nhân (1-1):</b></p>
            <ul style="margin-left: -15px;">
                <li>Tìm bot <b>@userinfobot</b> hoặc <b>@myidbot</b> trên Telegram, bấm <b>Start</b>.</li>
                <li>Bot sẽ gửi lại số <b>Id</b> của bạn (VD: <code>987654321</code>). Copy số này dán vào ô <b>Chat ID</b>.</li>
            </ul>

            <p><b>B. Nhận tin nhắn vào Nhóm / Group:</b></p>
            <ul style="margin-left: -15px;">
                <li>Thêm bot vừa tạo vào Nhóm chat của bạn và phong làm <b>Quản trị viên (Admin)</b>.</li>
                <li>Thêm bot <b>@RawDataBot</b> hoặc <b>@getmyid_bot</b> vào nhóm để xem ID của nhóm.</li>
                <li>ID của nhóm thường có dấu trừ ở đầu (VD: <code>-1001234567890</code> hoặc <code>-123456789</code>).</li>
            </ul>

            <hr style="border: 0; border-top: 1px solid #CBD5E1; margin: 12px 0;">

            <div style="background-color: #FEF3C7; border-left: 4px solid #F59E0B; padding: 8px 12px; border-radius: 4px;">
                <b style="color: #B45309;">⚠️ LƯU Ý QUAN TRỌNG NHẤT:</b><br>
                Trước khi kiểm tra kết nối hoặc nhận thông báo, bạn <b>BẮT BUỘC</b> phải mở chat riêng với Bot của bạn và bấm <b>/start</b> (hoặc gửi 1 tin nhắn bất kỳ cho Bot). Telegram sẽ chặn không cho bot chủ động gửi tin nếu bạn chưa từng bấm Start với nó!
            </div>
        </div>
        """
        browser.setHtml(html_content)
        layout.addWidget(browser)

        btn_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        btn_box.rejected.connect(self.accept)
        layout.addWidget(btn_box)
