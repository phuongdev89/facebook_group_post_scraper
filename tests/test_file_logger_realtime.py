import os
import time
import tempfile
import unittest
from unittest.mock import patch


class TestFileLoggerRealtime(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir_patch = patch("src.utils.file_logger.DATA_DIR", self.temp_dir.name)
        self.data_dir_patch.start()
        
        # Reset file_logger state
        import src.utils.file_logger as fl
        fl._initialized = False
        fl._access_logger = None
        fl._error_logger = None

    def tearDown(self):
        # Close all handlers to allow temp directory cleanup
        import src.utils.file_logger as fl
        for lg in (fl._access_logger, fl._error_logger):
            if lg:
                for h in lg.handlers[:]:
                    h.close()
                    lg.removeHandler(h)
        fl._initialized = False
        self.data_dir_patch.stop()
        self.temp_dir.cleanup()

    def test_realtime_access_log_write_and_fsync(self):
        from src.utils.file_logger import add_log, get_log_paths
        
        paths = get_log_paths()
        access_path = paths["access"]
        
        test_msg = f"TEST_REALTIME_ACCESS_{time.time()}"
        add_log(test_msg, level="INFO", module="TEST_MODULE")
        
        # Verify file exists and contains content immediately without closing logger
        self.assertTrue(os.path.exists(access_path))
        with open(access_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn(test_msg, content)
        self.assertIn("[TEST_MODULE]", content)

    def test_realtime_error_log_write_and_detection(self):
        from src.utils.file_logger import add_log, get_log_paths
        
        paths = get_log_paths()
        access_path = paths["access"]
        error_path = paths["error"]
        
        error_msg = f"❌ Lỗi kết nối mạng bất ngờ_{time.time()}"
        add_log(error_msg, level="INFO", module="NETWORK")
        
        # Should be detected as error and written to both access.log and error.log
        self.assertTrue(os.path.exists(error_path))
        with open(error_path, "r", encoding="utf-8") as f:
            error_content = f.read()
        self.assertIn(error_msg, error_content)
        self.assertIn("[NETWORK]", error_content)
        
        with open(access_path, "r", encoding="utf-8") as f:
            access_content = f.read()
        self.assertIn(error_msg, access_content)

    def test_app_icon_loads_successfully(self):
        from src.utils.helpers import get_app_icon_path, get_app_icon
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QIcon
        
        # Ensure QApplication instance exists for QIcon
        app = QApplication.instance() or QApplication([])
        
        icon_path = get_app_icon_path()
        self.assertTrue(os.path.exists(icon_path), f"Icon path not found: {icon_path}")
        
        icon = get_app_icon()
        self.assertIsInstance(icon, QIcon)
        self.assertFalse(icon.isNull(), "QIcon should not be null")


if __name__ == "__main__":
    unittest.main()
