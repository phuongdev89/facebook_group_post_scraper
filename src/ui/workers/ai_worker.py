import time
import threading
import queue
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.ai_analyzer import analyze_post_with_fallback, format_post_and_comments_payload
from src.core.telegram_notifier import send_keyword_match_alert
from src.database.repository import (
    save_ai_analysis,
    get_ai_analysis_by_post_id,
    get_pending_ai_posts,
    mark_post_ai_status,
    mark_post_ai_pending,
    get_post_comments_with_replies,
)
from src.utils.file_logger import add_log


class AIAnalysisWorker(QThread):
    """
    Background Thread chuyên trách quét DB & phân tích AI cho các bài viết đang chờ:
    - Quét bảng posts với ai_status = 1 (Pending AI).
    - Tách biệt hoàn toàn khỏi luồng cào bài viết / cập nhật bình luận giúp tốc độ cào tối đa.
    - Tự động so sánh vai trò cũ/mới để chống spam thông báo Telegram.
    - Lưu kết quả vào ai_analyses và chuyển tiếp cho Telegram Dispatcher.
    """
    log_signal = pyqtSignal(str)
    analysis_completed_signal = pyqtSignal(dict)

    def __init__(self, ai_config=None, telegram_config=None, check_interval: int = 3):
        super().__init__()
        self.ai_config = ai_config or {}
        self.telegram_config = telegram_config or {}
        self.check_interval = check_interval
        self.task_queue = queue.Queue()
        self.stop_requested = False
        self._wake_event = threading.Event()

    def update_config(self, ai_config=None, telegram_config=None):
        if ai_config is not None:
            self.ai_config = dict(ai_config)
        if telegram_config is not None:
            self.telegram_config = dict(telegram_config)

    def trigger_check_now(self):
        """Kích hoạt quét DB và phân tích ngay lập tức"""
        self._wake_event.set()

    def enqueue(self, post_data: dict, comments_data: list, matched_keyword: str, matched_source: str):
        """Đưa bài viết vào hàng đợi phân tích (lưu vào SQLite và kích hoạt worker)"""
        post_id = str(post_data.get("post_id", ""))
        if post_id:
            mark_post_ai_pending(post_id, matched_keyword, matched_source)
        self.trigger_check_now()

    def stop(self):
        """Dừng worker"""
        self.stop_requested = True
        self._wake_event.set()

    def log(self, message: str):
        self.log_signal.emit(message)
        add_log(message, level="INFO", module="AI_WORKER")

    def _process_single_post(self, post: dict, comments: list, kw_hit: str, kw_source: str):
        post_id = str(post.get("post_id", "N/A"))
        ai_enabled = self.ai_config.get("enabled", False)
        ai_provider = self.ai_config.get("provider", "openai")
        ai_base_url = self.ai_config.get("base_url", "")
        ai_api_key = self.ai_config.get("api_key", "")
        default_m = "gemini-2.0-flash" if ai_provider in ("google_ai", "google_ai_studio") else "gpt-4o-mini"
        ai_models = self.ai_config.get("models") or self.ai_config.get("model") or default_m
        ai_prompt = self.ai_config.get("prompt", "")
        try:
            ai_timeout = int(self.ai_config.get("timeout", 20))
        except (ValueError, TypeError):
            ai_timeout = 20

        tg_enabled = self.telegram_config.get("enabled", False)
        tg_token = self.telegram_config.get("token", "")
        tg_chat_id = self.telegram_config.get("chat_id", "")
        notify_on_keyword = self.telegram_config.get("notify_on_keyword", False)

        try:
            # 1. Kiểm tra bài viết đã từng được AI phân tích trước đó chưa
            existing_analysis = get_ai_analysis_by_post_id(post_id)
            old_actor_role = (existing_analysis.get("actor_role") or existing_analysis.get("seller_type") or "").strip() if existing_analysis else ""

            # 2. Nếu comments rỗng, thử load từ SQLite
            if not comments:
                comments = get_post_comments_with_replies(post_id)

            payload_json = format_post_and_comments_payload(post, comments)

            if ai_enabled and ai_api_key:
                self.log(f"🤖 [AI Worker] Đang phân tích bài {post_id} qua AI ({ai_provider}, timeout {ai_timeout}s)...")
                should_notify, _, ai_result, ai_reason, model_used = analyze_post_with_fallback(
                    base_url=ai_base_url,
                    api_key=ai_api_key,
                    models=ai_models,
                    prompt=ai_prompt,
                    post_content=payload_json,
                    timeout=ai_timeout,
                    logger=self.log,
                    provider=ai_provider
                )

                target_name = (ai_result.get("target_name") or ai_result.get("device_name") or "") if ai_result else ""
                price = (ai_result.get("price") or ai_result.get("price_or_budget") or "") if ai_result else ""
                new_actor_role = (ai_result.get("actor_role") or ai_result.get("seller_type") or "").strip() if ai_result else ""
                matched_snippet = (ai_result.get("matched_snippet") or ai_result.get("seller_snippet") or "") if ai_result else ""
                reason = ai_result.get("reason", "") if ai_result else ai_reason
                raw_resp = ai_result.get("raw_response", "") if ai_result else ""

                # Kiểm tra trùng lặp và thay đổi vai trò
                if existing_analysis:
                    role_changed = (new_actor_role.lower() != old_actor_role.lower()) if old_actor_role else True
                    if not role_changed:
                        should_send_telegram = False
                        self.log(f"   ℹ️ [AI Trùng Lặp] Bài {post_id} đã được phân tích trước đó (Vai trò '{old_actor_role}' không đổi) -> Cập nhật dữ liệu, BỎ QUA thông báo Telegram.")
                    else:
                        should_send_telegram = should_notify
                        if should_notify:
                            self.log(f"   🎯 [AI Alert - Vai trò mới] Bài {post_id} thay đổi vai trò: '{old_actor_role}' ➔ '{new_actor_role}'! Đã xếp hàng gửi Telegram.")
                        else:
                            self.log(f"   ℹ️ [AI Worker] Bài {post_id} thay đổi vai trò thành '{new_actor_role}' nhưng AI đánh giá không cần thông báo.")
                else:
                    should_send_telegram = should_notify
                    if should_notify:
                        self.log(f"   🎯 [AI Alert] Bài {post_id} phát hiện THÔNG TIN KHỚP: {target_name} ({price}) [Model: {model_used}] -> Đã xếp hàng gửi Telegram.")
                    else:
                        self.log(f"   ℹ️ [AI Worker] Bài {post_id}: AI đánh giá không khớp yêu cầu (BỎ QUA thông báo).")

                analysis_id = save_ai_analysis(
                    post_id=post_id,
                    group_name=post.get("group_name") or post.get("page_name") or "",
                    matched_keyword=kw_hit,
                    matched_source=kw_source,
                    model_used=model_used,
                    should_notify=should_notify,
                    target_name=target_name,
                    price=price,
                    actor_role=new_actor_role,
                    matched_snippet=matched_snippet,
                    reason=reason,
                    raw_response=raw_resp,
                    telegram_sent=0 if should_send_telegram else 1
                )

                mark_post_ai_status(post_id, 2)

                self.analysis_completed_signal.emit({
                    "id": analysis_id,
                    "post_id": post_id,
                    "should_notify": should_notify,
                    "target_name": target_name,
                    "device_name": target_name,
                    "price": price,
                    "actor_role": new_actor_role,
                    "model_used": model_used,
                    "telegram_sent": 0 if should_send_telegram else 1
                })

            else:
                if existing_analysis:
                    self.log(f"   ℹ️ [Trùng Lặp] Bài {post_id} đã tồn tại trong dữ liệu -> Bỏ qua gửi thông báo Telegram.")
                elif tg_enabled and tg_token and tg_chat_id and notify_on_keyword:
                    self.log(f"   📱 [Thông báo] AI tắt, gửi cảnh báo từ khóa '{kw_hit}' bài {post_id} sang Telegram...")
                    send_keyword_match_alert(
                        token=tg_token,
                        chat_id=tg_chat_id,
                        post_data=post,
                        matched_keyword=kw_hit,
                        matched_type=kw_source
                    )
                mark_post_ai_status(post_id, 2)

        except Exception as e:
            self.log(f"   ⚠️ [AI Worker] Lỗi xử lý bài {post_id}: {e}")
            mark_post_ai_status(post_id, -1)

    def run(self):
        while not self.stop_requested:
            try:
                pending_posts = get_pending_ai_posts(limit=5)
                if pending_posts:
                    for p in pending_posts:
                        if self.stop_requested:
                            break
                        post_id = p.get("post_id")
                        kw_hit = p.get("matched_keyword") or ""
                        kw_source = p.get("matched_source") or "Bài viết"
                        mark_post_ai_status(post_id, 3)
                        comments = get_post_comments_with_replies(post_id)
                        self._process_single_post(p, comments, kw_hit, kw_source)
            except Exception as ex:
                self.log(f"⚠️ [AI Worker] Lỗi quét danh sách bài chờ AI: {ex}")

            self._wake_event.wait(timeout=self.check_interval)
            self._wake_event.clear()


class FetchOpenAIModelsWorker(QThread):
    finished_signal = pyqtSignal(bool, list, str)

    def __init__(self, base_url: str = "", api_key: str = "", timeout: int = 8):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout

    def run(self):
        from src.core.ai_analyzer import fetch_openai_models_from_api
        ok, models, msg = fetch_openai_models_from_api(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self.timeout
        )
        self.finished_signal.emit(ok, models, msg)


class TestAIModelsWorker(QThread):
    """
    Worker kiểm tra thực tế từng model AI bất đồng bộ qua QThread:
    - Phát tín hiệu model_testing_started(model_name) khi bắt đầu test 1 model.
    - Phát tín hiệu model_tested_single(result_dict) ngay khi test xong 1 model.
    - Phát tín hiệu progress_signal(current, total, model_name).
    - Phát tín hiệu finished_all_signal(all_results) khi test xong tất cả.
    - Không làm đơ/treo giao diện người dùng.
    """
    model_testing_started = pyqtSignal(str)
    model_tested_single = pyqtSignal(dict)
    progress_signal = pyqtSignal(int, int, str)
    finished_all_signal = pyqtSignal(list)
    log_signal = pyqtSignal(str)

    def __init__(self, base_url: str, api_key: str, models: list, timeout: int = 15, provider: str = "openai"):
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.models = list(models)
        self.timeout = timeout
        self.provider = provider
        self.stop_requested = False

    def stop(self):
        self.stop_requested = True

    def run(self):
        from src.core.ai_analyzer import verify_single_model_pure_json
        results = []
        total = len(self.models)

        for idx, model_name in enumerate(self.models):
            if self.stop_requested:
                break

            self.model_testing_started.emit(model_name)
            self.progress_signal.emit(idx + 1, total, model_name)
            self.log_signal.emit(f"🧪 [{idx+1}/{total}] Đang test model: {model_name}...")

            is_valid, is_thinking, msg, data = verify_single_model_pure_json(
                base_url=self.base_url,
                api_key=self.api_key,
                model_name=model_name,
                timeout=self.timeout,
                provider=self.provider
            )
            status_type = "ok" if is_valid else ("thinking" if is_thinking else "error")
            res = {
                "name": model_name,
                "is_valid": is_valid,
                "is_thinking": is_thinking,
                "status": status_type,
                "message": msg,
                "response": data
            }
            results.append(res)
            self.model_tested_single.emit(res)
            
            status_icon = "✅" if is_valid else ("🧠" if is_thinking else "❌")
            self.log_signal.emit(f"   {status_icon} Model {model_name}: {msg}")

        self.finished_all_signal.emit(results)


