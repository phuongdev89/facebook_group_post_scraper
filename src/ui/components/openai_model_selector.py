from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, 
    QCheckBox, QPushButton, QScrollArea, QFrame, QLineEdit, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from src.core.ai_analyzer import (
    DEFAULT_OPENAI_MODELS,
    fetch_openai_models_from_api,
    is_thinking_model
)


class FetchOpenAIModelsWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)

    def __init__(self, base_url: str = "", api_key: str = "", timeout: int = 8):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def run(self):
        ok, models, msg = fetch_openai_models_from_api(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout
        )
        self.finished_signal.emit(ok, models, msg)


class OpenAIModelSelectorWidget(QWidget):
    """
    Widget hiển thị danh sách checkbox các model OpenAI / OpenAI Tương thích.
    Hỗ trợ:
    - Check/Uncheck từng model để sử dụng luân phiên khi cào (tương tự Gemini Model Selector).
    - Tự động tải từ Base URL / API Key (OpenAI, OpenRouter, DeepSeek, Groq, Ollama, LM Studio...).
    - Tự động sắp xếp models theo bảng chữ cái Alphabet (A-Z).
    - Tự động phát hiện và đánh dấu các model Thinking / Reasoner để loại trừ.
    - Cho phép nhập thêm bất kỳ model tùy chỉnh nào và kiểm tra live qua API.
    """
    models_changed = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.models_list = DEFAULT_OPENAI_MODELS.copy()
        self._sort_models_alphabetically()
        self.checkboxes: dict[str, QCheckBox] = {}
        self.selected_models: set[str] = {"gpt-4o-mini", "gpt-4o"}
        self.fetch_worker = None
        self.init_ui()

    def _sort_models_alphabetically(self):
        """Sắp xếp danh sách model theo Alphabet (A-Z), gom nhóm model Thinking ở phía sau"""
        def sort_key(item):
            name = item.get("name", "").lower() if isinstance(item, dict) else str(item).lower()
            is_think = item.get("is_thinking", is_thinking_model(name)) if isinstance(item, dict) else is_thinking_model(name)
            return (1 if is_think else 0, name)
        self.models_list.sort(key=sort_key)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # 1. Header bar
        header_layout = QHBoxLayout()
        self.status_label = QLabel("🧠 <b>Danh sách Model OpenAI / Tương thích:</b>")
        self.status_label.setStyleSheet("color: #4F46E5; font-size: 12px;")
        header_layout.addWidget(self.status_label)

        header_layout.addStretch()

        self.btn_select_all = QPushButton("Chọn tất cả")
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
        self.btn_select_all.clicked.connect(self.toggle_select_all)
        header_layout.addWidget(self.btn_select_all)

        self.btn_clear_all = QPushButton("🗑 Xóa tất cả")
        self.btn_clear_all.setToolTip("Xóa toàn bộ danh sách model OpenAI để nhập lại hoặc tải lại từ đầu")
        self.btn_clear_all.setStyleSheet("""
            QPushButton {
                background-color: #FEF2F2;
                color: #DC2626;
                font-size: 10px;
                font-weight: bold;
                padding: 2px 6px;
                border-radius: 3px;
                border: 1px solid #FECACA;
            }
            QPushButton:hover { background-color: #FEE2E2; }
        """)
        self.btn_clear_all.clicked.connect(self.clear_all_models)
        header_layout.addWidget(self.btn_clear_all)

        self.btn_refresh = QPushButton("🔄 Tải Models từ API")
        self.btn_refresh.setToolTip("Gửi yêu cầu tới Base URL / API Key để tải toàn bộ danh sách model khả dụng")
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
            QPushButton:disabled { background-color: #E2E8F0; color: #94A3B8; }
        """)
        header_layout.addWidget(self.btn_refresh)

        self.btn_test_models = QPushButton("🧪 Test AI & Kiểm tra Models")
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
        header_layout.addWidget(self.btn_test_models)

        main_layout.addLayout(header_layout)

        # 2. Custom Model Input Bar
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(4)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Nhập thêm tên model tùy chỉnh (VD: deepseek-chat, qwen-2.5) rồi Enter hoặc bấm +...")
        self.custom_input.setStyleSheet("""
            QLineEdit {
                padding: 3px 6px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 11px;
                background: white;
            }
            QLineEdit:focus { border-color: #6366F1; }
        """)
        self.custom_input.returnPressed.connect(self.add_custom_model_from_input)
        input_layout.addWidget(self.custom_input)

        btn_add = QPushButton("+")
        btn_add.setToolTip("Thêm model này vào danh sách checkbox")
        btn_add.setFixedSize(26, 26)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: bold;
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        btn_add.clicked.connect(self.add_custom_model_from_input)
        input_layout.addWidget(btn_add)

        main_layout.addLayout(input_layout)

        # 3. Scroll Area for Checkbox Grid
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(110)
        self.scroll_area.setMaximumHeight(180)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #E0E7FF;
                border-radius: 6px;
                background-color: #FAFAFD;
            }
        """)

        self.container_widget = QWidget()
        self.grid_layout = QGridLayout(self.container_widget)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setSpacing(6)
        self.grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.scroll_area.setWidget(self.container_widget)
        main_layout.addWidget(self.scroll_area)

        # 4. Note
        self.note_label = QLabel("💡 <i>Tích chọn (✓) các model muốn dùng luân phiên. Model Thinking/Lỗi sẽ tự động bị loại trừ.</i>")
        self.note_label.setStyleSheet("font-size: 10px; color: #64748B;")
        self.note_label.setWordWrap(True)
        main_layout.addWidget(self.note_label)

        self.render_checkboxes()

    def add_custom_model_from_input(self):
        text = self.custom_input.text().strip()
        if not text:
            return
        for item in text.split(","):
            val = item.strip()
            if val:
                self.add_model(val, auto_check=True)
        self.custom_input.clear()

    def add_model(self, name: str, display_name: str = "", description: str = "", auto_check: bool = True):
        name = name.strip()
        if not name:
            return

        for m in self.models_list:
            if m["name"].lower() == name.lower():
                if auto_check and not m.get("is_thinking", False):
                    self.selected_models.add(m["name"])
                    self.render_checkboxes()
                    self.models_changed.emit(self.get_active_models())
                return

        thinking = is_thinking_model(name)
        new_entry = {
            "name": name,
            "display_name": display_name or name,
            "description": description or ("Model suy luận (Thinking)" if thinking else "Model tùy chỉnh (Chưa test)"),
            "is_thinking": thinking,
            "is_valid": not thinking,
            "enabled": (not thinking) if auto_check else False,
            "status": "thinking" if thinking else "untested",
            "message": "Model tư duy (Thinking)" if thinking else "Chưa test thực tế qua API"
        }
        self.models_list.append(new_entry)
        self._sort_models_alphabetically()
        if auto_check and not thinking:
            self.selected_models.add(name)
        self.render_checkboxes()
        self.models_changed.emit(self.get_active_models())

    def set_models_data(self, data: list, selected_names: list[str] = None):
        """Cập nhật danh sách model từ list[dict] hoặc list[str]"""
        if not data:
            data = DEFAULT_OPENAI_MODELS.copy()

        parsed = []
        new_selected = set(selected_names) if selected_names is not None else set()

        for item in data:
            if isinstance(item, dict):
                name = item.get("name", "").strip()
                if not name:
                    continue
                thinking = item.get("is_thinking", is_thinking_model(name))
                valid = item.get("is_valid", not thinking)
                enabled = item.get("enabled", valid)
                disp = item.get("display_name") or name
                desc = item.get("description", "")
                status = item.get("status")
                if not status:
                    status = "thinking" if thinking else "untested"
                msg = item.get("message", "")

                parsed.append({
                    "name": name,
                    "display_name": disp,
                    "description": desc,
                    "is_thinking": thinking,
                    "is_valid": valid,
                    "enabled": enabled,
                    "status": status,
                    "message": msg
                })
                if selected_names is None:
                    if enabled and not thinking and valid:
                        new_selected.add(name)
            elif isinstance(item, str) and item.strip():
                name = item.strip()
                thinking = is_thinking_model(name)
                parsed.append({
                    "name": name,
                    "display_name": name,
                    "description": "Model suy luận (Thinking)" if thinking else "",
                    "is_thinking": thinking,
                    "is_valid": not thinking,
                    "enabled": not thinking,
                    "status": "thinking" if thinking else "untested",
                    "message": "Model tư duy (Thinking)" if thinking else "Chưa test thực tế"
                })
                if selected_names is None and not thinking:
                    new_selected.add(name)

        self.models_list = parsed
        self._sort_models_alphabetically()

        if selected_names is not None:
            self.selected_models = set(selected_names)
        elif new_selected:
            self.selected_models = new_selected
        else:
            # Mặc định chọn model đầu tiên hợp lệ
            for m in self.models_list:
                if not m.get("is_thinking"):
                    self.selected_models.add(m["name"])
                    break

        self.render_checkboxes()
        self.models_changed.emit(self.get_active_models())

    # Compatibility alias
    def set_tags(self, tags: list):
        self.set_models_data(tags)

    def set_selected_models(self, names: list[str]):
        if names:
            self.selected_models = set(names)
            existing_names = {m["name"] for m in self.models_list}
            for n in names:
                if n and n not in existing_names:
                    self.models_list.append({
                        "name": n,
                        "display_name": n,
                        "description": "",
                        "is_thinking": is_thinking_model(n),
                        "is_valid": not is_thinking_model(n),
                        "enabled": True,
                        "status": "ok"
                    })
            self._sort_models_alphabetically()
            self.render_checkboxes()
            self.models_changed.emit(self.get_active_models())

    def get_active_models(self) -> list[str]:
        """Lấy danh sách các model hợp lệ đang được tích chọn"""
        selected = []
        for m in self.models_list:
            name = m["name"]
            is_valid = m.get("is_valid", True)
            is_thinking = m.get("is_thinking", False)
            if name in self.selected_models and is_valid and not is_thinking:
                selected.append(name)
        if not selected:
            # Fallback nếu không có model nào được tích
            for m in self.models_list:
                if not m.get("is_thinking", False) and m.get("is_valid", True):
                    return [m["name"]]
        return selected

    def get_tags(self) -> list[str]:
        return self.get_active_models()

    def get_all_models_data(self) -> list[dict]:
        """Trả về toàn bộ danh sách metadata model để lưu vào SQLite"""
        data = []
        for m in self.models_list:
            name = m["name"]
            is_checked = name in self.selected_models
            data.append({
                "name": name,
                "display_name": m.get("display_name", name),
                "description": m.get("description", ""),
                "is_thinking": m.get("is_thinking", False),
                "is_valid": m.get("is_valid", True),
                "enabled": is_checked,
                "status": m.get("status", "ok"),
                "message": m.get("message", "")
            })
        return data

    def toggle_select_all(self):
        """Bật/Tắt chọn tất cả model hợp lệ"""
        all_valid = [m["name"] for m in self.models_list if not m.get("is_thinking", False) and m.get("is_valid", True)]
        if self.selected_models.issuperset(all_valid) and all_valid:
            self.selected_models.clear()
            self.btn_select_all.setText("Chọn tất cả")
        else:
            self.selected_models.update(all_valid)
            self.btn_select_all.setText("Bỏ chọn tất cả")

        for name, cb in self.checkboxes.items():
            cb.blockSignals(True)
            cb.setChecked(name in self.selected_models)
            cb.blockSignals(False)
        self.models_changed.emit(self.get_active_models())

    def on_checkbox_toggled(self, model_name: str, is_checked: bool):
        if is_checked:
            self.selected_models.add(model_name)
        else:
            self.selected_models.discard(model_name)
        self.models_changed.emit(self.get_active_models())

    def set_model_testing_state(self, model_name: str, current: int = 0, total: int = 0):
        """Hiển thị trạng thái đang kiểm tra (xoay/spinner) cho từng model trực tiếp trên checkbox"""
        if total > 0:
            self.status_label.setText(f"⏳ <b>Đang test ({current}/{total}):</b> <code>{model_name}</code>...")
        else:
            self.status_label.setText(f"⏳ <b>Đang test:</b> <code>{model_name}</code>...")

        # Tìm checkbox tương ứng và cập nhật giao diện
        cb = self.checkboxes.get(model_name)
        if cb:
            cb.setText(f"⏳ {model_name} (Đang test...)")
            cb.setStyleSheet("""
                QCheckBox {
                    font-size: 11px;
                    font-weight: bold;
                    color: #4F46E5;
                    padding: 2px 4px;
                    background-color: #EEF2FF;
                    border-radius: 3px;
                }
                QCheckBox::indicator { width: 14px; height: 14px; }
            """)

    def set_single_model_result(self, result: dict):
        """Cập nhật kết quả ngay lập tức khi một model test xong"""
        model_name = result.get("name", "")
        if not model_name:
            return

        is_valid = result.get("is_valid", False)
        is_thinking = result.get("is_thinking", False)
        status = result.get("status", "error")
        msg = result.get("message", "")

        for m in self.models_list:
            if m["name"].lower() == model_name.lower():
                m["is_valid"] = is_valid
                m["is_thinking"] = is_thinking
                m["status"] = status
                m["message"] = msg
                if not is_valid or is_thinking:
                    self.selected_models.discard(m["name"])
                else:
                    self.selected_models.add(m["name"])

        cb = self.checkboxes.get(model_name)
        if cb:
            if is_thinking:
                cb.setText(f"{model_name}  [Thinking - Loại trừ]")
                cb.setToolTip(msg or "Model suy luận (Thinking) — Đã loại trừ")
                cb.setChecked(False)
                cb.setEnabled(False)
                cb.setStyleSheet("""
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #EF4444;
                        font-style: italic;
                        padding: 2px 4px;
                    }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """)
            elif not is_valid or status == "error":
                cb.setText(f"{model_name}  [Lỗi API]")
                cb.setToolTip(msg or "Model gặp lỗi kết nối hoặc không trả về JSON thuần")
                cb.setChecked(False)
                cb.setEnabled(True)
                cb.setStyleSheet("""
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #DC2626;
                        font-style: italic;
                        padding: 2px 4px;
                    }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """)
            else:
                cb.setText(f"{model_name} ✓")
                cb.setToolTip(f"Model: {model_name} (Sẵn sàng - Test OK)")
                cb.setChecked(True)
                cb.setEnabled(True)
                cb.setStyleSheet("""
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #047857;
                        padding: 2px 4px;
                    }
                    QCheckBox:hover { color: #4F46E5; }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """)

        self.models_changed.emit(self.get_active_models())

    def update_with_test_results(self, results: list[dict]):
        """Cập nhật trạng thái từng model sau khi chạy test thực tế qua API"""
        self.status_label.setText("🧠 <b>Danh sách Model OpenAI / Tương thích:</b>")
        res_map = {r["name"].lower(): r for r in results if "name" in r}
        for m in self.models_list:
            m_key = m["name"].lower()
            if m_key in res_map:
                r = res_map[m_key]
                m["is_valid"] = r.get("is_valid", False)
                m["is_thinking"] = r.get("is_thinking", False)
                m["status"] = r.get("status", "error")
                m["message"] = r.get("message", "")
                if not m["is_valid"] or m["is_thinking"]:
                    self.selected_models.discard(m["name"])

        self._sort_models_alphabetically()
        self.render_checkboxes()
        self.models_changed.emit(self.get_active_models())

    def clear_all_models(self):
        """Xóa sạch toàn bộ danh sách model"""
        self.models_list = []
        self.selected_models.clear()
        self.render_checkboxes()
        self.status_label.setText("🧠 <b>Danh sách Model OpenAI:</b> <i>(Đã xóa hết)</i>")
        self.models_changed.emit([])

    def render_checkboxes(self):
        """Dựng lại toàn bộ danh sách Checkbox trong Grid mà không dùng thẻ HTML span"""
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.checkboxes.clear()

        if not self.models_list:
            empty_lbl = QLabel("<i>Chưa có model nào. Nhập tên model ở trên hoặc bấm '🔄 Tải Models từ API'.</i>")
            empty_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; padding: 10px;")
            self.grid_layout.addWidget(empty_lbl, 0, 0, 1, 2)
            return

        cols = 2  # Chia làm 2 cột
        for idx, m in enumerate(self.models_list):
            name = m.get("name", "")
            disp = m.get("display_name") or name
            desc = m.get("description", "")
            is_thinking = m.get("is_thinking", False)
            is_valid = m.get("is_valid", True)
            status = m.get("status", "ok")
            msg = m.get("message", "")
            is_checked = (name in self.selected_models) and (not is_thinking) and is_valid

            # Định dạng text thuần (Plain text) và style màu sắc (Không dùng HTML tags)
            if is_thinking:
                label_text = f"{name}  [Thinking - Loại trừ]"
                tooltip_text = msg or "Model suy luận (Thinking / Reasoner) — Đã loại trừ"
                cb_style = """
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #EF4444;
                        font-style: italic;
                        padding: 2px 4px;
                    }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """
            elif not is_valid or status == "error":
                label_text = f"{name}  [Lỗi API]"
                tooltip_text = msg or "Model gặp lỗi kết nối hoặc không trả về JSON thuần"
                cb_style = """
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #DC2626;
                        font-style: italic;
                        padding: 2px 4px;
                    }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """
            elif status == "ok":
                label_text = f"{name} ✓"
                tooltip_text = desc if desc else f"Model: {name} (Sẵn sàng)"
                cb_style = """
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #047857;
                        padding: 2px 4px;
                    }
                    QCheckBox:hover { color: #4F46E5; }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """
            else:
                # Trạng thái untested / chưa test -> Màu vàng / Cam hổ phách
                label_text = f"{name}"
                tooltip_text = desc if desc else f"Model: {name} (Chưa test qua API - Bấm '🧪 Test AI' để xác minh)"
                cb_style = """
                    QCheckBox {
                        font-size: 11px;
                        font-weight: 500;
                        color: #D97706;
                        padding: 2px 4px;
                    }
                    QCheckBox:hover { color: #B45309; }
                    QCheckBox::indicator { width: 14px; height: 14px; }
                """

            cb = QCheckBox(label_text)
            cb.setToolTip(tooltip_text)
            cb.setChecked(is_checked)
            cb.setEnabled(not is_thinking)
            cb.setStyleSheet(cb_style)
            cb.toggled.connect(lambda checked, n=name: self.on_checkbox_toggled(n, checked))
            self.checkboxes[name] = cb

            row = idx // cols
            col = idx % cols
            self.grid_layout.addWidget(cb, row, col)

    def fetch_models(self, base_url: str, api_key: str, callback=None):
        """Khởi chạy worker tải danh sách model từ OpenAI / Base URL API"""
        self.btn_refresh.setEnabled(False)
        self.btn_refresh.setText("⏳ Đang tải...")
        self.status_label.setText("⏳ <i>Đang lấy danh sách models từ API...</i>")

        self.fetch_worker = FetchOpenAIModelsWorker(base_url, api_key)

        def on_finished(ok: bool, models: list, msg: str):
            self.btn_refresh.setEnabled(True)
            self.btn_refresh.setText("🔄 Tải Models từ API")
            if ok and models:
                curr_selected = self.get_active_models()
                self.models_list = models
                self._sort_models_alphabetically()
                self.selected_models = set([m["name"] for m in models if m["name"] in curr_selected and not m.get("is_thinking")])
                if not self.selected_models:
                    # Mặc định tích các model hợp lệ đầu tiên
                    valid_top = [m["name"] for m in self.models_list if not m.get("is_thinking")][:3]
                    self.selected_models = set(valid_top)

                self.render_checkboxes()
                self.status_label.setText(f"✅ <b>{msg}</b>")
                self.models_changed.emit(self.get_active_models())
            else:
                self.status_label.setText(f"⚠️ <i>{msg}</i>")

            if callback:
                callback(ok, models, msg)

        self.fetch_worker.finished_signal.connect(on_finished)
        self.fetch_worker.start()
