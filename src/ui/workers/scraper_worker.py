import time
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.proxy_utils import select_proxy
from src.core.group_scraper import fetch_posts as fetch_group_posts
from src.core.comment_scraper import fetch_comments
from src.utils.helpers import extract_group_id_from_url
from src.database.repository import save_or_update_post, mark_post_ai_pending, update_group_last_scraped
from src.ui.workers.ai_worker import AIAnalysisWorker

# group_scraper dùng global state (COOKIES, FB_DTSG) nên serialize fetch_posts,
# nhưng parallel hóa fetch_comments cho mỗi bài trong cùng 1 nhóm.
# ponytail: refactor group_scraper sang thread-local state để parallel groups thực sự
_SCRAPE_LOCK = threading.Lock()
MAX_COMMENT_WORKERS = 4  # parallel fetch comments trong 1 nhóm

class ScraperThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)
    finished_signal = pyqtSignal(bool, str)
    
    def __init__(self, params, cookies=None, fb_dtsg=None, telegram_config=None, ai_config=None):
        super().__init__()
        self.params = params
        self.cookies = cookies or {}
        self.fb_dtsg = fb_dtsg or ""
        self.telegram_config = telegram_config or {}
        self.ai_config = ai_config or {}
        self.stop_requested = False
        
        self.ai_worker = AIAnalysisWorker(self.ai_config, self.telegram_config)
        self.ai_worker.log_signal.connect(self.log)
    
    def stop(self):
        self.stop_requested = True
        self.log("🛑 Nhận được yêu cầu DỪNG. Đang dừng cào...")
        if self.ai_worker and self.ai_worker.isRunning():
            self.ai_worker.stop()

    def log(self, message):
        from src.utils.file_logger import add_log
        add_log(message, module="SCRAPER")
        self.log_signal.emit(message)

    def _apply_proxy(self):
        has_cookies = bool(self.cookies)
        proxies = select_proxy(has_cookies)
        if proxies:
            proxy_url = proxies['http']
            if has_cookies:
                port = re.search(r':(\d+)$', proxy_url)
                port_str = port.group(1) if port else '?'
                self.log(f"🔒 Proxy: STATIC (cookie session) — port {port_str}")
            else:
                self.log(f"🔄 Proxy: ROTATING — {proxy_url}")
        else:
            self.log("⚠️  No proxy configured")

        # Đồng bộ proxy tới tất cả scraper modules
        import src.core.comment_scraper as comment_scraper
        import src.core.group_scraper as group_scraper
        import src.core.page_scraper as page_scraper
        import src.core.media_scraper as media_scraper
        comment_scraper.PROXIES = proxies
        group_scraper.PROXIES = proxies
        page_scraper.PROXIES = proxies
        media_scraper.PROXIES = proxies

    def _scrape_one_group(self, group_item, idx, total_groups, post_count, min_comments, keywords):
        """Cào một nhóm — fetch_posts serialize (global state), fetch_comments parallel."""
        if self.stop_requested:
            return 0

        if isinstance(group_item, dict):
            group_url = group_item.get("url", "")
            configured_name = group_item.get("name", "").strip()
            raw_gid = str(group_item.get("group_id") or "").strip()
        else:
            group_url = str(group_item)
            configured_name = ""
            raw_gid = ""

        self.log(f"\n[Nhóm {idx+1}/{total_groups}] Đang quét: {group_url}")
        if not raw_gid or not raw_gid.isdigit():
            self.log(f"🔄 Đang tự động phân giải Group ID cho: {group_url}...")
            group_id = extract_group_id_from_url(group_url, self.cookies)
        else:
            group_id = raw_gid

        if not group_id:
            self.log(f"❌ Không tìm thấy Group ID cho: {group_url}. (Gợi ý: Cấu hình Cookie nếu đây là nhóm kín/riêng tư).")
            return 0

        self.log(f"🔍 Group ID: {group_id}")
        update_group_last_scraped(group_id)
        if group_url:
            update_group_last_scraped(group_url)

        # group_scraper dùng global state — serialize để tránh race condition
        with _SCRAPE_LOCK:
            posts = fetch_group_posts(
                group_id=group_id,
                group_name=configured_name,
                limit=post_count,
                target_count=post_count,
                cookies=self.cookies,
                fb_dtsg=self.fb_dtsg,
                logger=self.log
            )

        if not posts:
            self.log(f"⚠️ Không lấy được bài viết nào từ nhóm {group_id}")
            return 0

        self.log(f"📄 Tìm thấy {len(posts)} bài viết từ nhóm {group_id}. Đang lấy bình luận song song...")

        def fetch_one_post_comments(post):
            if self.stop_requested:
                return post, []
            post_id = post.get("post_id")
            if not post_id:
                return post, []
            if configured_name and not post.get("group_name"):
                post["group_name"] = configured_name
            try:
                target_cmt_count = max(min_comments, 20)
                comments, _ = fetch_comments(
                    post_id,
                    target_count=target_cmt_count,
                    cookies=self.cookies,
                    fb_dtsg=self.fb_dtsg,
                    logger=self.log
                )
                return post, comments
            except Exception as e:
                self.log(f"⚠️ Lỗi lấy comment bài {post_id}: {e}")
                return post, []

        saved = 0
        with ThreadPoolExecutor(max_workers=MAX_COMMENT_WORKERS) as pool:
            futs = {pool.submit(fetch_one_post_comments, p): p for p in posts}
            for fut in as_completed(futs):
                if self.stop_requested:
                    pool.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    post, comments = fut.result()
                except Exception as e:
                    self.log(f"⚠️ Lỗi xử lý bài: {e}")
                    continue

                post_id = post.get("post_id")
                if not post_id:
                    continue

                save_or_update_post(
                    post_type="group_post",
                    post_id=post_id,
                    post_data=post,
                    comments_data=comments
                )
                saved += 1

                kw_hit = None
                kw_source = "Bài viết"
                post_msg = (post.get("message") or post.get("text") or "").lower()
                for kw in keywords:
                    if kw.lower() in post_msg:
                        kw_hit = kw
                        break

                if not kw_hit and comments:
                    for c in comments:
                        c_text = (c.get("text") or "").lower()
                        for kw in keywords:
                            if kw.lower() in c_text:
                                kw_hit = kw
                                kw_source = "Bình luận"
                                break
                        if kw_hit:
                            break

                if kw_hit:
                    self.log(f"   🎯 Khớp từ khóa '{kw_hit}' ({kw_source}) tại bài {post_id} -> Đưa vào hàng đợi AI.")
                    mark_post_ai_pending(post_id, kw_hit, kw_source)
                    self.ai_worker.enqueue(post, comments, kw_hit, kw_source)

        return saved

    def run(self):
        self.ai_worker.start()
        try:
            self._apply_proxy()
            start_time = time.time()
            groups = self.params.get("groups") or self.params.get("group_urls") or self.params.get("urls") or []
            post_count = self.params.get("count") or self.params.get("post_count") or 5
            min_comments = self.params.get("min_comments", 0)
            keywords = self.params.get("keywords", [])
            infinite_loop = self.params.get("infinite_loop", False)
            loop_interval = self.params.get("loop_interval", 60)
            total_groups = len(groups)
            total_posts_saved = 0

            loop_count = 0
            while not self.stop_requested:
                loop_count += 1
                if infinite_loop:
                    self.log(f"\n{'='*50}\n🔄 Bắt đầu vòng quét thứ {loop_count}...\n{'='*50}")

                total_posts_saved = 0
                for idx, group_item in enumerate(groups):
                    if self.stop_requested:
                        break
                    try:
                        total_posts_saved += self._scrape_one_group(
                            group_item, idx, total_groups, post_count, min_comments, keywords
                        )
                    except Exception as e:
                        self.log(f"❌ Lỗi cào nhóm {idx+1}: {e}")

                if not infinite_loop or self.stop_requested:
                    break

                self.log(f"⏳ Nghỉ {loop_interval}s trước vòng quét tiếp theo...")
                for _ in range(loop_interval):
                    if self.stop_requested:
                        break
                    time.sleep(1)

            duration = time.time() - start_time
            msg = f"Hoàn thành cào dữ liệu ({total_posts_saved} bài viết trong {duration:.1f}s)."
            self.finished_signal.emit(True, msg)

        except Exception as e:
            self.finished_signal.emit(False, f"Lỗi cào dữ liệu: {e}")
        finally:
            if self.ai_worker and self.ai_worker.isRunning():
                self.ai_worker.stop()
                self.ai_worker.wait(3000)
