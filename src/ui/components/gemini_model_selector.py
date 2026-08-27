from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QCheckBox, QPushButton, QScrollArea, QFrame, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from src.core.ai_analyzer import DEFAULT_GEMINI_MODELS, fetch_gemini_models_from_api


from src.utils.i18n import tr, get_current_language


class FetchGeminiModelsWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)

    def __init__(self, api_key: str):
        super().__init__()
        self.api_key = api_key

    def run(self):
        ok, models, msg = fetch_gemini_models_from_api(self.api_key)
        self.finished_signal.emit(ok, models, msg)


class GeminiModelSelectorWidget(QWidget):
    """
    Widget hiển thị danh sách checkbox các model Gemini của Google AI Studio.
    Hỗ trợ tự động parse và cập nhật danh sách model từ API Key của người dùng.
    """
    models_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.models_list = DEFAULT_GEMINI_MODELS.copy()
        self.checkboxes: dict[str, QCheckBox] = {}
        self.selected_models: set[str] = {"gemini-2.0-flash", "gemini-2.5-flash", "gemini-1.5-flash"}
        self.fetch_worker = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()
        self.status_label = QLabel(f"✨ <b>{tr('model_sel_gemini_title')}</b>")
        self.status_label.setStyleSheet("color: #0369A1; font-size: 12px;")
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        self.btn_select_all = QPushButton(tr("btn_select_all"))
        self.btn_select_all.setStyleSheet("""
            QPushButton {
                background-color: #F0FDF4;
                color: #15803D;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 3px;
                border: 1px solid #BBF7D0;
            }
            QPushButton:hover { background-color: #DCFCE7; }
        """)
        self.btn_select_all.clicked.connect(self.select_all)
        header_layout.addWidget(self.btn_select_all)

        self.btn_refresh = QPushButton("🔄 " + ("Fetch Models" if get_current_language() == "en" else "Tải Models từ Key"))
        self.btn_refresh.setToolTip("Fetch all available Gemini models for your API Key" if get_current_language() == "en" else "Gửi yêu cầu tới Google AI Studio để tải toàn bộ model khả dụng cho API Key của bạn")
        self.btn_refresh.setStyleSheet("""
            QPushButton {
                background-color: #E0F2FE;
                color: #0284C7;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 8px;
                border-radius: 3px;
                border: 1px solid #BAE6FD;
            }
            QPushButton:hover { background-color: #BAE6FD; }
        """)
        header_layout.addWidget(self.btn_refresh)

        main_layout.addLayout(header_layout)

        # Scroll Area for Checkbox Grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(110)
        self.scroll_area.setMaximumHeight(170)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #BAE6FD;
                border-radius: 6px;
                background-color: #F8FAFC;
            }
        """)

        self.container_widget = QWidget()
        self.grid_layout = QGridLayout(self.container_widget)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container_widget)
        main_layout.addWidget(self.scroll_area)

        self.render_checkboxes()

    def retranslate_ui(self):
        """Retranslate dynamic labels and buttons"""
        if hasattr(self, 'status_label'):
            self.status_label.setText(f"✨ <b>{tr('model_sel_gemini_title')}</b>")
        if hasattr(self, 'btn_select_all'):
            self.btn_select_all.setText(tr("btn_select_all"))
        if hasattr(self, 'btn_refresh'):
            self.btn_refresh.setText("🔄 " + ("Fetch Models" if get_current_language() == "en" else "Tải Models từ Key"))
            self.btn_refresh.setToolTip("Fetch all available Gemini models for your API Key" if get_current_language() == "en" else "Gửi yêu cầu tới Google AI Studio để tải toàn bộ model khả dụng cho API Key của bạn")

    def set_models(self, models_list: list, selected_names: list[str] = None):
        """Cập nhật danh sách model và trạng thái tích chọn"""
        if not models_list:
            models_list = DEFAULT_GEMINI_MODELS.copy()
        
        parsed = []
        for m in models_list:
            if isinstance(m, dict):
                parsed.append(m)
            elif isinstance(m, str) and m.strip():
                parsed.append({"name": m.strip(), "display_name": m.strip(), "description": ""})

        self.models_list = parsed

        if selected_names is not None:
            self.selected_models = set(selected_names)

        self.render_checkboxes()

    def set_selected_models(self, names: list[str]):
        """Cập nhật danh sách model được tích chọn"""
        if names:
            self.selected_models = set(names)
            # Đồng thời đảm bảo nếu có model trong names chưa có trong models_list thì thêm vào
            existing_names = {m["name"] for m in self.models_list}
            for n in names:
                if n and n not in existing_names:
                    self.models_list.append({"name": n, "display_name": n, "description": ""})
            self.render_checkboxes()

    def get_active_models(self) -> list[str]:
        """Lấy danh sách các model Gemini đang được tích chọn"""
        selected = []
        for m in self.models_list:
            name = m["name"]
            if name in self.selected_models:
                selected.append(name)
        if not selected and self.models_list:
            # Mặc định chọn model đầu tiên nếu không chọn gì
            return [self.models_list[0]["name"]]
        return selected

    def get_tags(self) -> list[str]:
        return self.get_active_models()

    def set_tags(self, tags: list):
        if tags:
            self.set_selected_models([str(t) for t in tags])

    def get_all_models_data(self) -> list[dict]:
        """Trả về dữ liệu tất cả models kèm trạng thái enabled"""
        data = []
        for m in self.models_list:
            name = m["name"]
            is_checked = name in self.selected_models
            data.append({
                "name": name,
                "display_name": m.get("display_name", name),
                "description": m.get("description", ""),
                "enabled": is_checked,
                "is_valid": True,
                "is_thinking": False,
                "status": "ok"
            })
        return data

    def select_all(self):
        """Tích chọn tất cả model"""
        for m in self.models_list:
            self.selected_models.add(m["name"])
        for cb in self.checkboxes.values():
            cb.blockSignals(True)
            cb.setChecked(True)
            cb.blockSignals(False)
        self.models_changed.emit(self.get_active_models())

    def on_checkbox_toggled(self, model_name: str, is_checked: bool):
        if is_checked:
            self.selected_models.add(model_name)
        else:
            self.selected_models.discard(model_name)
        self.models_changed.emit(self.get_active_models())

    def render_checkboxes(self):
        """Dựng lại toàn bộ danh sách Checkbox trong Grid"""
        # Xóa các widget cũ
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.checkboxes.clear()

        cols = 2  # Chia làm 2 cột
        for idx, m in enumerate(self.models_list):
            name = m.get("name", "")
            display_name = m.get("display_name") or name
            desc = m.get("description", "")
            is_checked = name in self.selected_models

            cb = QCheckBox(display_name)
            cb.setToolTip(desc if desc else f"Model: {name}")
            cb.setChecked(is_checked)
            cb.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    font-weight: 500;
                    color: #1E293B;
                    padding: 2px 4px;
                }
                QCheckBox:hover {
                    color: #0284C7;
                }
                QCheckBox::indicator {
                    width: 14px;
                    height: 14px;
                }
            """)
            cb.toggled.connect(lambda checked, n=name: self.on_checkbox_toggled(n, checked))
            self.checkboxes[name] = cb

            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(cb, row, col)

    def fetch_models_from_key(self, api_key: str, callback=None):
        """Khởi chạy worker tải danh sách model trực tiếp từ Google API Key"""
        if not api_key or not api_key.strip():
            self.status_label.setText("⚠️ <i>Chưa nhập API Key Google AI Studio</i>")
            return

        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ Đang tải...")
        self.status_label.setText("⏳ <i>Đang lấy danh sách models từ Google AI Studio...</i>")

        self.fetch_worker = FetchGeminiModelsWorker(api_key.strip())
        
        def on_finished(ok: bool, models: list, msg: str):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("🔄 Tải Models từ Key")
            if ok and models:
                # Giữ nguyên các model đang được tích chọn (nếu có trong danh sách mới)
                curr_selected = self.get_active_models()
                self.models_list = models
                self.selected_models = set([m["name"] for m in models if m["name"] in curr_selected])
                if not self.selected_models:
                    # Mặc định tích 3 model nhanh nhất
                    self.selected_models = {
                        models[0]["name"],
                        models[1]["name"] if len(models) > 1 else models[0]["name"]
                    }
                self.render_checkboxes()
                self.status_label.setText(f"✅ <b>{msg}</b>")
                self.models_changed.emit(self.get_active_models())
            else:
                self.status_label.setText(f"⚠️ <i>{msg}</i>")

            if callback:
                callback(ok, models, msg)

        self.fetch_worker.finished_signal.connect(on_finished)
        self.fetch_worker.start()
