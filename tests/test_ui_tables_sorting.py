import unittest
from PyQt6.QtWidgets import QApplication, QHeaderView
from PyQt6.QtCore import Qt
from src.ui.app import FacebookNotificationUI, SmartTableWidgetItem


class TestUITablesSortingAndLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.window = FacebookNotificationUI()

    def tearDown(self):
        self.window.close()

    def test_smart_table_widget_item_sorting(self):
        # 1. Numeric sorting
        item1 = SmartTableWidgetItem("10", sort_key=10)
        item2 = SmartTableWidgetItem("2", sort_key=2)
        item3 = SmartTableWidgetItem("100", sort_key=100)
        self.assertTrue(item2 < item1)
        self.assertTrue(item1 < item3)

        # 2. Text natural sorting
        item_a = SmartTableWidgetItem("Apple")
        item_b = SmartTableWidgetItem("banana")
        self.assertTrue(item_a < item_b)

    def test_history_table_column_layout_and_sorting(self):
        table = self.window.history_table
        header = table.horizontalHeader()

        # Sorting enabled
        self.assertTrue(table.isSortingEnabled())
        self.assertTrue(header.isSortIndicatorShown())
        self.assertTrue(header.sectionsClickable())

        # Column 3 (Nhóm / Trang) is interactive/fixed width
        self.assertEqual(header.sectionResizeMode(3), QHeaderView.ResizeMode.Interactive)
        self.assertEqual(table.columnWidth(3), 150)

        # Column 4 (Nội dung bài viết) is Stretch
        self.assertEqual(header.sectionResizeMode(4), QHeaderView.ResizeMode.Stretch)

        # Text elision mode is ElideRight
        self.assertEqual(table.textElideMode(), Qt.TextElideMode.ElideRight)

    def test_ai_analysis_table_column_layout_and_sorting(self):
        table = self.window.ai_analysis_table
        header = table.horizontalHeader()

        # Sorting enabled
        self.assertTrue(table.isSortingEnabled())
        self.assertTrue(header.isSortIndicatorShown())
        self.assertTrue(header.sectionsClickable())

        # Column 3 (Nhóm / Trang) is interactive 130px
        self.assertEqual(header.sectionResizeMode(3), QHeaderView.ResizeMode.Interactive)
        self.assertEqual(table.columnWidth(3), 130)

        # Column 6 (Mục tiêu / Nhu cầu) is interactive 130px
        self.assertEqual(header.sectionResizeMode(6), QHeaderView.ResizeMode.Interactive)
        self.assertEqual(table.columnWidth(6), 130)

        # Column 9 (Trích đoạn) and Column 10 (Đánh giá) are Stretch
        self.assertEqual(header.sectionResizeMode(9), QHeaderView.ResizeMode.Stretch)
        self.assertEqual(header.sectionResizeMode(10), QHeaderView.ResizeMode.Stretch)

        # Text elision mode is ElideRight
        self.assertEqual(table.textElideMode(), Qt.TextElideMode.ElideRight)


if __name__ == "__main__":
    unittest.main()
