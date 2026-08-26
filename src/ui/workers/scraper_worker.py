import time
import re
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.proxy_utils import select_proxy
from src.core.group_scraper import fetch_posts as fetch_group_posts
from src.core.comment_scraper import fetch_comments
from src.utils.helpers import extract_group_id_from_url
from src.database.repository import save_or_update_post, mark_post_ai_pending
from src.ui.workers.ai_worker import AIAnalysisWorker

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
            
            loop_count = 0
            while not self.stop_requested:
                loop_count += 1
                if infinite_loop:
                    self.log(f"\n{'='*50}\n🔄 Bắt đầu vòng quét thứ {loop_count}...\n{'='*50}")
                
                total_posts_saved = 0
                total_groups = len(groups)
                
                for idx, group_item in enumerate(groups):
                    if self.stop_requested:
                        break
                    
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
                        continue
                        
                    self.log(f"🔍 Group ID: {group_id}")
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
                        continue
                        
                    self.log(f"📄 Tìm thấy {len(posts)} bài viết. Đang lấy bình luận và lưu dữ liệu...")
                    for p_idx, post in enumerate(posts):
                        if self.stop_requested:
                            break
                            
                        post_id = post.get("post_id")
                        if not post_id:
                            continue
                        if configured_name and not post.get("group_name"):
                            post["group_name"] = configured_name
                            
                        comments = []
                        try:
                            target_cmt_count = max(min_comments, 20)
                            comments, _ = fetch_comments(
                                post_id,
                                target_count=target_cmt_count,
                                cookies=self.cookies,
                                fb_dtsg=self.fb_dtsg,
                                logger=self.log
                            )
                        except Exception as e:
                            self.log(f"⚠️ Lỗi lấy comment bài {post_id}: {e}")
                                
                        res = save_or_update_post(
                            post_type="group_post",
                            post_id=post_id,
                            post_data=post,
                            comments_data=comments
                        )
                        total_posts_saved += 1
                        
                        kw_hit = None
                        kw_source = "Bài viết"
                        post_msg = (post.get("message") or post.get("text") or "").lower()
                        for kw in keywords:
                            if kw.lower() in post_msg:
                                kw_hit = kw
                                kw_source = "Bài viết"
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
