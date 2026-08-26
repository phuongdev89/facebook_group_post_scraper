from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QListWidget, QListWidgetItem, 
                             QDialog, QLineEdit, QDialogButtonBox)
from PyQt6.QtCore import Qt, pyqtSignal
from src.database.repository import save_all_groups, get_all_groups

class AddGroupDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Thêm Nhóm Facebook mới")
        self.setFixedWidth(420)
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("URL Nhóm hoặc Link Bài Viết:"))
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText("VD: https://www.facebook.com/groups/congdongin3d/ hoặc ID nhóm")
        self.url_input.editingFinished.connect(self._on_url_blur)
        layout.addWidget(self.url_input)

        layout.addWidget(QLabel("Tên Nhóm (Tự động điền khi nhập link):"))
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("VD: Cộng Đồng In 3D")
        layout.addWidget(self.name_input)
        
        self.resolved_group_id = ""

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_url_blur(self):
        from src.utils.helpers import resolve_group_details
        raw = self.url_input.text().strip()
        if not raw:
            return
        res = resolve_group_details(raw)
        if res.get("resolved") and res.get("group_id"):
            self.resolved_group_id = res["group_id"]
            self.url_input.setText(res["url"])
            if not self.name_input.text().strip() and res.get("name"):
                self.name_input.setText(res["name"])
        
    def get_data(self):
        return {
            "name": self.name_input.text().strip(),
            "url": self.url_input.text().strip(),
            "group_id": self.resolved_group_id
        }

class GroupListWidget(QWidget):
    groups_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.groups = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        btn_layout = QHBoxLayout()
        self.select_all_btn = QPushButton("Chọn tất cả")
        self.select_all_btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        self.select_all_btn.clicked.connect(self.select_all)
        btn_layout.addWidget(self.select_all_btn)
        
        self.deselect_all_btn = QPushButton("Bỏ chọn")
        self.deselect_all_btn.setStyleSheet("font-size: 11px; padding: 2px 6px;")
        self.deselect_all_btn.clicked.connect(self.deselect_all)
        btn_layout.addWidget(self.deselect_all_btn)
        
        btn_layout.addStretch()
        
        add_btn = QPushButton("➕ Thêm Nhóm")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-weight: bold;
                font-size: 11px;
                padding: 4px 8px;
                border-radius: 4px;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        add_btn.clicked.connect(self.open_add_dialog)
        btn_layout.addWidget(add_btn)
        
        layout.addLayout(btn_layout)
        
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(140)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                background-color: white;
            }
            QListWidget::item { padding: 4px; border-bottom: 1px solid #F3F4F6; }
        """)
        layout.addWidget(self.list_widget)
        
    def open_add_dialog(self):
        dlg = AddGroupDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data["url"]:
                if not data["name"]:
                    data["name"] = data["url"]
                self.groups.append(data)
                self.render_items()
                self.save_to_db()
                self.groups_changed.emit()
                
    def set_groups(self, groups: list):
        self.groups = list(groups)
        self.render_items()
        
    def get_selected_urls(self) -> list:
        urls = []
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                if data and data.get("url"):
                    urls.append(data["url"])
        return urls
        
    def render_items(self):
        self.list_widget.clear()
        for g in self.groups:
            name = g.get("name") or g.get("url") or ""
            url = g.get("url") or ""
            item = QListWidgetItem(f"{name} ({url})")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked)
            item.setData(Qt.ItemDataRole.UserRole, g)
            self.list_widget.addItem(item)
            
    def select_all(self):
        for idx in range(self.list_widget.count()):
            self.list_widget.item(idx).setCheckState(Qt.CheckState.Checked)
            
    def deselect_all(self):
        for idx in range(self.list_widget.count()):
            self.list_widget.item(idx).setCheckState(Qt.CheckState.Unchecked)
            
    def save_to_db(self):
        save_all_groups(self.groups)
