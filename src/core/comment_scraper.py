import requests
import json
import time
import os
import sys
# Ensure stdout and stderr handle utf-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

GRAPHQL = "https://www.facebook.com/api/graphql/"

# Base headers for all requests
BASE_HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded"
}

# Get proxy configuration
PROXY = os.getenv('PROXY')
PROXIES = {'http': PROXY, 'https': PROXY} if PROXY else None

# FB_DTSG token (set by UI when provided)
FB_DTSG = ""

if PROXY:
    print(f"Using proxy: {PROXY}")

# ========= RETRY HELPER =========
def _is_cookie_expired(response):
    """Check if Facebook rejected expired/invalid cookies (error 1357004)"""
    if not response or not response.text:
        return False
    try:
        if '"error":1357004' in response.text or '"error": 1357004' in response.text:
            return True
    except Exception:
        pass
    return False


def retry_request(url, headers, data, proxies, cookies=None, max_retries=5):
    """Make a POST request with retry logic"""
    global PROXIES, FB_DTSG
    from src.core.proxy_utils import rotate_static_proxy, is_proxy_infra_error, is_ip_blocked

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies=cookies, timeout=30)
            if r.status_code == 200 and _is_cookie_expired(r):
                if cookies and isinstance(cookies, dict) and cookies.get("c_user"):
                    print(f"  ⚠️ Cookies hết hạn (error 1357004). Đang thử refresh qua headless browser...")
                    try:
                        from src.core.group_fetcher import refresh_cookies_via_browser
                        new_cookies, new_cookie_str, new_dtsg, new_raw_json = refresh_cookies_via_browser(cookies, headless=True)
                        if new_cookies and new_cookies.get("c_user"):
                            cookies = new_cookies
                            FB_DTSG = new_dtsg
                            data = {**data, "av": cookies.get("c_user", "0"), "__user": cookies.get("c_user", "0"), "fb_dtsg": FB_DTSG or ""}
                            try:
                                import src.database as database
                                database.set_setting("cookie_string", new_cookie_str)
                                if new_raw_json:
                                    database.set_setting("cookie_raw_json", new_raw_json)
                                if new_dtsg:
                                    database.set_setting("fb_dtsg", new_dtsg)
                                print(f"  ✅ Đã refresh và lưu cookies mới thành công.")
                            except Exception:
                                pass
                            r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies=cookies, timeout=30)
                            if r.status_code == 200 and not _is_cookie_expired(r):
                                return r
                    except Exception as e:
                        print(f"  ⚠️ Refresh cookies thất bại: {e}")
                print(f"  🔓 Chuyển sang chế độ ẩn danh (không cookies)...")
                cookies = None
                FB_DTSG = ""
                data = {**data, "av": "0", "__user": "0", "fb_dtsg": ""}
                r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies=None, timeout=30)
            if r.status_code == 200:
                return r
            if is_proxy_infra_error(status_code=r.status_code):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy auth failed (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            elif is_ip_blocked(status_code=r.status_code, response_text=r.text):
                print(f"  🛑 Attempt {attempt}/{max_retries}: Facebook blocked this IP (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            else:
                print(f"  ⚠️ Attempt {attempt}/{max_retries}: Status {r.status_code}")
        except requests.exceptions.ProxyError as e:
            print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy unreachable — rotating static proxy...")
            new_p = rotate_static_proxy()
            if new_p:
                proxies = new_p
                PROXIES = new_p
        except Exception as e:
            if is_proxy_infra_error(exc=e):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy connection error — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            else:
                print(f"  ⚠️ Attempt {attempt}/{max_retries}: {str(e)}")

        if attempt < max_retries:
            wait_time = attempt * 2
            print(f"  ⏳ Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception(f"Failed after {max_retries} attempts")

# ===== PAYLOADS =====
import base64

def normalize_feedback_id(post_or_feedback_id: str) -> str:
    """Đảm bảo feedback_id luôn ở định dạng chuẩn Facebook GraphQL Relay ID (base64 feedback:<post_id>)"""
    s = str(post_or_feedback_id or "").strip()
    if not s:
        return ""
    if s.startswith("ZmVlZGJhY2s"):
        return s
    if s.startswith("feedback:"):
        return base64.b64encode(s.encode("utf-8")).decode("utf-8")
    if s.isdigit():
        return base64.b64encode(f"feedback:{s}".encode("utf-8")).decode("utf-8")
    return s


def comments_payload(feedback_id, cursor=None, cookies=None):
    # Extract user ID from cookies if available
    user_id = "0"
    if cookies and "c_user" in cookies:
        user_id = cookies["c_user"]
    
    clean_fb_id = normalize_feedback_id(feedback_id)
    return {
        "av": user_id,
        "__user": user_id,
        "__a": "1",
        "fb_dtsg": FB_DTSG if FB_DTSG else "",
        "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true",
        "doc_id": "27806180149070312",
        "variables": json.dumps({
            "commentsAfterCount": -1,
            "commentsAfterCursor": cursor,
            "commentsBeforeCount": None,
            "commentsBeforeCursor": None,
            "commentsIntentToken": None,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "scale": 2,
            "useDefaultActor": False,
            "id": clean_fb_id,
            "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
            "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
            "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
            "__relay_internal__pv__IsWorkUserrelayprovider": False
        })
    }


def replies_payload(comment_feedback_id, expansion_token, cookies=None):
    # Extract user ID from cookies if available
    user_id = "0"
    if cookies and "c_user" in cookies:
        user_id = cookies["c_user"]
    
    return {
        "av": user_id,
        "__user": user_id,
        "__a": "1",
        "fb_dtsg": FB_DTSG if FB_DTSG else "",
        "fb_api_caller_class": "RelayModern",
        "server_timestamps": "true",
        "doc_id": "26570577339199586",
        "variables": json.dumps({
            "clientKey": None,
            "expansionToken": expansion_token,
            "feedLocation": "POST_PERMALINK_DIALOG",
            "focusCommentID": None,
            "scale": 2,
            "useDefaultActor": False,
            "id": comment_feedback_id,
            "__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider": "AUTO_TRANSLATE",
            "__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider": False,
            "__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider": True,
            "__relay_internal__pv__IsWorkUserrelayprovider": False
        })
    }

# ===== FETCH COMMENTS =====
import json

def fb_json(response_text):
    """
    Facebook GraphQL sometimes returns:
    for (;;);
    {json}
    {json}

    This extracts the first valid JSON object safely.
    """
    text = response_text.strip()

    # Remove for (;;);
    if text.startswith("for (;;);"):
        text = text[len("for (;;);"):]

    # Keep only first JSON object
    first = text.split("\n")[0].strip()

    return json.loads(first)


def _safe(obj, *keys, default=None):
    """Safe nested dict access — returns default if any key missing or value is None/non-dict"""
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k)
        if obj is None:
            return default
    return obj if obj is not None else default


def fetch_comments(feedback_id, cookies=None, fb_dtsg=None, target_count=None, logger=None, **kwargs):
    global FB_DTSG
    if fb_dtsg:
        FB_DTSG = fb_dtsg

    results = []
    cursor = None
    response_count = 0
    post_info = None  # Store parent post info from first response

    while True:
        headers = {**BASE_HEADERS, "x-fb-friendly-name": "CommentsListComponentsPaginationQuery"}
        r = retry_request(
            GRAPHQL,
            headers,
            comments_payload(feedback_id, cursor, cookies),
            PROXIES,
            cookies=cookies
        )
        j = fb_json(r.text)
        if not isinstance(j, dict):
            break
        
        # Save each JSON response for inspection
        response_count += 1
        
        comments_block = _safe(j, "data", "node", "comment_rendering_instance_for_feed_location", "comments", default={})
        edges = _safe(comments_block, "edges", default=[])
        if not edges:
            break

        for e in edges:
            if not isinstance(e, dict):
                continue
            n = e.get("node")
            if not isinstance(n, dict):
                continue
            fb = n.get("feedback")
            if not isinstance(fb, dict):
                fb = {}

            # Extract parent_post_story info from first response
            if response_count == 1 and post_info is None:
                parent_post_story = n.get("parent_post_story")
                if isinstance(parent_post_story, dict):
                    post_info = {
                        "post_story_id": parent_post_story.get("id"),
                        "media_id": None
                    }
                    
                    # Extract first media ID
                    attachments = _safe(parent_post_story, "attachments", default=[])
                    for attachment in attachments:
                        if isinstance(attachment, dict):
                            media = attachment.get("media")
                            if isinstance(media, dict) and media.get("id"):
                                post_info["media_id"] = media.get("id")
                                break  # Only get first one

            # Extract reaction count
            reactors = _safe(fb, "reactors", default={})
            total_reactions = reactors.get("count_reduced", "0") if isinstance(reactors, dict) else "0"
            
            expansion_info = fb.get("expansion_info")
            expansion_token = expansion_info.get("expansion_token") if isinstance(expansion_info, dict) else None

            body = n.get("body")
            body_text = body.get("text", "") if isinstance(body, dict) else ""

            results.append({
                "comment_id": n.get("legacy_fbid"),
                "text": body_text,
                "reaction_count": total_reactions,
                "_feedback_id": fb.get("id"),  # Internal use only (for fetching replies)
                "_expansion_token": expansion_token  # Internal use only
            })

        cursor = _safe(comments_block, "page_info", "end_cursor", default=None)
        if not cursor:
            break
        if target_count and len(results) >= target_count:
            break

    # Lấy replies cho từng bình luận
    for c in results:
        try:
            c["replies"] = fetch_replies(c, cookies=cookies)
        except Exception:
            c["replies"] = []

    return results, post_info

# ===== FETCH REPLIES =====

def fetch_replies(comment, cookies=None):
    feedback_id = comment.get("_feedback_id")
    expansion_token = comment.get("_expansion_token")

    # If no expansion token or feedback id, comment has no expandable replies -> skip HTTP request
    if not feedback_id or not expansion_token:
        return []

    headers = {**BASE_HEADERS, "x-fb-friendly-name": "Depth1CommentsListPaginationQuery"}
    try:
        r = retry_request(
            GRAPHQL,
            headers,
            replies_payload(feedback_id, expansion_token, cookies),
            PROXIES,
            cookies=cookies
        )

        j = fb_json(r.text)
        if not isinstance(j, dict):
            return []

        replies = []
        edges = _safe(j, "data", "node", "replies_connection", "edges", default=[])

        for e in edges:
            if not isinstance(e, dict):
                continue
            n = e.get("node")
            if not isinstance(n, dict):
                continue
            fb = n.get("feedback")
            if not isinstance(fb, dict):
                fb = {}
            
            # Extract reaction count
            reactors = _safe(fb, "reactors", default={})
            total_reactions = reactors.get("count_reduced", "0") if isinstance(reactors, dict) else "0"
            
            body = n.get("body")
            body_text = body.get("text", "") if isinstance(body, dict) else ""

            replies.append({
                "reply_id": n.get("legacy_fbid"),
                # "author": n["author"]["name"],
                "text": body_text,
                "reaction_count": total_reactions
            })

        return replies
    except Exception as e:
        print(f"    ⚠️ Error fetching replies: {e}")
        return []

# ===== RUN =====

if __name__ == "__main__":
    POST_FEEDBACK_ID = "ZmVlZGJhY2s6MTg3NDE2NTYxMzI0NjAwMw=="
    POST_ID = "1420269302790428"  # The actual post ID

    all_data = []

    comments, post_info = fetch_comments(POST_FEEDBACK_ID)
    
    # Add post info to the output
    output = {
        "post_info": post_info,
        "comments": []
    }

    for c in comments:
        # print(f"\n🗨️ {c['author']}: {c['text']}")
        c["replies"] = fetch_replies(c)

        # for r in c["replies"]:
        #     print(f"   ↳ {r['author']}: {r['text']}")

        output["comments"].append(c)

    import src.database as database
    database.init_db()
    database.save_or_update_post("simple_post", POST_ID, post_info or {"post_id": POST_ID}, output["comments"])
    print(f"💬 Saved to SQLite database.")
