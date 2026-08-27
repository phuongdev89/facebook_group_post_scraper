import time
import re
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.proxy_utils import select_proxy
from src.core.comment_scraper import fetch_comments
import src.core.comment_scraper as comment_scraper
from src.database.repository import (
    get_post_by_id,
    save_or_update_post,
    mark_post_ai_pending,
    ai_analysis_exists
)


class CommentUpdateWorker(QThread):
    """
    Luồng nền cập nhật bình luận nhanh:
    - Chỉ lấy bình luận & reply và lưu SQLite với tốc độ cao nhất.
    - Bài viết khớp từ khóa được đưa vào hàng đợi SQLite (ai_status = 1) để AI Worker xử lý ngầm trong thread riêng.
    """
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)        # current, total
    finished_signal = pyqtSignal(bool, str)       # success, message
    post_status_signal = pyqtSignal(str, str, int) # post_id, status ('updating'|'done'|'error'), comment_count

    def __init__(self, post_ids: list[str], cookies=None, fb_dtsg=None, telegram_config=None, ai_config=None, keywords=None):
        super().__init__()
        self.post_ids = [str(pid) for pid in post_ids if pid]
        self.cookies = cookies or {}
        self.fb_dtsg = fb_dtsg or ""
        self.telegram_config = telegram_config or {}
        self.ai_config = ai_config or {}
        self.keywords = keywords or []
        self.stop_requested = False

    def stop(self):
        """Yêu cầu dừng worker"""
        self.stop_requested = True
        self.log("🛑 Nhận được yêu cầu DỪNG cập nhật bình luận...")

    def log(self, message: str):
        from src.utils.file_logger import add_log
        add_log(message, module="COMMENT_UPDATER")
        self.log_signal.emit(message)

    def _apply_proxy(self):
        has_cookies = bool(self.cookies)
        proxies = select_proxy(has_cookies)
        if proxies:
            proxy_url = proxies.get('http', '')
            if has_cookies:
                port = re.search(r':(\d+)$', proxy_url)
                port_str = port.group(1) if port else '?'
                self.log(f"🔒 Proxy: STATIC (cookie session) — port {port_str}")
            else:
                self.log(f"🔄 Proxy: ROTATING — {proxy_url}")
        else:
            self.log("⚠️ No proxy configured")

        comment_scraper.PROXIES = proxies

    def check_keyword_match(self, post_data: dict, comments_data: list, keywords: list[str]) -> tuple[bool, str, str, str | None]:
        """Kiểm tra bài viết hoặc các bình luận mới có chứa từ khóa lọc không, trả về (matched, kw, source, comment_id)"""
        if not keywords:
            return True, "", "", None

        # 1. Kiểm tra nội dung bài viết
        post_text = (post_data.get("message") or post_data.get("text") or "").lower()
        for kw in keywords:
            kw_clean = kw.strip().lower()
            if kw_clean and kw_clean in post_text:
                return True, kw, "Bài viết", None

        # 2. Kiểm tra bình luận và reply
        for c in comments_data:
            c_text = (c.get("text") or "").lower()
            for kw in keywords:
                kw_clean = kw.strip().lower()
                if kw_clean and kw_clean in c_text:
                    c_id = str(c.get("comment_id") or c.get("id") or "")
                    return True, kw, "Bình luận", c_id if c_id else None

            replies = c.get("replies") or []
            for r in replies:
                r_text = (r.get("text") or "").lower()
                for kw in keywords:
                    kw_clean = kw.strip().lower()
                    if kw_clean and kw_clean in r_text:
                        r_id = str(r.get("reply_id") or r.get("id") or c.get("comment_id") or "")
                        return True, kw, "Phản hồi bình luận", r_id if r_id else None

        return False, "", "", None

    def run(self):
        try:
            self._apply_proxy()
            if self.fb_dtsg:
                comment_scraper.FB_DTSG = self.fb_dtsg

            total = len(self.post_ids)
            updated_count = 0
            self.log(f"\n=======================================================")
            self.log(f"🔄 BẮT ĐẦU CẬP NHẬT BÌNH LUẬN CHO {total} BÀI VIẾT")
            self.log(f"=======================================================")

            for idx, post_id in enumerate(self.post_ids, 1):
                if self.stop_requested:
                    break

                self.post_status_signal.emit(post_id, "updating", 0)
                self.log(f"\n[{idx}/{total}] 🔄 Đang lấy bình luận mới cho bài viết ID: {post_id}...")
                post_record = get_post_by_id(post_id)
                post_data = post_record or {"post_id": post_id}

                try:
                    comments, _ = fetch_comments(
                        post_id,
                        cookies=self.cookies,
                        fb_dtsg=self.fb_dtsg,
                        logger=self.log
                    )
                    self.log(f"  ✓ Đã lấy {len(comments)} bình luận cho bài {post_id}")

                    # Cập nhật bình luận vào SQLite
                    post_type = post_data.get("post_type", "group_post")
                    save_or_update_post(post_type, post_id, post_data, comments)
                    updated_count += 1

                    # Kiểm tra khớp từ khóa -> đưa vào hàng đợi AI
                    matched, kw_hit, kw_source, kw_comment_id = self.check_keyword_match(post_data, comments, self.keywords)
                    if matched:
                        if ai_analysis_exists(post_id, kw_comment_id):
                            self.log(f"  ℹ️ Khớp từ khóa '{kw_hit}' tại {kw_source} (ID: {kw_comment_id or post_id}) nhưng đã được phân tích AI trước đó -> Bỏ qua.")
                        else:
                            if self.keywords:
                                self.log(f"  🎯 Khớp từ khóa '{kw_hit}' tại {kw_source}! Đã chuyển vào hàng đợi phân tích AI ngầm.")
                            mark_post_ai_pending(post_id, kw_hit, kw_source, kw_comment_id)
                    else:
                        self.log(f"  ⏭ Không khớp từ khóa lọc.")

                    self.post_status_signal.emit(post_id, "done", len(comments))
                    time.sleep(0.1)

                except Exception as ex:
                    self.log(f"  ❌ Lỗi khi cập nhật bình luận bài {post_id}: {ex}")
                    self.post_status_signal.emit(post_id, "error", 0)

                self.progress_signal.emit(idx, total)

            if self.stop_requested:
                self.finished_signal.emit(True, f"Đã DỪNG tiến trình cập nhật bình luận ({updated_count}/{total} bài).")
            else:
                self.finished_signal.emit(True, f"Đã hoàn thành cập nhật bình luận cho {updated_count}/{total} bài viết. Các bài khớp từ khóa đang được AI phân tích ngầm.")
        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi trong quá trình cập nhật bình luận: {e}")
