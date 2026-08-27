from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QApplication, QMessageBox, QDialogButtonBox)
from PyQt6.QtCore import Qt
from src.utils.i18n import tr, get_current_language


META_PROMPT_TEMPLATE_VI = """Tôi đang sử dụng phần mềm quét bài viết & bình luận Facebook tự động để phát hiện các cơ hội kinh doanh và thông tin quan trọng.
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


META_PROMPT_TEMPLATE_EN = """I am using an automated Facebook post & comment scraper system to discover business opportunities and leads.
The scraper passes post and comment data to AI in JSON format and requires the AI to return results in the EXACT following JSON schema:

{
  "should_notify": true/false (true if target lead/opportunity is detected, false otherwise),
  "target_name": "Name of product / service / rental area / job vacancy / target demand",
  "price": "Selling price / Monthly rent / Salary / Budget (or 'Negotiable / Not mentioned')",
  "actor_role": "Post Author | Commenter | Both Author and Commenter | None (or specific role)",
  "matched_snippet": "Verbatim quote from post/comment that proves the match",
  "reason": "Concise rationale explaining why this matches or does not match"
}

==================================================
[YOUR SPECIFIC REQUIREMENTS - EDIT THIS SECTION]:
- I want AI to detect and notify: [e.g. People looking to buy second-hand cameras / Room for rent in downtown / Hiring remote developers...]
- Exclude false positives: [e.g. Spam, scam loan advertisements, people just asking for price consultations...]
==================================================

Please rewrite a complete, detailed, and strict SYSTEM PROMPT in English guiding the AI to analyze Facebook data and return ONLY ONE JSON object matching the schema above (strictly no surrounding markdown explanations)."""



class PromptGuideDialog(QDialog):
    """
    Hộp thoại hướng dẫn người dùng cách tạo prompt mới bằng cách copy Meta-Prompt
    và gửi cho ChatGPT / Claude / Gemini / DeepSeek.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("💡 " + tr("prompt_guide_title"))
        self.setMinimumSize(600, 520)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        is_en = (get_current_language() == "en")

        title = QLabel("✨ " + ("How to create a custom System Prompt tailored for your needs:" if is_en else "Cách tạo System Prompt mới theo đúng nhu cầu của bạn:"))
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1E3A8A;")
        layout.addWidget(title)

        steps_html = (
            "<b>1.</b> Click <b>'📋 Copy Meta-Prompt'</b> button below.<br>"
            "<b>2.</b> Open your LLM of choice (<i>ChatGPT, Claude, Gemini, DeepSeek...</i>) and paste the template into the chat box.<br>"
            "<b>3.</b> Find the section <b>[YOUR SPECIFIC REQUIREMENTS]</b> and describe your criteria.<br>"
            "<b>4.</b> Your AI will generate a tailored JSON-compliant System Prompt.<br>"
            "<b>5.</b> Copy that generated prompt and paste into the <b>System Prompt</b> field in this software."
            if is_en else
            "<b>1.</b> Bấm nút <b>'📋 Sao chép Mẫu gửi AI'</b> bên dưới.<br>"
            "<b>2.</b> Mở AI của bạn (<i>ChatGPT, Claude, Gemini, DeepSeek...</i>) và dán nội dung vào ô chat.<br>"
            "<b>3.</b> Tìm đến đoạn <b>[YÊU CẦU CỦA BẠN]</b> và viết nội dung bạn mong muốn vào đó rồi gửi cho AI.<br>"
            "<b>4.</b> AI của bạn sẽ gửi về một System Prompt mới chuẩn JSON.<br>"
            "<b>5.</b> Copy toàn bộ Prompt mới đó và dán vào ô <b>System Prompt</b> trong phần mềm này."
        )
        steps_label = QLabel(steps_html)
        steps_label.setStyleSheet("font-size: 12px; color: #334155; line-height: 1.5; background: #F1F5F9; padding: 10px; border-radius: 6px;")
        layout.addWidget(steps_label)

        layout.addWidget(QLabel("<b>" + ("Meta-Prompt Template Content:" if is_en else "Nội dung Mẫu gửi AI (Meta-Prompt):") + "</b>"))

        self.prompt_text = QTextEdit()
        self.prompt_text.setPlainText(META_PROMPT_TEMPLATE_EN if is_en else META_PROMPT_TEMPLATE_VI)
        self.prompt_text.setStyleSheet("font-family: Consolas, monospace; font-size: 12px; background-color: #FAFAFA; border: 1px solid #CBD5E1; border-radius: 4px; padding: 6px;")
        layout.addWidget(self.prompt_text)

        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("📋 " + ("Copy Meta-Prompt to Clipboard" if is_en else "Sao chép Mẫu gửi AI vào Clipboard"))
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

        close_btn = QPushButton(tr("btn_close"))
        close_btn.setStyleSheet("padding: 8px 16px;")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def copy_template(self):
        is_en = (get_current_language() == "en")
        clipboard = QApplication.clipboard()
        clipboard.setText(self.prompt_text.toPlainText())
        self.copy_btn.setText("✅ " + ("Copied to Clipboard!" if is_en else "Đã sao chép vào Clipboard!"))
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
            "Copied" if is_en else "Đã sao chép",
            "✅ Meta-Prompt copied to clipboard!\n\nOpen ChatGPT / Claude / Gemini / DeepSeek, paste template and fill [YOUR REQUIREMENTS]."
            if is_en else
            "✅ Đã sao chép Mẫu gửi AI vào bộ nhớ tạm (Clipboard)!\n\n"
            "Bây giờ bạn hãy mở ChatGPT / Claude / Gemini / DeepSeek, dán mẫu này vào và chỉnh sửa mục [YÊU CẦU CỦA BẠN]."
        )
