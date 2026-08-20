import time
import re
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.proxy_utils import select_proxy
from src.core.comment_scraper import fetch_comments
import src.core.comment_scraper as comment_scraper
from src.database.repository import get_post_by_id, save_or_update_post
from src.ui.workers.ai_worker import AIAnalysisWorker


class CommentUpdateWorker(QThread):
    """Luồng nền cập nhật bình luận cho các bài viết đã chọn hoặc trong 24h, kèm đẩy vào AI queue"""
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

        self.ai_worker = AIAnalysisWorker(self.ai_config, self.telegram_config)
        self.ai_worker.log_signal.connect(self.log)

    def stop(self):
        """Yêu cầu dừng worker"""
        self.stop_requested = True
        self.log("🛑 Nhận được yêu cầu DỪNG cập nhật bình luận...")
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()

    def log(self, message: str):
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

    def check_keyword_match(self, post_data: dict, comments_data: list, keywords: list[str]) -> tuple[bool, str, str]:
        """Kiểm tra bài viết hoặc các bình luận mới có chứa từ khóa lọc không"""
        if not keywords:
            return True, "", ""

        # 1. Kiểm tra nội dung bài viết
        post_text = (post_data.get("message") or post_data.get("text") or "").lower()
        for kw in keywords:
            kw_clean = kw.strip().lower()
            if kw_clean and kw_clean in post_text:
                return True, kw, "Bài viết"

        # 2. Kiểm tra bình luận và reply
        for c in comments_data:
            c_text = (c.get("text") or "").lower()
            for kw in keywords:
                kw_clean = kw.strip().lower()
                if kw_clean and kw_clean in c_text:
                    return True, kw, "Bình luận"

            replies = c.get("replies") or []
            for r in replies:
                r_text = (r.get("text") or "").lower()
                for kw in keywords:
                    kw_clean = kw.strip().lower()
                    if kw_clean and kw_clean in r_text:
                        return True, kw, "Phản hồi bình luận"

        return False, "", ""

    def run(self):
        try:
            self._apply_proxy()
            if self.fb_dtsg:
                comment_scraper.FB_DTSG = self.fb_dtsg
            self.ai_worker.start()

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
                    comments, _ = fetch_comments(post_id, cookies=self.cookies)
                    self.log(f"  ✓ Đã lấy {len(comments)} bình luận cho bài {post_id}")

                    # Cập nhật vào SQLite
                    post_type = post_data.get("post_type", "group_post")
                    save_or_update_post(post_type, post_id, post_data, comments)
                    updated_count += 1
                    self.post_status_signal.emit(post_id, "done", len(comments))

                    # Kiểm tra khớp từ khóa & đẩy vào queue AI
                    matched, kw_hit, kw_source = self.check_keyword_match(post_data, comments, self.keywords)
                    if matched:
                        if self.keywords:
                            self.log(f"  🎯 Khớp từ khóa '{kw_hit}' tại {kw_source}!")
                        self.ai_worker.enqueue(post_data, comments, kw_hit, kw_source)
                        self.log(f"  ⚡ Đã chuyển bài {post_id} và các bình luận mới vào hàng đợi phân tích AI song song")
                    else:
                        self.log(f"  ⏭ Không khớp từ khóa lọc, bỏ qua phân tích AI cho bài {post_id}")

                    time.sleep(0.3)
                except Exception as ex:
                    self.log(f"  ❌ Lỗi khi cập nhật bình luận bài {post_id}: {ex}")
                    self.post_status_signal.emit(post_id, "error", 0)

                self.progress_signal.emit(idx, total)

            # Chờ queue AI hoàn thành tất cả tác vụ
            self.log("⏳ Đang chờ hoàn tất các tác vụ phân tích AI và thông báo Telegram trong hàng đợi...")
            self.ai_worker.task_queue.join()

            if self.stop_requested:
                self.finished_signal.emit(True, f"Đã DỪNG tiến trình cập nhật bình luận ({updated_count}/{total} bài).")
            else:
                self.finished_signal.emit(True, f"Đã hoàn thành cập nhật bình luận cho {updated_count}/{total} bài viết.")
        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi trong quá trình cập nhật bình luận: {e}")
        finally:
            if self.ai_worker and self.ai_worker.isRunning():
                self.ai_worker.stop()
                self.ai_worker.wait(3000)
