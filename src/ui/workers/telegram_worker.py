import time
import threading
from PyQt6.QtCore import QThread, pyqtSignal
import src.database as database
from src.core.telegram_notifier import send_keyword_match_alert
from src.utils.file_logger import add_log


class TelegramDispatcherThread(QThread):
    """
    Background Thread chuyên trách quét SQLite database định kỳ:
    - Tìm các bài viết/phân tích AI đã xác nhận should_notify = 1 nhưng chưa gửi Telegram (telegram_sent = 0 hoặc NULL).
    - Tự động gửi cảnh báo sang Telegram Bot theo cấu hình trong SQLite settings.
    - Cập nhật trạng thái telegram_sent = 1 trong database sau khi gửi thành công.
    - Đảm bảo 100% không bị mất thông báo dù scraper dừng hoặc gặp sự cố mạng.
    """
    notification_sent_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str)

    def __init__(self, check_interval: int = 5):
        super().__init__()
        self.check_interval = check_interval
        self.stop_requested = False
        self._wake_event = threading.Event()
        self._last_warn_time = 0

    def stop(self):
        """Dừng thread khi đóng ứng dụng"""
        self.stop_requested = True
        self._wake_event.set()

    def trigger_check_now(self):
        """Kích hoạt quét DB và gửi ngay lập tức mà không cần chờ hết chu kỳ sleep"""
        self._wake_event.set()

    def log(self, message: str):
        self.log_signal.emit(message)
        add_log(message, level="INFO", module="TELEGRAM_DISPATCHER")

    def run(self):
        self.log("🚀 [Telegram Dispatcher] Thread quét DB & tự động gửi Telegram đã khởi động.")
        
        while not self.stop_requested:
            try:
                # 1. Lấy danh sách các bài viết cần gửi Telegram
                pending_analyses = database.get_pending_telegram_analyses(limit=5)
                
                if pending_analyses:
                    # 2. Đọc cấu hình Telegram mới nhất từ SQLite
                    settings = database.get_all_settings()
                    tg_enabled = settings.get("telegram_enabled") == "1"
                    tg_token = settings.get("telegram_token", "").strip()
                    tg_chat_id = settings.get("telegram_chat_id", "").strip()
                    notify_on_keyword = settings.get("notify_on_keyword", "1") in ("1", "True", True)

                    if tg_enabled and tg_token and tg_chat_id:
                        for item in pending_analyses:
                            if self.stop_requested:
                                break

                            analysis_id = item.get("id")
                            post_id = str(item.get("post_id", "N/A"))
                            group_name = item.get("group_name") or item.get("post_group_name") or item.get("post_page_name") or "Facebook Post"
                            post_msg = item.get("post_message") or item.get("seller_snippet") or ""
                            permalink = item.get("permalink") or f"https://www.facebook.com/{post_id}"

                            post_data = {
                                "post_id": post_id,
                                "group_name": group_name,
                                "message": post_msg,
                                "permalink": permalink
                            }

                            matched_kw = item.get("matched_keyword") or ""
                            matched_src = item.get("matched_source") or "Bài viết"
                            model_used = item.get("model_used") or ""

                            ai_result = {
                                "should_notify": True,
                                "target_name": item.get("target_name") or item.get("device_name") or "",
                                "price": item.get("price") or "",
                                "actor_role": item.get("actor_role") or item.get("seller_type") or "",
                                "matched_snippet": item.get("matched_snippet") or item.get("seller_snippet") or "",
                                "reason": item.get("reason") or ""
                            }

                            self.log(f"📱 [Telegram Dispatcher] Đang gửi thông báo cho bài {post_id} sang Telegram...")
                            ok, msg = send_keyword_match_alert(
                                token=tg_token,
                                chat_id=tg_chat_id,
                                post_data=post_data,
                                matched_keyword=matched_kw,
                                matched_type=matched_src,
                                ai_result=ai_result,
                                model_used=model_used
                            )

                            if ok:
                                database.mark_telegram_analysis_sent(analysis_id, status=1)
                                self.log(f"✅ [Telegram Dispatcher] Gửi thành công thông báo Telegram cho bài {post_id}.")
                                item["telegram_sent"] = 1
                                self.notification_sent_signal.emit(item)
                                time.sleep(1.0)
                            else:
                                database.mark_telegram_analysis_sent(analysis_id, status=-1)
                                self.log(f"⚠️ [Telegram Dispatcher] Không gửi được Telegram cho bài {post_id}: {msg}. Đã đánh dấu Lỗi (Bấm 'Gửi lại Telegram' trên bảng AI để thử lại).")
                                item["telegram_sent"] = -1
                                self.notification_sent_signal.emit(item)
                                time.sleep(1.5)
                    else:
                        # Telegram chưa được cấu hình hoặc bị tắt
                        now = time.time()
                        if now - self._last_warn_time > 60:
                            self.log(f"ℹ️ [Telegram Dispatcher] Có {len(pending_analyses)} bài viết chờ gửi nhưng Telegram chưa được bật hoặc thiếu Token/Chat ID.")
                            self._last_warn_time = now

            except Exception as e:
                self.log(f"❌ [Telegram Dispatcher] Lỗi trong luồng quét DB: {e}")

            # Chờ chu kỳ tiếp theo hoặc sự kiện kích hoạt tức thì
            self._wake_event.wait(timeout=self.check_interval)
            self._wake_event.clear()

        self.log("🛑 [Telegram Dispatcher] Thread đã dừng.")
