import queue
from PyQt6.QtCore import QThread, pyqtSignal
from src.core.ai_analyzer import analyze_post_with_fallback, format_post_and_comments_payload
from src.core.telegram_notifier import send_keyword_match_alert
from src.database.repository import save_ai_analysis

class AIAnalysisWorker(QThread):
    log_signal = pyqtSignal(str)
    analysis_completed_signal = pyqtSignal(dict)

    def __init__(self, ai_config=None, telegram_config=None):
        super().__init__()
        self.ai_config = ai_config or {}
        self.telegram_config = telegram_config or {}
        self.task_queue = queue.Queue()
        self.stop_requested = False

    def update_config(self, ai_config=None, telegram_config=None):
        if ai_config is not None:
            self.ai_config = dict(ai_config)
        if telegram_config is not None:
            self.telegram_config = dict(telegram_config)

    def enqueue(self, post_data: dict, comments_data: list, matched_keyword: str, matched_source: str):
        self.task_queue.put((post_data, comments_data, matched_keyword, matched_source))

    def stop(self):
        self.stop_requested = True
        self.task_queue.put(None)

    def log(self, message: str):
        self.log_signal.emit(message)

    def run(self):
        while not self.stop_requested:
            try:
                task = self.task_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if task is None:
                break

            post, comments, kw_hit, kw_source = task
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
                payload_json = format_post_and_comments_payload(post, comments)

                if ai_enabled and ai_api_key:
                    self.log(f"      🤖 [AI Thread] Đang phân tích bài {post_id} qua AI ({ai_provider}, timeout {ai_timeout}s)...")
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
                    actor_role = (ai_result.get("actor_role") or ai_result.get("seller_type") or "") if ai_result else ""
                    matched_snippet = (ai_result.get("matched_snippet") or ai_result.get("seller_snippet") or "") if ai_result else ""
                    reason = ai_result.get("reason", "") if ai_result else ai_reason
                    raw_resp = ai_result.get("raw_response", "") if ai_result else ""

                    analysis_id = save_ai_analysis(
                        post_id=post_id,
                        group_name=post.get("group_name") or post.get("page_name") or "",
                        matched_keyword=kw_hit,
                        matched_source=kw_source,
                        model_used=model_used,
                        should_notify=should_notify,
                        target_name=target_name,
                        price=price,
                        actor_role=actor_role,
                        matched_snippet=matched_snippet,
                        reason=reason,
                        raw_response=raw_resp,
                        telegram_sent=0 if should_notify else 0
                    )

                    if should_notify:
                        self.log(f"      🎯 [AI Alert] Bài {post_id} phát hiện THÔNG TIN KHỚP: {target_name} ({price}) [Model: {model_used}] -> Đã xếp hàng gửi Telegram.")
                    else:
                        self.log(f"      ℹ️ [AI Thread] Bài {post_id}: AI đánh giá không khớp yêu cầu (BỎ QUA thông báo).")

                    self.analysis_completed_signal.emit({
                        "id": analysis_id,
                        "post_id": post_id,
                        "should_notify": should_notify,
                        "target_name": target_name,
                        "device_name": target_name,
                        "price": price,
                        "model_used": model_used,
                        "telegram_sent": 0 if should_notify else 0
                    })

                else:
                    if tg_enabled and tg_token and tg_chat_id and notify_on_keyword:
                        self.log(f"      📱 [AI Thread] AI tắt, gửi cảnh báo từ khóa '{kw_hit}' bài {post_id} sang Telegram...")
                        send_keyword_match_alert(
                            token=tg_token,
                            chat_id=tg_chat_id,
                            post_data=post,
                            matched_keyword=kw_hit,
                            matched_type=kw_source
                        )

            except Exception as e:
                self.log(f"      ⚠️ [AI Thread] Lỗi xử lý bài {post_id}: {e}")
            finally:
                self.task_queue.task_done()
