from PyQt6.QtCore import QThread, pyqtSignal
from src.core.group_fetcher import fetch_user_joined_groups, fetch_groups_via_browser


class GroupFetchWorker(QThread):
    """Worker chạy ngầm để lấy danh sách nhóm Facebook qua Cookies mà không làm đơ giao diện"""
    log_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(list, str)  # (groups_list, error_message)

    def __init__(self, cookies: dict, fb_dtsg: str = "", max_pages: int = 40, proxy=None, use_browser: bool = False, parent=None):
        super().__init__(parent)
        self.cookies = cookies or {}
        self.fb_dtsg = fb_dtsg or ""
        self.max_pages = max_pages
        self.proxy = proxy
        self.use_browser = use_browser
        self._is_stopped = False

    def stop(self):
        self._is_stopped = True

    def log(self, msg: str):
        from src.utils.file_logger import add_log
        add_log(msg, module="GROUP_FETCHER")
        self.log_signal.emit(msg)
        self.status_signal.emit(msg)

    def run(self):
        try:
            if not self.cookies:
                self.finished_signal.emit([], "Không có Cookies Facebook để thực hiện.")
                return

            if self.use_browser:
                self.status_signal.emit("Đang mở trình duyệt tự động để tải toàn bộ danh sách nhóm...")
                groups = fetch_groups_via_browser(
                    cookies=self.cookies,
                    logger=self.log,
                    headless=False,
                    max_scrolls=50
                )
            else:
                self.status_signal.emit("Đang kết nối tới Facebook...")
                groups = fetch_user_joined_groups(
                    cookies=self.cookies,
                    fb_dtsg=self.fb_dtsg,
                    max_pages=self.max_pages,
                    logger=self.log,
                    proxy=self.proxy,
                    allow_browser_fallback=True
                )
            
            if self._is_stopped:
                return

            self.finished_signal.emit(groups, "")
        except Exception as e:
            self.log(f"❌ Lỗi khi tải danh sách nhóm: {str(e)}")
            self.finished_signal.emit([], str(e))
