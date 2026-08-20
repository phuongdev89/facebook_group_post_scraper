from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QLineEdit, QPushButton, QFrame, QScrollArea)
from PyQt6.QtCore import Qt, pyqtSignal
from src.core.ai_analyzer import is_thinking_model


class TagLabel(QFrame):
    removed = pyqtSignal(str)
    
    def __init__(self, text: str, parent=None, is_strikethrough: bool = False, tooltip: str = ""):
        super().__init__(parent)
        self.text = text
        self.is_strikethrough = is_strikethrough

        if is_strikethrough:
            self.setStyleSheet("""
                TagLabel {
                    background-color: #F3F4F6;
                    border: 1px dashed #D1D5DB;
                    border-radius: 12px;
                    padding: 2px 8px;
                }
            """)
        else:
            self.setStyleSheet("""
                TagLabel {
                    background-color: #E0E7FF;
                    border: 1px solid #C7D2FE;
                    border-radius: 12px;
                    padding: 2px 8px;
                }
            """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)
        
        lbl = QLabel()
        if is_strikethrough:
            lbl.setText(f"<s>{text}</s> <span style='color: #EF4444; font-size: 10px; font-weight: bold;'>[Loại trừ]</span>")
            lbl.setStyleSheet("color: #9CA3AF; font-weight: 500; font-size: 11px;")
        else:
            lbl.setText(f"{text} <span style='color: #10B981; font-size: 10px; font-weight: bold;'>✓</span>")
            lbl.setStyleSheet("color: #3730A3; font-weight: 500; font-size: 11px;")
        
        if tooltip:
            lbl.setToolTip(tooltip)
            self.setToolTip(tooltip)

        layout.addWidget(lbl)
        
        btn = QPushButton("×")
        btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: #6B7280;
                font-weight: bold;
                font-size: 13px;
                border: none;
                padding: 0;
            }
            QPushButton:hover { color: #DC2626; }
        """)
        btn.setFixedSize(14, 14)
        btn.clicked.connect(lambda: self.removed.emit(self.text))
        layout.addWidget(btn)


class TagWidget(QWidget):
    tags_changed = pyqtSignal(list)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []
        self.init_ui()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)
        
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(4)
        
        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Nhập từ khóa rồi Enter hoặc click '+'...")
        self.input_field.returnPressed.connect(self.add_tag_from_input)
        input_layout.addWidget(self.input_field)
        
        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        add_btn.clicked.connect(self.add_tag_from_input)
        input_layout.addWidget(add_btn)
        
        main_layout.addLayout(input_layout)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMaximumHeight(80)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #E5E7EB; border-radius: 4px; background: #FAFAFA; }")
        
        self.tags_container = QWidget()
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(4, 4, 4, 4)
        self.tags_layout.setSpacing(6)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        
        self.scroll_area.setWidget(self.tags_container)
        main_layout.addWidget(self.scroll_area)
        
    def add_tag_from_input(self):
        text = self.input_field.text().strip()
        if text:
            for item in text.split(","):
                val = item.strip()
                if val and val.lower() not in [t.lower() for t in self.tags]:
                    self.tags.append(val)
            self.input_field.clear()
            self.render_tags()
            self.tags_changed.emit(self.tags)
            
    def add_tag(self, tag):
        tag = tag.strip()
        if tag and tag.lower() not in [t.lower() for t in self.tags]:
            self.tags.append(tag)
            self.render_tags()
            self.tags_changed.emit(self.tags)
            
    def remove_tag(self, tag):
        self.tags = [t for t in self.tags if t != tag]
        self.render_tags()
        self.tags_changed.emit(self.tags)
        
    def set_tags(self, tags: list):
        self.tags = [t.strip() for t in tags if t.strip()]
        self.render_tags()
        self.tags_changed.emit(self.tags)
        
    def get_tags(self) -> list:
        return list(self.tags)
        
    def render_tags(self):
        while self.tags_layout.count():
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
        for tag in self.tags:
            tag_label = TagLabel(tag)
            tag_label.removed.connect(self.remove_tag)
            self.tags_layout.addWidget(tag_label)


class ModelTagWidget(QWidget):
    """
    Widget chuyên dụng hiển thị danh sách Model AI:
    - Quản lý trạng thái từng model: name, is_valid, is_thinking, status, message, enabled.
    - Model không trả về JSON thuần hoặc là Thinking model hoặc lỗi sẽ được hiển thị GẠCH NGANG (strikethrough).
    - Cung cấp get_active_models() để chỉ lấy các model hợp lệ có thể sử dụng khi cào.
    - Cung cấp get_all_models_data() để lưu đầy đủ metadata vào SQLite settings.
    """
    models_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.models_data = []  # list[dict]: [{"name": "...", "is_valid": bool, "is_thinking": bool, "status": "...", "message": "...", "enabled": bool}]
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(4)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(4)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("Nhập tên model AI (VD: gpt-4o-mini, deepseek-chat) rồi Enter...")
        self.input_field.returnPressed.connect(self.add_model_from_input)
        input_layout.addWidget(self.input_field)

        add_btn = QPushButton("+")
        add_btn.setFixedSize(28, 28)
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        add_btn.clicked.connect(self.add_model_from_input)
        input_layout.addWidget(add_btn)

        main_layout.addLayout(input_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(55)
        self.scroll_area.setMaximumHeight(85)
        self.scroll_area.setStyleSheet("QScrollArea { border: 1px solid #E5E7EB; border-radius: 4px; background: #FAFAFA; }")

        self.tags_container = QWidget()
        self.tags_layout = QHBoxLayout(self.tags_container)
        self.tags_layout.setContentsMargins(4, 4, 4, 4)
        self.tags_layout.setSpacing(6)
        self.tags_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.scroll_area.setWidget(self.tags_container)
        main_layout.addWidget(self.scroll_area)

    def add_model_from_input(self):
        text = self.input_field.text().strip()
        if text:
            for item in text.split(","):
                val = item.strip()
                if val:
                    self.add_model(val)
            self.input_field.clear()

    def add_model(self, name: str, is_valid: bool = None, is_thinking: bool = None, status: str = "", message: str = ""):
        name = name.strip()
        if not name:
            return

        # Kiểm tra trùng lặp
        for m in self.models_data:
            if m["name"].lower() == name.lower():
                return

        thinking_check = is_thinking if is_thinking is not None else is_thinking_model(name)
        valid_check = is_valid if is_valid is not None else (not thinking_check)

        if not message:
            if thinking_check:
                message = "Model tư duy (Thinking) — Tự động gạch ngang loại trừ"
            else:
                message = "Model hoạt động bình thường"

        self.models_data.append({
            "name": name,
            "is_valid": valid_check,
            "is_thinking": thinking_check,
            "status": status or ("thinking" if thinking_check else "ok"),
            "message": message,
            "enabled": valid_check
        })
        self.render_tags()
        self.models_changed.emit(self.get_active_models())

    def remove_model(self, name: str):
        self.models_data = [m for m in self.models_data if m["name"] != name]
        self.render_tags()
        self.models_changed.emit(self.get_active_models())

    def set_models_data(self, data: list):
        """
        Nạp danh sách model từ list[str] hoặc list[dict].
        """
        self.models_data = []
        for item in data:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
                if not name:
                    continue
                thinking = item.get("is_thinking", is_thinking_model(name))
                valid = item.get("is_valid", not thinking)
                enabled = item.get("enabled", valid)
                msg = item.get("message", "")
                self.models_data.append({
                    "name": name,
                    "is_valid": valid,
                    "is_thinking": thinking,
                    "status": item.get("status", "thinking" if thinking else "ok"),
                    "message": msg or ("Model tư duy (Thinking)" if thinking else "Sẵn sàng"),
                    "enabled": enabled
                })
            elif isinstance(item, str):
                name = item.strip()
                if not name:
                    continue
                thinking = is_thinking_model(name)
                self.models_data.append({
                    "name": name,
                    "is_valid": not thinking,
                    "is_thinking": thinking,
                    "status": "thinking" if thinking else "ok",
                    "message": "Model tư duy (Thinking)" if thinking else "Sẵn sàng",
                    "enabled": not thinking
                })
        self.render_tags()
        self.models_changed.emit(self.get_active_models())

    # Alias for compatibility with TagWidget
    def set_tags(self, tags: list):
        self.set_models_data(tags)

    def get_tags(self) -> list:
        return self.get_active_models()

    def get_active_models(self) -> list[str]:
        """Trả về danh sách tên model hợp lệ (không bị gạch ngang / không lỗi / không thinking)"""
        active = []
        for m in self.models_data:
            if m.get("is_valid", True) and not m.get("is_thinking", False) and m.get("enabled", True):
                active.append(m["name"])
        return active

    def get_all_models_data(self) -> list[dict]:
        """Trả về toàn bộ danh sách metadata model để lưu vào SQLite"""
        return list(self.models_data)

    def update_with_test_results(self, results: list[dict]):
        """
        Cập nhật lại trạng thái từng model sau khi chạy Test AI thực tế qua API.
        """
        res_map = {r["name"].lower(): r for r in results if "name" in r}
        for m in self.models_data:
            m_key = m["name"].lower()
            if m_key in res_map:
                r = res_map[m_key]
                m["is_valid"] = r.get("is_valid", False)
                m["is_thinking"] = r.get("is_thinking", False)
                m["status"] = r.get("status", "error")
                m["message"] = r.get("message", "")
                m["enabled"] = m["is_valid"]
        self.render_tags()
        self.models_changed.emit(self.get_active_models())

    def render_tags(self):
        while self.tags_layout.count():
            child = self.tags_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        for m in self.models_data:
            name = m.get("name", "")
            is_strikethrough = (not m.get("is_valid", True)) or m.get("is_thinking", False)
            tooltip = m.get("message", "")
            tag_label = TagLabel(text=name, is_strikethrough=is_strikethrough, tooltip=tooltip)
            tag_label.removed.connect(self.remove_model)
            self.tags_layout.addWidget(tag_label)

