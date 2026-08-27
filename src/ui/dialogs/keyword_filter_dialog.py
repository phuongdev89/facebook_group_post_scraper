"""
Keyword Filter Dialog - Cửa sổ phóng to cấu hình bộ lọc từ khóa & biểu thức logic
Hỗ trợ:
- Dựng điều kiện trực quan (Visual Rule Builder)
- Tự nhập biểu thức (Raw Expression)
- Diễn giải ý nghĩa bộ lọc bằng tiếng Việt thời gian thực
"""

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt
from src.ui.components.keyword_filter_widget import KeywordFilterWidget
from src.utils.keyword_engine import explain_expression, validate_expression


class KeywordFilterDialog(QDialog):
    def __init__(self, initial_expression: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("🔍 Cấu hình Bộ lọc Từ khóa & Biểu thức Logic nâng cao")
        # Cho phép phóng to Max màn hình (Maximize button) và thu nhỏ
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.WindowMaximizeButtonHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(850, 580)
        self.setMinimumSize(680, 440)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.final_expression = initial_expression
        self.init_ui(initial_expression)

    def init_ui(self, initial_expr: str):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)

        # Header Info Banner
        info_banner = QFrame()
        info_banner.setStyleSheet("background-color: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px;")
        banner_layout = QVBoxLayout(info_banner)
        banner_layout.setContentsMargins(12, 10, 12, 10)
        banner_layout.setSpacing(4)

        banner_title = QLabel("<b>💡 Trình xây dựng biểu thức logic từ khóa</b>")
        banner_title.setStyleSheet("color: #1E40AF; font-size: 13px;")
        banner_layout.addWidget(banner_title)

        banner_desc = QLabel(
            "Bạn có thể chọn tạo điều kiện bằng giao diện trực quan theo từng khối/nhóm, hoặc tự gõ biểu thức tự do. "
            "Hệ thống sẽ tự động chuyển đổi qua lại giữa 2 chế độ và diễn giải ý nghĩa bên dưới."
        )
        banner_desc.setStyleSheet("color: #3B82F6; font-size: 11px;")
        banner_desc.setWordWrap(True)
        banner_layout.addWidget(banner_desc)
        main_layout.addWidget(info_banner)

        # Filter Widget
        self.filter_widget = KeywordFilterWidget(self)
        self.filter_widget.set_expression(initial_expr)
        self.filter_widget.expression_changed.connect(self.on_expression_updated)
        main_layout.addWidget(self.filter_widget, stretch=1)

        # Live Explanation Card
        self.explainer_card = QFrame()
        self.explainer_card.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px;")
        explainer_layout = QVBoxLayout(self.explainer_card)
        explainer_layout.setContentsMargins(12, 10, 12, 10)
        explainer_layout.setSpacing(4)

        explainer_title = QLabel("<b>🗣️ Ý nghĩa bộ lọc (Giải thích bằng tiếng Việt):</b>")
        explainer_title.setStyleSheet("color: #334155; font-size: 11px;")
        explainer_layout.addWidget(explainer_title)

        self.explanation_label = QLabel(explain_expression(initial_expr))
        self.explanation_label.setStyleSheet("color: #0F172A; font-size: 12px; font-weight: 500;")
        self.explanation_label.setWordWrap(True)
        explainer_layout.addWidget(self.explanation_label)
        main_layout.addWidget(self.explainer_card)

        # Bottom Buttons (Apply / Cancel)
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.cancel_btn = QPushButton("Đóng")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: #F3F4F6;
                color: #374151;
                font-weight: 500;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.apply_btn = QPushButton("✅ Áp dụng & Lưu bộ lọc")
        self.apply_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 20px;
                border-radius: 6px;
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.apply_btn.clicked.connect(self.on_apply)
        btn_layout.addWidget(self.apply_btn)

        main_layout.addLayout(btn_layout)

    def on_expression_updated(self, expr: str):
        self.explanation_label.setText(explain_expression(expr))

    def on_apply(self):
        expr = self.filter_widget.get_expression()
        ok, msg = validate_expression(expr)
        if expr and not ok:
            QMessageBox.warning(self, "Cú pháp không hợp lệ", f"Biểu thức chưa hợp lệ:\n{msg}\n\nVui lòng kiểm tra lại trước khi áp dụng.")
            return

        self.final_expression = expr
        self.accept()

    def get_expression(self) -> str:
        return self.final_expression
