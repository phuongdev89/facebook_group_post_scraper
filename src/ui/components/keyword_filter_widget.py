"""
Keyword Filter Widget - Giao diện bộ lọc từ khóa 2 chế độ:
1. "🧱 Dựng điều kiện trực quan (Visual Rule Builder)": Thêm nhóm, thêm dòng điều kiện AND/OR/NOT
2. "✍️ Tự nhập biểu thức (Raw Expression)": Nhập tự do ("a1" AND ("bán" OR "pass")) OR ("combo" AND "xé lẻ")
Tự động chuyển đổi 2 chiều và xác thực cú pháp thời gian thực.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QRadioButton, QButtonGroup,
    QFrame, QScrollArea, QGroupBox, QMessageBox, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal
from src.utils.keyword_engine import (
    validate_expression,
    expression_to_visual_groups,
    visual_groups_to_expression
)


from src.utils.i18n import tr, get_current_language


class ConditionRowWidget(QWidget):
    """Một dòng điều kiện trong nhóm: [Dropdown AND/OR/NOT] [Ô nhập từ khóa] [Nút Xóa]"""
    changed = pyqtSignal()
    removed = pyqtSignal(object)

    def __init__(self, op="AND", text="", is_first=False, parent=None):
        super().__init__(parent)
        self.is_first = is_first
        self.init_ui(op, text)

    def init_ui(self, op, text):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(6)

        self.op_combo = QComboBox()
        self.op_combo.addItem(tr("filter_op_and"), "AND")
        self.op_combo.addItem(tr("filter_op_or"), "OR")
        self.op_combo.addItem(tr("filter_op_not"), "NOT")
        self.op_combo.setFixedWidth(140)
        self.op_combo.setStyleSheet("""
            QComboBox {
                padding: 4px 8px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                background-color: #F9FAFB;
                font-weight: 500;
                font-size: 11px;
            }
        """)

        # Set operator
        op_upper = str(op or "AND").upper()
        idx = self.op_combo.findData(op_upper)
        if idx >= 0:
            self.op_combo.setCurrentIndex(idx)
        else:
            self.op_combo.setCurrentIndex(0)

        self.op_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        layout.addWidget(self.op_combo)

        # Text input
        self.text_input = QLineEdit()
        self.text_input.setText(text)
        self.text_input.setPlaceholderText(tr("filter_input_placeholder"))
        self.text_input.setStyleSheet("""
            QLineEdit {
                padding: 5px 8px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus { border: 1px solid #4F46E5; }
        """)
        self.text_input.textChanged.connect(lambda: self.changed.emit())
        layout.addWidget(self.text_input, stretch=1)

        # Delete button
        self.del_btn = QPushButton("✕")
        self.del_btn.setFixedSize(24, 24)
        self.del_btn.setStyleSheet("""
            QPushButton {
                background-color: #FEE2E2;
                color: #DC2626;
                font-weight: bold;
                font-size: 12px;
                border: 1px solid #FECACA;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #EF4444; color: white; }
        """)
        self.del_btn.clicked.connect(lambda: self.removed.emit(self))
        layout.addWidget(self.del_btn)

    def get_data(self) -> dict:
        return {
            "op": self.op_combo.currentData(),
            "text": self.text_input.text().strip()
        }

    def set_data(self, op: str, text: str):
        idx = self.op_combo.findData(op)
        if idx >= 0:
            self.op_combo.setCurrentIndex(idx)
        self.text_input.setText(text)

    def retranslate_ui(self):
        curr_op = self.op_combo.currentData()
        self.op_combo.blockSignals(True)
        self.op_combo.clear()
        self.op_combo.addItem(tr("filter_op_and"), "AND")
        self.op_combo.addItem(tr("filter_op_or"), "OR")
        self.op_combo.addItem(tr("filter_op_not"), "NOT")
        idx = self.op_combo.findData(curr_op)
        if idx >= 0:
            self.op_combo.setCurrentIndex(idx)
        self.op_combo.blockSignals(False)
        if hasattr(self, 'text_input'):
            self.text_input.setPlaceholderText(tr("filter_input_placeholder"))


class GroupCardWidget(QFrame):
    """Khối một nhóm điều kiện (Hỗ trợ toán tử nối từ nhóm 2 trở đi)"""
    changed = pyqtSignal()
    group_removed = pyqtSignal(object)

    def __init__(self, group_index: int = 1, group_op: str = "OR", items: list = None, parent=None):
        super().__init__(parent)
        self.group_index = group_index
        self.group_op = group_op
        self.rows = []
        self.init_ui(items or [{"op": "AND", "text": ""}])

    def init_ui(self, items):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("""
            GroupCardWidget {
                background-color: #F8FAFC;
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                margin-bottom: 8px;
            }
        """)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 8, 10, 8)
        main_layout.setSpacing(6)

        # Header bar
        header_layout = QHBoxLayout()

        # Toán tử nối với nhóm trước (Chỉ hiển thị từ Nhóm 2 trở đi)
        self.group_op_container = QWidget()
        op_h_layout = QHBoxLayout(self.group_op_container)
        op_h_layout.setContentsMargins(0, 0, 0, 0)
        op_h_layout.setSpacing(4)

        op_prefix_lbl = QLabel(tr("filter_op_prefix"))
        op_prefix_lbl.setStyleSheet("color: #4B5563; font-size: 11px; font-weight: bold;")
        op_h_layout.addWidget(op_prefix_lbl)

        self.group_op_combo = QComboBox()
        self.group_op_combo.addItem(tr("filter_op_or"), "OR")
        self.group_op_combo.addItem(tr("filter_op_and"), "AND")
        self.group_op_combo.addItem(tr("filter_op_not"), "NOT")
        self.group_op_combo.setFixedWidth(175)
        self.group_op_combo.setStyleSheet("""
            QComboBox {
                padding: 3px 6px;
                border: 1px solid #93C5FD;
                border-radius: 4px;
                background-color: #EFF6FF;
                color: #1E40AF;
                font-weight: bold;
                font-size: 11px;
            }
        """)

        idx = self.group_op_combo.findData(str(self.group_op or "OR").upper())
        if idx >= 0:
            self.group_op_combo.setCurrentIndex(idx)
        else:
            self.group_op_combo.setCurrentIndex(0)

        self.group_op_combo.currentIndexChanged.connect(lambda: self.changed.emit())
        op_h_layout.addWidget(self.group_op_combo)
        header_layout.addWidget(self.group_op_container)

        self.badge_lbl = QLabel(tr("filter_group_badge").format(idx=self.group_index))
        self.badge_lbl.setStyleSheet("font-weight: bold; color: #1E293B; font-size: 12px;")
        header_layout.addWidget(self.badge_lbl)

        # Ẩn dropdown toán tử nếu là nhóm 1
        self.group_op_container.setVisible(self.group_index > 1)

        header_layout.addStretch()

        self.del_group_btn = QPushButton(tr("filter_del_group"))
        self.del_group_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #EF4444;
                font-size: 11px;
                border: none;
                padding: 2px 6px;
            }
            QPushButton:hover { text-decoration: underline; }
        """)
        self.del_group_btn.clicked.connect(lambda: self.group_removed.emit(self))
        header_layout.addWidget(self.del_group_btn)
        main_layout.addLayout(header_layout)

        # Rows container
        self.rows_layout = QVBoxLayout()
        self.rows_layout.setContentsMargins(0, 0, 0, 0)
        self.rows_layout.setSpacing(4)
        main_layout.addLayout(self.rows_layout)

        for idx, it in enumerate(items):
            self._add_row(it.get("op", "AND"), it.get("text", ""), is_first=(idx == 0))

        # Bottom action bar of this group
        btn_layout = QHBoxLayout()
        add_cond_btn = QPushButton(tr("filter_add_cond"))
        add_cond_btn.setStyleSheet("""
            QPushButton {
                background-color: #EEF2FF;
                color: #4338CA;
                font-size: 11px;
                font-weight: 600;
                border: 1px dashed #C7D2FE;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover { background-color: #E0E7FF; }
        """)
        add_cond_btn.clicked.connect(lambda: self._add_row("AND", ""))
        btn_layout.addWidget(add_cond_btn)
        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

    def _add_row(self, op="AND", text="", is_first=False):
        row = ConditionRowWidget(op=op, text=text, is_first=is_first, parent=self)
        row.changed.connect(lambda: self.changed.emit())
        row.removed.connect(self._remove_row)
        self.rows.append(row)
        self.rows_layout.addWidget(row)
        self.changed.emit()

    def _remove_row(self, row_widget):
        if len(self.rows) <= 1:
            # Nếu chỉ còn 1 dòng, clear text chứ không xóa hết
            row_widget.set_data("AND", "")
            self.changed.emit()
            return

        if row_widget in self.rows:
            self.rows.remove(row_widget)
            self.rows_layout.removeWidget(row_widget)
            row_widget.deleteLater()
            self.changed.emit()

    def set_group_index(self, idx: int):
        self.group_index = idx
        self.badge_lbl.setText(tr("filter_group_badge").format(idx=self.group_index))
        if hasattr(self, 'group_op_container'):
            self.group_op_container.setVisible(self.group_index > 1)

    def get_group_op(self) -> str:
        if self.group_index <= 1:
            return "OR"
        return self.group_op_combo.currentData()

    def get_data(self) -> dict:
        items = [r.get_data() for r in self.rows if r.get_data().get("text")]
        return {
            "id": self.group_index,
            "group_op": self.get_group_op(),
            "items": items if items else [{"op": "AND", "text": ""}]
        }

    def retranslate_ui(self):
        curr_op = self.group_op_combo.currentData()
        self.group_op_combo.blockSignals(True)
        self.group_op_combo.clear()
        self.group_op_combo.addItem(tr("filter_op_or"), "OR")
        self.group_op_combo.addItem(tr("filter_op_and"), "AND")
        self.group_op_combo.addItem(tr("filter_op_not"), "NOT")
        idx = self.group_op_combo.findData(curr_op)
        if idx >= 0:
            self.group_op_combo.setCurrentIndex(idx)
        self.group_op_combo.blockSignals(False)

        if hasattr(self, 'badge_lbl'):
            self.badge_lbl.setText(tr("filter_group_badge").format(idx=self.group_index))
        if hasattr(self, 'del_group_btn'):
            self.del_group_btn.setText(tr("filter_del_group"))
        if hasattr(self, 'add_cond_btn'):
            self.add_cond_btn.setText(tr("filter_add_cond"))
        for r in self.rows:
            if hasattr(r, 'retranslate_ui'):
                r.retranslate_ui()


class KeywordFilterWidget(QWidget):
    """
    Component bộ lọc từ khóa 2 chế độ:
    - Mode 0: 🧱 Dựng điều kiện trực quan (Visual Rule Builder)
    - Mode 1: ✍️ Tự nhập biểu thức (Raw Expression)
    """
    expression_changed = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = 0  # 0: visual, 1: raw
        self.groups_widgets = []
        self._suppress_events = False
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(6)

        # Header Box
        header_box = QHBoxLayout()
        header_lbl = QLabel(f"<b>{tr('kw_card_title')}</b>")
        header_lbl.setStyleSheet("font-size: 12px; color: #1E293B;")
        header_box.addWidget(header_lbl)

        # Mode Selection Radio Buttons
        self.mode_group = QButtonGroup(self)
        
        self.radio_visual = QRadioButton(tr("filter_mode_visual"))
        self.radio_visual.setChecked(True)
        self.mode_group.addButton(self.radio_visual, 0)
        header_box.addWidget(self.radio_visual)

        self.radio_raw = QRadioButton(tr("filter_mode_raw"))
        self.mode_group.addButton(self.radio_raw, 1)
        header_box.addWidget(self.radio_raw)

        self.mode_group.idClicked.connect(self.on_mode_switched)

        header_box.addStretch()

        # Syntax Status Label
        self.syntax_status_lbl = QLabel(tr("filter_syntax_valid"))
        self.syntax_status_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        header_box.addWidget(self.syntax_status_lbl)

        main_layout.addLayout(header_box)

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # --- CONTAINER 1: VISUAL BUILDER VIEW ---
        self.visual_container = QWidget()
        self.visual_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        visual_layout = QVBoxLayout(self.visual_container)
        visual_layout.setContentsMargins(0, 0, 0, 0)
        visual_layout.setSpacing(6)

        # Scroll Area for Group Cards (Xóa khung viền thừa, nền trong suốt)
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setMinimumHeight(180)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.scroll_area.setStyleSheet("QScrollArea { border: none; background-color: transparent; }")

        self.groups_content_widget = QWidget()
        self.groups_content_widget.setStyleSheet("background: transparent;")
        self.groups_layout = QVBoxLayout(self.groups_content_widget)
        self.groups_layout.setContentsMargins(0, 0, 0, 0)
        self.groups_layout.setSpacing(6)
        self.groups_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll_area.setWidget(self.groups_content_widget)

        visual_layout.addWidget(self.scroll_area, 1)

        # Bottom Bar of Visual Builder
        bottom_bar = QHBoxLayout()
        add_group_btn = QPushButton(tr("filter_add_new_group"))
        add_group_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-size: 11px;
                font-weight: bold;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        add_group_btn.clicked.connect(self.add_visual_group)
        bottom_bar.addWidget(add_group_btn)

        bottom_bar.addSpacing(15)
        preset_lbl = QLabel(tr("filter_quick_presets"))
        preset_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        bottom_bar.addWidget(preset_lbl)

        btn_sample1 = QPushButton("Mẫu A1 Bán/Pass" if get_current_language() == "vi" else "Preset: Buy/Sell A1")
        btn_sample1.setStyleSheet("font-size: 10px; padding: 3px 6px;")
        btn_sample1.clicked.connect(lambda: self.set_expression('("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'))
        bottom_bar.addWidget(btn_sample1)

        btn_sample2 = QPushButton("Mẫu Phủ định NOT lock" if get_current_language() == "vi" else "Preset: NOT lock")
        btn_sample2.setStyleSheet("font-size: 10px; padding: 3px 6px;")
        btn_sample2.clicked.connect(lambda: self.set_expression('(iphone or samsung) and not (lock or "dính icloud" or xác)'))
        bottom_bar.addWidget(btn_sample2)

        btn_clear = QPushButton(tr("filter_btn_clear"))
        btn_clear.setStyleSheet("font-size: 10px; padding: 3px 6px; color: #DC2626;")
        btn_clear.clicked.connect(self.clear_all)
        bottom_bar.addWidget(btn_clear)

        bottom_bar.addStretch()
        visual_layout.addLayout(bottom_bar)

        main_layout.addWidget(self.visual_container, 1)

        # --- CONTAINER 2: RAW EXPRESSION VIEW ---
        self.raw_container = QWidget()
        self.raw_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.raw_container.setVisible(False)
        raw_layout = QVBoxLayout(self.raw_container)
        raw_layout.setContentsMargins(0, 0, 0, 0)
        raw_layout.setSpacing(4)

        self.raw_expr_input = QLineEdit()
        self.raw_expr_input.setPlaceholderText('Ví dụ: ("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")')
        self.raw_expr_input.setStyleSheet("""
            QLineEdit {
                padding: 8px 10px;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
                font-family: Consolas, monospace;
            }
            QLineEdit:focus { border: 1px solid #4F46E5; }
        """)
        self.raw_expr_input.textChanged.connect(self.on_raw_input_changed)
        raw_layout.addWidget(self.raw_expr_input)

        raw_hint = QLabel(tr("filter_raw_hint"))
        raw_hint.setStyleSheet("color: #6B7280; font-size: 11px;")
        raw_layout.addWidget(raw_hint)

        main_layout.addWidget(self.raw_container, 1)

        # Khởi tạo mặc định 1 nhóm
        self.add_visual_group()

    def add_visual_group(self, group_op="OR", items=None):
        """Thêm 1 nhóm điều kiện vào giao diện trực quan"""
        idx = len(self.groups_widgets) + 1
        group_card = GroupCardWidget(group_index=idx, group_op=group_op, items=items or [{"op": "AND", "text": ""}], parent=self)
        group_card.changed.connect(self.on_visual_data_changed)
        group_card.group_removed.connect(self.remove_visual_group)
        self.groups_widgets.append(group_card)
        self.groups_layout.addWidget(group_card)
        self.on_visual_data_changed()

    def remove_visual_group(self, group_card):
        """Xóa 1 nhóm điều kiện"""
        if len(self.groups_widgets) <= 1:
            # Không xóa nhóm cuối cùng, chỉ reset
            self.set_expression("")
            return

        if group_card in self.groups_widgets:
            self.groups_widgets.remove(group_card)
            self.groups_layout.removeWidget(group_card)
            group_card.deleteLater()

            # Đánh số lại các nhóm
            for i, g in enumerate(self.groups_widgets):
                g.set_group_index(i + 1)

            self.on_visual_data_changed()

    def clear_all(self):
        """Xóa toàn bộ bộ lọc"""
        self._suppress_events = True
        for g in list(self.groups_widgets):
            self.groups_layout.removeWidget(g)
            g.deleteLater()
        self.groups_widgets.clear()
        self.raw_expr_input.clear()
        self._suppress_events = False
        self.add_visual_group()
        self.validate_and_emit("")

    def on_visual_data_changed(self):
        """Khi người dùng sửa nội dung trong chế độ trực quan -> tự tạo biểu thức chuỗi"""
        if self._suppress_events or self.current_mode != 0:
            return

        groups_data = [g.get_data() for g in self.groups_widgets]
        expr = visual_groups_to_expression(groups_data)
        
        self._suppress_events = True
        self.raw_expr_input.setText(expr)
        self._suppress_events = False

        self.validate_and_emit(expr)

    def on_raw_input_changed(self, text: str):
        """Khi người dùng sửa nội dung trong chế độ Raw -> validate"""
        if self._suppress_events or self.current_mode != 1:
            return

        self.validate_and_emit(text)

    def validate_and_emit(self, expr: str):
        """Xác thực biểu thức và phát tín hiệu thay đổi"""
        expr_clean = expr.strip()
        ok, msg = validate_expression(expr_clean)

        if not expr_clean:
            self.syntax_status_lbl.setText(tr("filter_syntax_empty"))
            self.syntax_status_lbl.setStyleSheet("color: #6B7280; font-size: 11px;")
        elif ok:
            self.syntax_status_lbl.setText(tr("filter_syntax_valid"))
            self.syntax_status_lbl.setStyleSheet("color: #10B981; font-weight: bold; font-size: 11px;")
        else:
            self.syntax_status_lbl.setText(msg)
            self.syntax_status_lbl.setStyleSheet("color: #EF4444; font-weight: bold; font-size: 11px;")

        self.expression_changed.emit(expr_clean)

    def on_mode_switched(self, mode_id: int):
        """Chuyển đổi qua lại giữa 2 chế độ và tự parse dữ liệu tương ứng"""
        if mode_id == self.current_mode:
            return

        self.current_mode = mode_id

        if mode_id == 0:
            # Chuyển sang Trực quan (Visual Builder) -> Parse từ Raw text
            raw_text = self.raw_expr_input.text().strip()
            ok, msg = validate_expression(raw_text)
            if raw_text and not ok:
                QMessageBox.warning(
                    self,
                    "Invalid Syntax" if get_current_language() == "en" else "Cú pháp biểu thức chưa hợp lệ",
                    f"{msg}"
                )
                # Rollback radio về Raw
                self.radio_raw.setChecked(True)
                self.current_mode = 1
                return

            self._suppress_events = True
            visual_groups = expression_to_visual_groups(raw_text)
            self._render_visual_groups(visual_groups)
            self._suppress_events = False

            self.visual_container.setVisible(True)
            self.raw_container.setVisible(False)
            self.validate_and_emit(raw_text)

        else:
            # Chuyển sang Tự nhập biểu thức (Raw Expression) -> Tạo string từ Visual groups
            groups_data = [g.get_data() for g in self.groups_widgets]
            expr = visual_groups_to_expression(groups_data)

            self._suppress_events = True
            self.raw_expr_input.setText(expr)
            self._suppress_events = False

            self.visual_container.setVisible(False)
            self.raw_container.setVisible(True)
            self.validate_and_emit(expr)

    def _render_visual_groups(self, groups_data: list):
        """Render lại toàn bộ danh sách group cards"""
        for g in list(self.groups_widgets):
            self.groups_layout.removeWidget(g)
            g.deleteLater()
        self.groups_widgets.clear()

        for idx, grp in enumerate(groups_data):
            items = grp.get("items", [{"op": "AND", "text": ""}])
            grp_op = grp.get("group_op", "OR")
            card = GroupCardWidget(group_index=idx + 1, group_op=grp_op, items=items, parent=self)
            card.changed.connect(self.on_visual_data_changed)
            card.group_removed.connect(self.remove_visual_group)
            self.groups_widgets.append(card)
            self.groups_layout.addWidget(card)

    def get_expression(self) -> str:
        """Lấy chuỗi biểu thức logic hiện tại"""
        if self.current_mode == 1:
            return self.raw_expr_input.text().strip()
        else:
            groups_data = [g.get_data() for g in self.groups_widgets]
            return visual_groups_to_expression(groups_data)

    def set_expression(self, expr: str):
        """Nạp biểu thức vào component (đồng bộ cả 2 chế độ)"""
        expr = str(expr or "").strip()
        self._suppress_events = True
        self.raw_expr_input.setText(expr)

        visual_groups = expression_to_visual_groups(expr)
        self._render_visual_groups(visual_groups)
        self._suppress_events = False

        self.validate_and_emit(expr)

    def retranslate_ui(self):
        """Retranslate dynamic labels, radio buttons and placeholders"""
        if hasattr(self, 'radio_visual'):
            self.radio_visual.setText(tr("filter_mode_visual"))
        if hasattr(self, 'radio_raw'):
            self.radio_raw.setText(tr("filter_mode_raw"))
        if hasattr(self, 'btn_add_group'):
            self.btn_add_group.setText(tr("filter_btn_add_group"))
        if hasattr(self, 'btn_clear'):
            self.btn_clear.setText(tr("filter_btn_clear"))
        if hasattr(self, 'raw_expr_input'):
            self.raw_expr_input.setPlaceholderText(
                'e.g.: ("a1" and ("sell" or "pass")) or ("combo" and "split")'
                if get_current_language() == "en" else
                'Ví dụ: ("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'
            )
        if hasattr(self, 'raw_hint'):
            self.raw_hint.setText(tr("filter_raw_hint"))
        for g in self.groups_widgets:
            if hasattr(g, 'retranslate_ui'):
                g.retranslate_ui()
        self.validate_and_emit(self.get_expression())
