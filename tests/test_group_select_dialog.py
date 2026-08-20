import sys
import unittest
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from src.ui.dialogs.group_select_dialog import GroupSelectDialog, _strip_accents

app = QApplication.instance() or QApplication(sys.argv)


class TestGroupSelectDialog(unittest.TestCase):

    def setUp(self):
        self.sample_groups = [
            {"name": "Lập Trình Python Việt Nam", "url": "https://www.facebook.com/groups/laptrinhpython/", "group_id": "111"},
            {"name": "Cộng Đồng Machine Learning & AI", "url": "https://www.facebook.com/groups/machinelearning/", "group_id": "222"},
            {"name": "Chợ Mua Bán Đồ Điện Tử", "url": "https://www.facebook.com/groups/333444555/", "group_id": "333444555"},
            {"name": "Hội Yêu Thích Công Nghệ", "url": "https://www.facebook.com/groups/congnghe/", "group_id": "444"},
        ]

    def test_strip_accents(self):
        self.assertEqual(_strip_accents("Lập Trình Python"), "lap trinh python")
        self.assertEqual(_strip_accents("Đồ Cũ"), "do cu")
        self.assertEqual(_strip_accents("Cộng Đồng AI"), "cong dong ai")

    def test_dialog_init_and_selection(self):
        dlg = GroupSelectDialog(self.sample_groups)
        self.assertEqual(dlg.list_widget.count(), 4)

        # Mặc định tất cả được chọn
        selected = dlg.get_selected_groups()
        self.assertEqual(len(selected), 4)

        # Bỏ chọn tất cả
        dlg.deselect_all()
        self.assertEqual(len(dlg.get_selected_groups()), 0)

        # Chọn tất cả lại
        dlg.select_all()
        self.assertEqual(len(dlg.get_selected_groups()), 4)

        # Đảo chọn
        dlg.list_widget.item(0).setCheckState(Qt.CheckState.Unchecked)
        self.assertEqual(len(dlg.get_selected_groups()), 3)
        dlg.invert_selection()
        self.assertEqual(len(dlg.get_selected_groups()), 1)
        self.assertEqual(dlg.get_selected_groups()[0]["group_id"], "111")

    def test_filter_realtime(self):
        dlg = GroupSelectDialog(self.sample_groups)

        # Lọc không dấu "lap trinh" -> chỉ khớp "Lập Trình Python Việt Nam"
        dlg.filter_input.setText("lap trinh")
        visible_items = [dlg.list_widget.item(i) for i in range(dlg.list_widget.count()) if not dlg.list_widget.item(i).isHidden()]
        self.assertEqual(len(visible_items), 1)
        data = visible_items[0].data(Qt.ItemDataRole.UserRole)
        self.assertEqual(data["name"], "Lập Trình Python Việt Nam")

        # Lọc theo ID số "333444" -> khớp "Chợ Mua Bán Đồ Điện Tử"
        dlg.filter_input.setText("333444")
        visible_items = [dlg.list_widget.item(i) for i in range(dlg.list_widget.count()) if not dlg.list_widget.item(i).isHidden()]
        self.assertEqual(len(visible_items), 1)
        data = visible_items[0].data(Qt.ItemDataRole.UserRole)
        self.assertEqual(data["group_id"], "333444555")

        # Xóa bộ lọc -> hiển thị lại toàn bộ
        dlg.clear_filter()
        visible_items = [dlg.list_widget.item(i) for i in range(dlg.list_widget.count()) if not dlg.list_widget.item(i).isHidden()]
        self.assertEqual(len(visible_items), 4)

    def test_import_mode(self):
        dlg = GroupSelectDialog(self.sample_groups)
        self.assertEqual(dlg.get_import_mode(), "append")

        dlg.radio_replace.setChecked(True)
        self.assertEqual(dlg.get_import_mode(), "replace")


if __name__ == "__main__":
    unittest.main()
