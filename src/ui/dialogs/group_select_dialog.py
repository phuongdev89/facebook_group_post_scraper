import unicodedata
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QRadioButton,
    QButtonGroup, QFrame, QWidget, QMessageBox, QStyledItemDelegate,
    QStyleOptionViewItem, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect, QPoint, QSize, QEvent
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont


def _strip_accents(text: str) -> str:
    """Loại bỏ dấu tiếng Việt để tìm kiếm không phân biệt dấu"""
    if not text:
        return ""
    text = unicodedata.normalize('NFD', text)
    text = "".join(char for char in text if unicodedata.category(char) != 'Mn')
    return text.replace('đ', 'd').replace('Đ', 'D').lower()


class GroupItemDelegate(QStyledItemDelegate):
    """
    Delegate tùy biến để vẽ từng hàng trong danh sách nhóm Facebook:
    - Checkbox sắc nét, rõ ràng (khi checked có nền xanh đậm #2563EB và dấu tích trắng sáng ✓)
    - Tên nhóm in đậm nổi bật (#0F172A)
    - Link nhóm rõ ràng (#64748B)
    - Hỗ trợ click chuột vào bất kỳ vị trí nào trên hàng để đổi trạng thái checkbox
    """
    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index):
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Lấy dữ liệu nhóm
        data = index.data(Qt.ItemDataRole.UserRole) or {}
        name = data.get("name") or "Nhóm chưa đặt tên"
        url = data.get("url") or ""
        check_val = index.data(Qt.ItemDataRole.CheckStateRole)
        is_checked = (check_val in (2, Qt.CheckState.Checked, Qt.CheckState.Checked.value))

        rect = option.rect

        # 1. Vẽ nền hàng (Background)
        if option.state & QStyle.StateFlag.State_Selected:
            bg_color = QColor("#EFF6FF")
        elif option.state & QStyle.StateFlag.State_MouseOver:
            bg_color = QColor("#F8FAFC")
        else:
            bg_color = QColor("#FFFFFF")

        painter.fillRect(rect, bg_color)

        # Đường viền ngăn cách dưới
        painter.setPen(QPen(QColor("#F1F5F9"), 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())

        # 2. Vẽ Checkbox sắc nét
        box_size = 18
        box_x = rect.left() + 12
        box_y = rect.top() + (rect.height() - box_size) // 2
        box_rect = QRect(box_x, box_y, box_size, box_size)

        if is_checked:
            # Trạng thái CHECKED: Nền xanh biển đậm + Dấu tích trắng sắc nét
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor("#2563EB")))
            painter.drawRoundedRect(box_rect, 4, 4)

            # Vẽ dấu tích ✓ trắng rõ ràng
            pen = QPen(QColor("#FFFFFF"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)
            p1 = QPoint(box_x + 4, box_y + 9)
            p2 = QPoint(box_x + 8, box_y + 13)
            p3 = QPoint(box_x + 14, box_y + 5)
            painter.drawLine(p1, p2)
            painter.drawLine(p2, p3)
        else:
            # Trạng thái UNCHECKED: Khung viền xám + Nền trắng sạch
            painter.setPen(QPen(QColor("#94A3B8"), 1.8))
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.drawRoundedRect(box_rect.adjusted(1, 1, -1, -1), 4, 4)

        # 3. Vẽ Text: Tên nhóm & Link URL
        text_x = box_x + box_size + 12
        text_width = rect.width() - text_x - 14

        # Tên nhóm (in đậm, màu tối)
        font_name = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(font_name)
        painter.setPen(QColor("#0F172A"))
        name_rect = QRect(text_x, rect.top() + 6, text_width, 18)
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name)

        # Link nhóm (màu xám nhạt, có icon link 🔗)
        font_url = QFont("Segoe UI", 8)
        painter.setFont(font_url)
        painter.setPen(QColor("#64748B"))
        url_rect = QRect(text_x, rect.top() + 25, text_width, 16)
        painter.drawText(url_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, f"🔗 {url}")

        painter.restore()

    def sizeHint(self, option, index):
        return QSize(option.rect.width(), 48)

    def editorEvent(self, event, model, option, index):
        # Click chuột hoặc nhấp đúp vào hàng sẽ đảo trạng thái checkbox
        if event.type() in (QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick):
            if event.button() == Qt.MouseButton.LeftButton:
                check_val = index.data(Qt.ItemDataRole.CheckStateRole)
                is_checked = (check_val in (2, Qt.CheckState.Checked, Qt.CheckState.Checked.value))
                new_val = Qt.CheckState.Unchecked if is_checked else Qt.CheckState.Checked
                model.setData(index, new_val, Qt.ItemDataRole.CheckStateRole)
                return True
        return super().editorEvent(event, model, option, index)


class GroupSelectDialog(QDialog):
    """
    Hộp thoại hiển thị danh sách nhóm Facebook bóc tách từ Cookie,
    cho phép người dùng tìm kiếm/lọc thời gian thực, tích chọn checkbox và nhập vào hệ thống.
    """
    def __init__(self, groups: list[dict], current_existing_urls: list[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("📋 Danh sách Nhóm Facebook từ Cookie")
        self.resize(780, 580)
        self.setMinimumSize(600, 420)

        self.all_groups = list(groups) if groups else []
        self.current_existing_urls = set(current_existing_urls or [])
        self.init_ui()
        self.populate_items()

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(10)
        self.setLayout(main_layout)

        # 1. Header Information & Badges
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_label = QLabel("<b>🌐 Danh sách Nhóm Facebook từ Cookie</b>")
        title_label.setStyleSheet("font-size: 15px; color: #1E3A8A;")
        title_box.addWidget(title_label)

        sub_label = QLabel("Tích chọn các nhóm bạn muốn thêm vào danh sách quét bài viết.")
        sub_label.setStyleSheet("font-size: 12px; color: #4B5563;")
        title_box.addWidget(sub_label)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Count Badges
        self.total_badge = QLabel(f"Tổng: {len(self.all_groups)} nhóm")
        self.total_badge.setStyleSheet("""
            background-color: #F3F4F6;
            color: #374151;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            border: 1px solid #D1D5DB;
        """)
        header_layout.addWidget(self.total_badge)

        self.selected_badge = QLabel("Đã chọn: 0 nhóm")
        self.selected_badge.setStyleSheet("""
            background-color: #DBEAFE;
            color: #1E40AF;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: bold;
            border: 1px solid #BFDBFE;
        """)
        header_layout.addWidget(self.selected_badge)

        main_layout.addLayout(header_layout)

        # 2. Search & Filter Bar
        filter_frame = QFrame()
        filter_frame.setStyleSheet("""
            QFrame {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px 8px;
            }
        """)
        filter_layout = QHBoxLayout(filter_frame)
        filter_layout.setContentsMargins(4, 4, 4, 4)
        filter_layout.setSpacing(8)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet("font-size: 13px;")
        filter_layout.addWidget(search_icon)

        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("Lọc nhóm theo tên, URL, hoặc ID nhóm (gõ không dấu hoặc có dấu)...")
        self.filter_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                background-color: white;
            }
            QLineEdit:focus {
                border: 1px solid #3B82F6;
            }
        """)
        self.filter_input.textChanged.connect(self.apply_filter)
        filter_layout.addWidget(self.filter_input, stretch=1)

        self.clear_filter_btn = QPushButton("❌")
        self.clear_filter_btn.setToolTip("Xóa từ khóa lọc")
        self.clear_filter_btn.setFixedSize(26, 26)
        self.clear_filter_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #6B7280;
                border: 1px solid #D1D5DB;
                border-radius: 13px;
                font-size: 10px;
            }
            QPushButton:hover { background-color: #E5E7EB; color: #111827; }
        """)
        self.clear_filter_btn.clicked.connect(self.clear_filter)
        filter_layout.addWidget(self.clear_filter_btn)

        main_layout.addWidget(filter_frame)

        # 3. Quick Selection Toolbar
        tools_layout = QHBoxLayout()
        tools_layout.setSpacing(6)

        self.select_all_btn = QPushButton("✅ Chọn tất cả")
        self.select_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #EFF6FF;
                color: #1D4ED8;
                border: 1px solid #BFDBFE;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #DBEAFE; }
        """)
        self.select_all_btn.clicked.connect(self.select_all)
        tools_layout.addWidget(self.select_all_btn)

        self.deselect_all_btn = QPushButton("⬜ Bỏ chọn")
        self.deselect_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        tools_layout.addWidget(self.deselect_all_btn)

        self.select_visible_btn = QPushButton("🔍 Chọn các nhóm đang lọc")
        self.select_visible_btn.setStyleSheet("""
            QPushButton {
                background-color: #F5F3FF;
                color: #6D28D9;
                border: 1px solid #DDD6FE;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #EDE9FE; }
        """)
        self.select_visible_btn.clicked.connect(self.select_visible)
        tools_layout.addWidget(self.select_visible_btn)

        self.invert_selection_btn = QPushButton("🔄 Đảo chọn")
        self.invert_selection_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 11px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.invert_selection_btn.clicked.connect(self.invert_selection)
        tools_layout.addWidget(self.invert_selection_btn)

        tools_layout.addStretch()

        self.visible_count_label = QLabel(f"Hiển thị: {len(self.all_groups)} nhóm")
        self.visible_count_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        tools_layout.addWidget(self.visible_count_label)

        main_layout.addLayout(tools_layout)

        # 4. Group List Widget với Custom Item Delegate
        self.list_widget = QListWidget()
        self.list_widget.setItemDelegate(GroupItemDelegate(self.list_widget))
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                background-color: white;
            }
        """)
        self.list_widget.itemChanged.connect(self.on_item_changed)
        main_layout.addWidget(self.list_widget, stretch=1)

        # 5. Import Options (Append vs Replace)
        import_opts_layout = QHBoxLayout()
        import_opts_layout.setSpacing(16)
        
        mode_label = QLabel("<b>Chế độ nhập:</b>")
        mode_label.setStyleSheet("font-size: 12px; color: #374151;")
        import_opts_layout.addWidget(mode_label)

        self.radio_append = QRadioButton("➕ Thêm vào danh sách hiện tại (giữ nhóm cũ, khử trùng)")
        self.radio_append.setChecked(True)
        self.radio_append.setStyleSheet("font-size: 12px; color: #1F2937;")
        import_opts_layout.addWidget(self.radio_append)

        self.radio_replace = QRadioButton("🔄 Thay thế toàn bộ danh sách hiện tại")
        self.radio_replace.setStyleSheet("font-size: 12px; color: #1F2937;")
        import_opts_layout.addWidget(self.radio_replace)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.radio_append)
        self.mode_group.addButton(self.radio_replace)

        import_opts_layout.addStretch()
        main_layout.addLayout(import_opts_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.Shape.HLine)
        divider.setFrameShadow(QFrame.Shadow.Sunken)
        divider.setStyleSheet("color: #E5E7EB;")
        main_layout.addWidget(divider)

        # 6. Bottom Action Buttons
        btn_layout = QHBoxLayout()
        
        hint_label = QLabel("💡 <i>Nhấp vào bất kỳ hàng nào để tích chọn/bỏ chọn nhóm.</i>")
        hint_label.setStyleSheet("color: #6B7280; font-size: 11px;")
        btn_layout.addWidget(hint_label)

        btn_layout.addStretch()

        self.cancel_btn = QPushButton("❌ Hủy")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 7px 18px;
                font-size: 12px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #E5E7EB; color: #111827; }
        """)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.cancel_btn)

        self.import_btn = QPushButton("📥 Nhập nhóm đã chọn")
        self.import_btn.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: bold;
                border-radius: 4px;
                padding: 7px 22px;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.import_btn.clicked.connect(self.on_import_clicked)
        btn_layout.addWidget(self.import_btn)

        main_layout.addLayout(btn_layout)

    def populate_items(self):
        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        for g in self.all_groups:
            name = g.get("name") or "Nhóm chưa đặt tên"
            url = g.get("url") or ""

            item_text = f"{name} {url}"
            item = QListWidgetItem(item_text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            
            # Mặc định check chọn tất cả các nhóm
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, g)
            self.list_widget.addItem(item)

        self.list_widget.blockSignals(False)
        self.update_counts()

    def apply_filter(self):
        query = self.filter_input.text().strip()
        query_norm = _strip_accents(query)

        visible_count = 0
        self.list_widget.blockSignals(True)

        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.ItemDataRole.UserRole) or {}
            name = data.get("name", "")
            url = data.get("url", "")
            group_id = data.get("group_id", "")

            # Tìm kiếm không phân biệt dấu và hoa thường
            search_haystack = f"{name} {url} {group_id}"
            search_haystack_norm = _strip_accents(search_haystack)

            if not query or query_norm in search_haystack_norm or query.lower() in search_haystack.lower():
                item.setHidden(False)
                visible_count += 1
            else:
                item.setHidden(True)

        self.list_widget.blockSignals(False)
        self.visible_count_label.setText(f"Hiển thị: {visible_count}/{self.list_widget.count()} nhóm")

    def clear_filter(self):
        self.filter_input.clear()

    def select_all(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.CheckState.Checked)
        self.list_widget.blockSignals(False)
        self.list_widget.viewport().update()
        self.update_counts()

    def deselect_all(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(Qt.CheckState.Unchecked)
        self.list_widget.blockSignals(False)
        self.list_widget.viewport().update()
        self.update_counts()

    def select_visible(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)
        self.list_widget.blockSignals(False)
        self.list_widget.viewport().update()
        self.update_counts()

    def invert_selection(self):
        self.list_widget.blockSignals(True)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                new_state = Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked else Qt.CheckState.Checked
                item.setCheckState(new_state)
        self.list_widget.blockSignals(False)
        self.list_widget.viewport().update()
        self.update_counts()

    def on_item_changed(self, item):
        self.list_widget.viewport().update()
        self.update_counts()

    def update_counts(self):
        selected_count = len(self.get_selected_groups())
        total_count = self.list_widget.count()

        self.selected_badge.setText(f"Đã chọn: {selected_count} nhóm")
        self.import_btn.setText(f"📥 Nhập {selected_count} nhóm đã chọn" if selected_count > 0 else "📥 Nhập nhóm đã chọn")
        self.import_btn.setEnabled(selected_count > 0)

    def get_selected_groups(self) -> list[dict]:
        selected = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data:
                    selected.append(data)
        return selected

    def get_import_mode(self) -> str:
        return "replace" if self.radio_replace.isChecked() else "append"

    def on_import_clicked(self):
        selected = self.get_selected_groups()
        if not selected:
            QMessageBox.warning(self, "Chưa chọn nhóm", "Vui lòng tích chọn ít nhất một nhóm để nhập!")
            return
        self.accept()
