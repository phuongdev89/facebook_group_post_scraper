import os
import shutil
import tempfile
import unittest
from src.config.constants import (
    DATA_DIR,
    DEFAULT_DB_PATH,
    CHROME_DATA_DIR,
    LEGACY_DATA_DIR,
    LEGACY_DB_PATH,
    ensure_data_dir
)
from src.database.repository import (
    migrate_legacy_database,
    init_db,
    save_or_update_post,
    get_post_by_id
)


class TestDataDirAndMigration(unittest.TestCase):
    def test_constants_structure(self):
        """Kiểm tra đường dẫn DATA_DIR và CHROME_DATA_DIR trỏ tới ~/.facebook-notification"""
        user_home = os.path.expanduser("~")
        expected_data_dir = os.path.join(user_home, ".facebook-notification")
        self.assertEqual(DATA_DIR, expected_data_dir)
        self.assertEqual(DEFAULT_DB_PATH, os.path.join(expected_data_dir, "facebook_scraper.sqlite"))
        self.assertEqual(CHROME_DATA_DIR, os.path.join(expected_data_dir, "chromedata"))

    def test_ensure_data_dir(self):
        """Kiểm tra hàm ensure_data_dir tạo thư mục thành công"""
        d = ensure_data_dir()
        self.assertTrue(os.path.exists(d))

    def test_migration_logic(self):
        """Kiểm tra logic migrate_legacy_database copy đúng file database cũ sang đích"""
        with tempfile.TemporaryDirectory() as tmpdir:
            legacy_file = os.path.join(tmpdir, "legacy.sqlite")
            target_file = os.path.join(tmpdir, "new_home", "target.sqlite")

            # Khởi tạo legacy database với 1 bản ghi
            init_db(legacy_file)
            save_or_update_post("group_post", "migrated_123", {
                "post_id": "migrated_123",
                "message": "Legacy post test",
                "group_name": "Test Group"
            }, [], db_path=legacy_file)

            # Đảm bảo target chưa tồn tại
            self.assertFalse(os.path.exists(target_file))

            # Thực hiện migration
            migrated = migrate_legacy_database(target_db_path=target_file, legacy_db_path=legacy_file)
            self.assertTrue(migrated)
            self.assertTrue(os.path.exists(target_file))

            # Đọc lại từ database đích
            post = get_post_by_id("migrated_123", db_path=target_file)
            self.assertIsNotNone(post)
            self.assertEqual(post["message"], "Legacy post test")

            # Chạy lại migration khi target đã tồn tại -> phải trả về False và không ghi đè lỗi
            migrated_second = migrate_legacy_database(target_db_path=target_file, legacy_db_path=legacy_file)
            self.assertFalse(migrated_second)


if __name__ == "__main__":
    unittest.main()
