import requests
from datetime import datetime
from html import escape


def send_telegram_message(token: str, chat_id: str, text: str, parse_mode: str = "HTML") -> tuple[bool, str]:
    """
    Gửi tin nhắn qua Telegram Bot API (requests thuần).
    Trả về: (thành_công: bool, thông_điệp_lỗi_hoặc_ok: str)
    """
    if not token or not token.strip():
        return False, "Thiếu Telegram Bot Token"
    if not chat_id or not chat_id.strip():
        return False, "Thiếu Telegram Chat ID"

    url = f"https://api.telegram.org/bot{token.strip()}/sendMessage"
    payload = {
        "chat_id": chat_id.strip(),
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": False
    }

    try:
        r = requests.post(url, json=payload, timeout=15)
        res_json = r.json()
        if r.status_code == 200 and res_json.get("ok"):
            return True, "Gửi tin nhắn Telegram thành công"
        else:
            err_desc = res_json.get("description", f"HTTP {r.status_code}")
            return False, f"Telegram API Error: {err_desc}"
    except Exception as e:
        return False, f"Lỗi kết nối Telegram: {str(e)}"


def test_connection(token: str, chat_id: str) -> tuple[bool, str]:
    """Gửi tin nhắn kiểm tra kết nối tới Telegram bot"""
    now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    msg = (
        "<b>🤖 [Facebook Scraper] Kiểm tra kết nối</b>\n\n"
        f"✅ Bot Telegram đã kết nối thành công lúc <i>{now}</i>.\n"
        "Hệ thống đã sẵn sàng nhận thông báo!"
    )
    return send_telegram_message(token, chat_id, msg, parse_mode="HTML")


def send_finish_notification(token: str, chat_id: str, stats: dict) -> tuple[bool, str]:
    """Gửi thông báo tổng kết khi hoàn thành một vòng quét"""
    now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
    total_groups = stats.get("total_groups", 0)
    total_posts = stats.get("total_posts", 0)
    total_saved = stats.get("total_saved", 0)
    duration = stats.get("duration", 0)

    msg = (
        "<b>📢 [Facebook Scraper] Hoàn thành đợt quét</b>\n\n"
        f"⏰ Thời gian: <code>{now}</code>\n"
        f"📂 Số nhóm quét: <b>{total_groups}</b>\n"
        f"📄 Tổng số bài tìm thấy: <b>{total_posts}</b>\n"
        f"💾 Số bài lưu vào DB: <b>{total_saved}</b>\n"
        f"⏱ Thời gian thực hiện: <b>{duration:.1f}s</b>"
    )
    return send_telegram_message(token, chat_id, msg, parse_mode="HTML")


def send_keyword_match_alert(token: str, chat_id: str, post_data: dict, matched_keyword: str = "", matched_type: str = "Bài viết", ai_result: dict = None, model_used: str = "") -> tuple[bool, str]:
    """Gửi thông báo chi tiết khi phát hiện bài viết hoặc bình luận khớp từ khóa (hỗ trợ hiển thị kết quả AI)"""
    post_id = post_data.get("post_id", "N/A")
    group_name = post_data.get("group_name") or post_data.get("page_name") or "Nhóm Facebook"
    permalink = post_data.get("permalink") or f"https://www.facebook.com/{post_id}"
    
    # Trích xuất nội dung
    content = post_data.get("message") or post_data.get("text") or "(Không có nội dung văn bản)"
    content_snippet = content[:300] + ("..." if len(content) > 300 else "")

    now = datetime.now().strftime("%H:%M:%S %d/%m/%Y")

    if ai_result and ai_result.get("should_notify", False):
        target = ai_result.get("target_name") or ai_result.get("device_name") or "Không rõ"
        price = ai_result.get("price") or ai_result.get("price_or_budget") or "Thỏa thuận / Không đề cập"
        reason = ai_result.get("reason") or ""
        actor_role_raw = ai_result.get("actor_role") or ai_result.get("seller_type") or ""
        matched_snippet = ai_result.get("matched_snippet") or ai_result.get("seller_snippet") or ""

        if "comment" in actor_role_raw.lower() or "bình luận" in actor_role_raw.lower():
            actor_role_label = "💬 Người bình luận trong bài"
        elif "author" in actor_role_raw.lower() or "post" in actor_role_raw.lower() or "chủ bài" in actor_role_raw.lower():
            actor_role_label = "👤 Chủ bài đăng"
        elif actor_role_raw:
            actor_role_label = f"📌 {actor_role_raw}"
        else:
            actor_role_label = "Bài viết / Bình luận"

        msg = (
            "<b>🔔 [Facebook Scraper] Phát hiện thông tin khớp yêu cầu (AI Alert)!</b>\n\n"
            f"🎯 <b>Mục tiêu / Đối tượng:</b> <code>{escape(target)}</code>\n"
            f"💰 <b>Giá / Ngân sách / Lương:</b> <b>{escape(price)}</b>\n"
            f"📍 <b>Vai trò:</b> <b>{escape(actor_role_label)}</b>\n"
        )

        if matched_snippet:
            msg += f"💬 <b>Trích đoạn:</b> <i>{escape(matched_snippet[:200])}</i>\n"
        if reason:
            msg += f"💡 <b>Đánh giá AI:</b> <i>{escape(reason)}</i>\n"
        if model_used:
            msg += f"🤖 <b>Model AI:</b> <code>{escape(model_used)}</code>\n"


        msg += (
            f"\n🎯 <b>Từ khóa khớp:</b> <code>{escape(matched_keyword)}</code> (Tại {matched_type})\n"
            f"👥 <b>Nhóm/Trang:</b> {escape(group_name)}\n"
            f"⏰ <b>Thời gian:</b> {now}\n"
            f"📝 <b>Nội dung bài viết:</b>\n"
            f"<i>{escape(content_snippet)}</i>\n\n"
            f"🔗 <a href='{permalink}'>Xem bài viết trên Facebook</a>"
        )
    else:
        msg = (
            "<b>🔔 [Facebook Scraper] Phát hiện từ khóa mới!</b>\n\n"
            f"🎯 <b>Từ khóa khớp:</b> <code>{escape(matched_keyword)}</code> (Tại {matched_type})\n"
            f"👥 <b>Nhóm/Trang:</b> {escape(group_name)}\n"
            f"⏰ <b>Thời gian:</b> {now}\n"
            f"📝 <b>Nội dung trích đoạn:</b>\n"
            f"<i>{escape(content_snippet)}</i>\n\n"
            f"🔗 <a href='{permalink}'>Xem bài viết trên Facebook</a>"
        )
    return send_telegram_message(token, chat_id, msg, parse_mode="HTML")
