from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QApplication, QMessageBox, QDialogButtonBox)
from PyQt6.QtCore import Qt


META_PROMPT_TEMPLATE = """Tôi đang sử dụng phần mềm quét bài viết & bình luận Facebook tự động để phát hiện các cơ hội kinh doanh và thông tin quan trọng.
Phần mềm này gửi dữ liệu bài viết (post_message) và bình luận (comments/replies) sang cho AI dưới dạng JSON và yêu cầu AI trả về kết quả ĐÚNG ĐỊNH DẠNG JSON sau:

{
  "should_notify": true/false (true nếu tìm thấy thông tin khớp nhu cầu cần thông báo, false nếu không),
  "target_name": "Tên sản phẩm / dịch vụ / khu vực phòng trọ / vị trí tuyển dụng / nhu cầu phát hiện",
  "price": "Giá bán / Tiền thuê hàng tháng / Mức lương / Ngân sách (hoặc 'Thỏa thuận / Không đề cập')",
  "actor_role": "Chủ bài đăng | Người bình luận | Cả chủ bài và bình luận | Không có (hoặc vai trò cụ thể: Chủ nhà / Nhà tuyển dụng / Người tìm việc...)",
  "matched_snippet": "Trích dẫn nguyên văn ngắn gọn câu nói chứng minh phát hiện",
  "reason": "Lý do ngắn gọn xác định vì sao khớp hoặc không khớp"
}

==================================================
[YÊU CẦU CỦA BẠN - HÃY SỬA ĐOẠN NÀY THEO Ý BẠN]:
- Tôi muốn AI tìm kiếm và phát hiện: [Ví dụ: Người cho thuê phòng trọ quanh Cầu Giấy / Người tuyển thợ điện nước / Người thanh lý laptop / Người cần tìm mua flycam...]
- Loại trừ các trường hợp: [Ví dụ: Bài quảng cáo dịch vụ vay tiền, việc làm lừa đảo, người chỉ xin tư vấn giá, bài spam...]
==================================================

Hãy viết lại cho tôi một bản SYSTEM PROMPT hoàn chỉnh, chi tiết, nghiêm ngặt bằng tiếng Việt, hướng dẫn AI đọc dữ liệu Facebook và chỉ trả về DUY NHẤT 1 JSON object theo định dạng trên (tuyệt đối không kèm văn bản giải thích bên ngoài JSON)."""



class PromptGuideDialog(QDialog):
    """
    Hộp thoại hướng dẫn người dùng cách tạo prompt mới bằng cách copy Meta-Prompt
    và gửi cho ChatGPT / Claude / Gemini / DeepSeek.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💡 Hướng dẫn tạo & tùy biến Prompt cho AI")
        self.setMinimumSize(600, 520)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        title = QLabel("✨ Cách tạo System Prompt mới theo đúng nhu cầu của bạn:")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1E3A8A;")
        layout.addWidget(title)

        steps_label = QLabel(
            "<b>1.</b> Bấm nút <b>'📋 Sao chép Mẫu gửi AI'</b> bên dưới.<br>"
            "<b>2.</b> Mở AI của bạn (<i>ChatGPT, Claude, Gemini, DeepSeek...</i>) và dán nội dung vào ô chat.<br>"
            "<b>3.</b> Tìm đến đoạn <b>[YÊU CẦU CỦA BẠN]</b> và viết nội dung bạn mong muốn vào đó rồi gửi cho AI.<br>"
            "<b>4.</b> AI của bạn sẽ gửi về một System Prompt mới chuẩn JSON.<br>"
            "<b>5.</b> Copy toàn bộ Prompt mới đó và dán vào ô <b>System Prompt</b> trong phần mềm này."
        )
        steps_label.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.5; background: #F1F5F9; padding: 10px; border-radius: 6px;")
        layout.addWidget(steps_label)

        layout.addWidget(QLabel("<b>Nội dung Mẫu gửi AI (Meta-Prompt):</b>"))

        self.prompt_text = QTextEdit()
        self.prompt_text.setPlainText(META_PROMPT_TEMPLATE)
        self.prompt_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background-color: #FAFAFA; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.prompt_text)

        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("📋 Sao chép Mẫu gửi AI vào Clipboard")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.copy_btn.clicked.connect(self.copy_template)
        btn_layout.addWidget(self.copy_btn)

        btn_layout.addStretch()

        close_btn = QPushButton("Đóng")
        close_btn.setStyleSheet("padding: 8px 16px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def copy_template(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.prompt_text.toPlainText())
        self.copy_btn.setText("✅ Đã sao chép vào Clipboard!")
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 16px;
                border-radius: 4px;
            }
        """)
        QMessageBox.information(
            self,
            "Đã sao chép",
            "✅ Đã sao chép Mẫu gửi AI vào bộ nhớ tạm (Clipboard)!\n\n"
            "Bây giờ bạn hãy mở ChatGPT / Claude / Gemini / DeepSeek, dán mẫu này vào và chỉnh sửa mục [YÊU CẦU CỦA BẠN]."
        )
