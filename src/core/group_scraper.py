import requests
import json
import time
import os
import sys
import re
import uuid
# Ensure stdout and stderr handle utf-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

# Import database module
import src.database as database
database.init_db()

GRAPHQL_URL = "https://www.facebook.com/api/graphql/"

# ========= CONFIG (FILL THESE) =========
GROUP_ID = "363757814515154"  # group id
GROUP_NAME = None  # Will be extracted automatically
DOC_ID = "25716860671307636"  # GroupsCometFeedRegularStoriesPaginationQuery

HEADERS = {
    "user-agent": "Mozilla/5.0",
    "content-type": "application/x-www-form-urlencoded",
    "origin": "https://www.facebook.com",
    "referer": f"https://www.facebook.com/groups/{GROUP_ID}/",
}

# Get proxy configuration
PROXY = os.getenv('PROXY')
PROXIES = {'http': PROXY, 'https': PROXY} if PROXY else None

# Cookies (set by UI when provided)
COOKIES = {}

# FB_DTSG token (set by UI when provided)
FB_DTSG = ""

if PROXY:
    print(f"Using proxy: {PROXY}")


def _safe(obj, *keys, default=None):
    """Safe nested dict access — returns default if any key missing or value is None/non-dict"""
    for k in keys:
        if not isinstance(obj, dict):
            return default
        obj = obj.get(k)
        if obj is None:
            return default
    return obj if obj is not None else default


def extract_group_name(node):
    """Extract group name from post node"""
    if not node or not isinstance(node, dict):
        return None
    try:
        # Try from context_layout > story > comet_sections > title > story > to
        to_obj = _safe(node, 'comet_sections', 'context_layout', 'story', 'comet_sections', 'title', 'story', 'to')
        if isinstance(to_obj, dict) and to_obj.get('__typename') == 'Group' and to_obj.get('name'):
            return str(to_obj['name']).strip()

        target_group = _safe(node, 'comet_sections', 'content', 'story', 'target_group')
        if isinstance(target_group, dict) and target_group.get('name'):
            return str(target_group['name']).strip()

        associated_group = _safe(node, 'feedback', 'associated_group')
        if isinstance(associated_group, dict) and associated_group.get('name'):
            return str(associated_group['name']).strip()

        return None
    except Exception:
        return None


def extract_creation_time(node):
    """Extract post creation time (Unix timestamp) from node"""
    try:
        return _safe(node, 'comet_sections', 'timestamp', 'story', 'creation_time')
    except Exception:
        return None

# ========= RETRY HELPER =========
def _is_cookie_expired(response):
    """Check if Facebook rejected expired/invalid cookies (error 1357004)"""
    if not response or not response.text:
        return False
    try:
        text = response.text.replace("for (;;);", "").strip()
        if '"error":1357004' in text or '"error": 1357004' in text:
            return True
    except Exception:
        pass
    return False


def retry_request(url, headers, data, proxies, max_retries=5):
    """Make a POST request with retry logic"""
    global PROXIES, COOKIES, FB_DTSG
    from src.core.proxy_utils import rotate_static_proxy, is_proxy_infra_error, is_ip_blocked

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies=COOKIES, timeout=30)
            # Detect expired cookies — try refresh, then fallback to anonymous
            if r.status_code == 200 and _is_cookie_expired(r):
                if COOKIES.get("c_user"):
                    print(f"  ⚠️ Cookies hết hạn (error 1357004). Đang thử refresh qua headless browser...")
                    try:
                        from src.core.group_fetcher import refresh_cookies_via_browser
                        new_cookies, new_cookie_str, new_dtsg, new_raw_json = refresh_cookies_via_browser(COOKIES, headless=True)
                        if new_cookies and new_cookies.get("c_user"):
                            COOKIES = new_cookies
                            FB_DTSG = new_dtsg
                            # Cập nhật payload với cookies mới
                            data = {**data, "av": COOKIES.get("c_user", "0"), "__user": COOKIES.get("c_user", "0"), "fb_dtsg": FB_DTSG or ""}
                            # Lưu cookies mới vào DB
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
                            r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies=COOKIES, timeout=30)
                            if r.status_code == 200 and not _is_cookie_expired(r):
                                return r
                    except Exception as e:
                        print(f"  ⚠️ Refresh cookies thất bại: {e}")
                # Fallback: anonymous mode
                print(f"  🔓 Chuyển sang chế độ ẩn danh (không cookies)...")
                COOKIES = {}
                FB_DTSG = ""
                data = {**data, "av": "0", "__user": "0", "fb_dtsg": ""}
                r = requests.post(url, headers=headers, data=data, proxies=proxies, cookies={}, timeout=30)
            if r.status_code == 200:
                return r
            if is_proxy_infra_error(status_code=r.status_code):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy auth failed (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    proxies = new_p
                    PROXIES = new_p
            elif is_ip_blocked(status_code=r.status_code, response_text=r.text):
                print(f"  🛽 Attempt {attempt}/{max_retries}: Facebook blocked this IP (HTTP {r.status_code}) — rotating static proxy...")
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


def download_image(url, post_id, image_index=1, save_dir=None):
    """Placeholder - Images are now stored as URLs in SQLite without downloading to disk"""
    return None


def fetch_remaining_images(last_media_id, post_id, current_image_count, save_dir=None):
    """Fetch remaining images metadata (for posts with 5+ images) without downloading to disk"""
    if not last_media_id or not post_id:
        return []
    
    DOC_ID_PHOTO = "26168653472729001"  # CometPhotoRootContentQuery
    HEADERS_PHOTO = {
        "user-agent": "Mozilla/5.0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
        "x-fb-friendly-name": "CometPhotoRootContentQuery"
    }
    
    remaining_photos = []
    current_node = last_media_id
    visited = set()
    image_index = current_image_count + 1
    
    while current_node and current_node not in visited and image_index <= 50:
        visited.add(current_node)
        
        variables = {
            "isMediaset": True,
            "renderLocation": "comet_media_viewer",
            "nodeID": current_node,
            "mediasetToken": f"pcb.{post_id}",
            "scale": 2,
            "feedLocation": "COMET_MEDIA_VIEWER",
            "feedbackSource": 65,
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_MEDIA_VIEWER",
            "useDefaultActor": False,
            "shouldShowComments": True
        }
        
        payload = {
            "av": COOKIES.get("c_user", "0"),
            "__user": COOKIES.get("c_user", "0"),
            "__a": "1",
            "fb_dtsg": FB_DTSG if FB_DTSG else "",
            "doc_id": DOC_ID_PHOTO,
            "variables": json.dumps(variables)
        }
        
        try:
            r = requests.post(GRAPHQL_URL, headers=HEADERS_PHOTO, data=payload, proxies=PROXIES, cookies=COOKIES, timeout=30)
            if r.status_code != 200:
                break
            
            cleaned_blocks = parse_fb_response(r.text)
            if not cleaned_blocks:
                break
            
            image_url = None
            for block in cleaned_blocks:
                if "currMedia" in block:
                    image_url = block["currMedia"].get("image", {}).get("uri")
                    break
            
            if image_url:
                remaining_photos.append({
                    'id': current_node,
                    'url': image_url,
                    'saved_as': None
                })
                image_index += 1
            
            next_node = None
            for block in cleaned_blocks:
                if "nextMediaAfterNodeId" in block and block["nextMediaAfterNodeId"]:
                    node_id = block["nextMediaAfterNodeId"].get("id")
                    if node_id:
                        next_node = node_id
                        break
            
            if next_node:
                current_node = next_node
                time.sleep(0.5)
            else:
                break
                
        except Exception as e:
            break

    return remaining_photos


def extract_data_blocks(raw_text):
    """Extract all 'data' blocks from raw text"""
    blocks = []
    i = 0
    n = len(raw_text)

    while True:
        idx = raw_text.find('"data"', i)
        if idx == -1:
            break

        brace_start = raw_text.find('{', idx)
        if brace_start == -1:
            break

        depth = 0
        for j in range(brace_start, n):
            if raw_text[j] == '{':
                depth += 1
            elif raw_text[j] == '}':
                depth -= 1
                if depth == 0:
                    block_text = raw_text[brace_start:j+1]
                    try:
                        block = json.loads(block_text)
                        blocks.append(block)
                    except Exception:
                        pass
                    i = j + 1
                    break
        else:
            break

    return blocks


def clean_data_blocks(blocks):
    """Clean unwanted keys from data blocks"""
    cleaned = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        block.pop("errors", None)
        block.pop("extensions", None)

        cleaned.append(block)

    return cleaned


def parse_fb_response(text):
    """Parse Facebook response using the same logic as post_scraper"""
    text = text.replace("for (;;);", "").strip()
    extracted = extract_data_blocks(text)
    cleaned = clean_data_blocks(extracted)
    return cleaned


def extract_comment_count(node):
    """Extract comment count from post node"""
    try:
        # Path 1: feedback.comment_rendering_instance.comments.total_count
        v = _safe(node, 'feedback', 'comment_rendering_instance', 'comments', 'total_count')
        if v is not None: return v

        # Path 2-3: via story_ufi_container chain
        v = _safe(node, 'comet_sections', 'feedback', 'story', 'story_ufi_container', 'story',
                  'feedback_context', 'feedback_target_with_context',
                  'comment_rendering_instance', 'comments', 'total_count')
        if v is not None: return v

        v = _safe(node, 'comet_sections', 'feedback', 'story', 'story_ufi_container', 'story',
                  'feedback_context', 'feedback_target_with_context',
                  'comet_ufi_summary_and_actions_renderer', 'feedback',
                  'comment_rendering_instance', 'comments', 'total_count')
        if v is not None: return v

        # Path 4: old structure without story_ufi_container
        v = _safe(node, 'comet_sections', 'feedback', 'story',
                  'feedback_context', 'feedback_target_with_context',
                  'comment_rendering_instance', 'comments', 'total_count')
        if v is not None: return v

        # Path 5: comments_count_summary_renderer
        v = _safe(node, 'feedback', 'comments_count_summary_renderer', 'feedback',
                  'comment_rendering_instance', 'comments', 'total_count')
        if v is not None: return v

        # Path 6: full chain with comments_count_summary_renderer
        v = _safe(node, 'comet_sections', 'feedback', 'story', 'story_ufi_container', 'story',
                  'feedback_context', 'feedback_target_with_context',
                  'comet_ufi_summary_and_actions_renderer', 'feedback',
                  'comments_count_summary_renderer', 'feedback',
                  'comment_rendering_instance', 'comments', 'total_count')
        if v is not None: return v

        return 0
    except Exception:
        return 0


def is_reel_or_video_post(node):
    """Check if the post is a reel or video post"""
    if not node or node.get('__typename') != 'Story':
        return False
    
    # Check for reel in story type or anywhere in node
    node_typename = node.get('__typename', '')
    if 'reel' in node_typename.lower():
        return True
    
    # Check comet_sections for reel content
    comet_sections = node.get('comet_sections', {})
    content = comet_sections.get('content', {})
    
    content_typename = content.get('__typename', '')
    if 'reel' in content_typename.lower():
        return True
    
    # Check attachments for video/reel content
    attachments = node.get('attachments', [])
    for attachment in attachments:
        # Check for video media type
        if 'media' in attachment and attachment['media'].get('__typename') == 'Video':
            return True
        
        # Check for reel substring in media object
        if 'media' in attachment and 'reel' in str(attachment['media']).lower():
            return True
        
        # Check in styles > attachment > media for video or reel
        styles_media = attachment.get('styles', {}).get('attachment', {}).get('media', {})
        if styles_media.get('__typename') == 'Video':
            return True
        if 'reel' in str(styles_media).lower():
            return True
        
        # Check all_subattachments for videos or reels
        for subattachment in attachment.get('all_subattachments', {}).get('nodes', []):
            if 'media' in subattachment and subattachment['media'].get('__typename') == 'Video':
                return True
            if 'media' in subattachment and 'reel' in str(subattachment['media']).lower():
                return True
    
    return False


def extract_media(node, post_id=None, save_dir=None):
    """Extract photo and video URLs from a post without downloading to disk"""
    media = {
        'photos': [],
        'videos': []
    }
    
    image_index = 0
    last_media_id = None
    
    attachments = node.get('attachments', [])
    
    for attachment in attachments:
        # Handle photo attachments
        if 'media' in attachment and attachment['media'].get('__typename') == 'Photo':
            photo_data = attachment.get('styles', {}).get('attachment', {}).get('media', {})
            if 'photo_image' in photo_data:
                image_index += 1
                media_id = attachment['media'].get('id')
                last_media_id = media_id
                image_url = photo_data['photo_image'].get('uri')
                media['photos'].append({
                    'id': media_id,
                    'url': image_url,
                    'width': photo_data['photo_image'].get('width'),
                    'height': photo_data['photo_image'].get('height'),
                    'saved_as': None
                })
        
        # Handle albums (multiple photos)
        if 'all_subattachments' in attachment:
            for subattachment in attachment.get('all_subattachments', {}).get('nodes', []):
                if 'media' in subattachment and subattachment['media'].get('__typename') == 'Photo':
                    image_index += 1
                    photo_data = subattachment.get('media', {})
                    media_id = photo_data.get('id')
                    last_media_id = media_id
                    if 'image' in photo_data:
                        image_url = photo_data['image'].get('uri')
                        media['photos'].append({
                            'id': media_id,
                            'url': image_url,
                            'width': photo_data['image'].get('width'),
                            'height': photo_data['image'].get('height'),
                            'saved_as': None
                        })
        
        # Handle video attachments
        if 'media' in attachment and attachment['media'].get('__typename') == 'Video':
            video_data = attachment.get('media', {})
            media['videos'].append({
                'id': video_data.get('id'),
                'url': video_data.get('playable_url'),
                'thumbnail': video_data.get('preferred_thumbnail', {}).get('image', {}).get('uri')
            })
    
    # Fetch remaining images if we have exactly 5 photos
    if image_index == 5 and last_media_id:
        remaining_photos = fetch_remaining_images(last_media_id, post_id, image_index, save_dir)
        media['photos'].extend(remaining_photos)
    
    return media


def post_already_exists(post_id, base_folder=None):
    """Check if a post has already been scraped in SQLite"""
    if not post_id:
        return False
    return database.post_exists(str(post_id))


def extract_story_post_id(node):
    """Trích xuất post_id từ nhiều nguồn khả dĩ trong Story node của Facebook GraphQL"""
    if not node or not isinstance(node, dict):
        return None
    
    # 1. Trực tiếp từ post_id
    if node.get('post_id'):
        return str(node['post_id']).strip()
    
    # 2. legacy_story_hideable_id
    if node.get('legacy_story_hideable_id'):
        return str(node['legacy_story_hideable_id']).strip()

    # 3. legacy_fbid
    if node.get('legacy_fbid'):
        return str(node['legacy_fbid']).strip()

    # 4. feedback legacy_token
    feedback = node.get('feedback', {})
    if isinstance(feedback, dict) and feedback.get('legacy_token'):
        return str(feedback['legacy_token']).strip()

    # 5. Regex từ permalink_url hoặc url
    permalink = node.get('permalink_url') or node.get('url') or ''
    if permalink:
        for p in [r'/posts/(\d+)', r'/permalink/(\d+)', r'story_fbid=([^&]+)', r'fbid=(\d+)', r'multi_permalinks=(\d+)']:
            m = re.search(p, str(permalink))
            if m:
                return m.group(1).strip()

    # 6. Base64 decode feedback id (e.g. feedback:<post_id>)
    feedback_id = feedback.get('id') if isinstance(feedback, dict) else None
    if feedback_id and isinstance(feedback_id, str):
        try:
            import base64
            decoded = base64.b64decode(feedback_id).decode('utf-8', errors='ignore')
            if 'feedback:' in decoded:
                f_id = decoded.split('feedback:', 1)[1].strip()
                if f_id.isdigit():
                    return f_id
        except Exception:
            pass

    # 7. Base64 decode node id
    node_id = node.get('id')
    if node_id and isinstance(node_id, str):
        if node_id.isdigit():
            return node_id
        try:
            import base64
            decoded = base64.b64decode(node_id).decode('utf-8', errors='ignore')
            for prefix in ['Story:', 'post:', 'feedback:']:
                if prefix in decoded:
                    sub_id = decoded.split(prefix, 1)[1].strip()
                    if sub_id.isdigit():
                        return sub_id
        except Exception:
            pass

    return None


def extract_post_data(node, group_name=None):
    """Extract relevant data from a post node (in-memory only, no disk files)"""
    if not node or node.get('__typename') != 'Story':
        return None

    # 1. Trích xuất post_id từ direct property trước (như mã nguồn cũ), fallback sang extract_story_post_id
    post_id = node.get('post_id')
    if not post_id:
        post_id = extract_story_post_id(node)
    if not post_id:
        return None
    post_id = str(post_id).strip()

    content_story = _safe(node, 'comet_sections', 'content', 'story') or {}

    message = ''
    message_obj = content_story.get('message') if isinstance(content_story, dict) else None
    if isinstance(message_obj, dict):
        message = message_obj.get('text', '') or ''
    if not message:
        comet_msg = _safe(node, 'comet_sections', 'message', 'story', 'message')
        if isinstance(comet_msg, dict):
            message = comet_msg.get('text', '') or ''
        elif isinstance(node.get('message'), dict):
            message = (node.get('message') or {}).get('text', '') or ''

    comment_count = extract_comment_count(node)

    if not group_name:
        group_name = extract_group_name(node)

    creation_time = extract_creation_time(node)
    permalink = node.get('permalink_url') or f"https://www.facebook.com/groups/{GROUP_ID}/posts/{post_id}/"

    media_data = extract_media(node, post_id)
    post_data = {
        'id': node.get('id') or post_id,
        'post_id': post_id,
        'message': message,
        'text': message,
        'comment_count': comment_count,
        'group_name': group_name,
        'permalink': permalink,
        'creation_time': creation_time,
        'photos': media_data.get('photos', []),
        'videos': media_data.get('videos', [])
    }

    return post_data


def retry_request(url, headers, data, proxies=None, cookies=None, fb_dtsg=None, max_retries=5):
    """Make a POST request with retry logic (Thread-safe)"""
    global PROXIES
    req_proxies = proxies if proxies is not None else PROXIES
    req_cookies = cookies if cookies is not None else COOKIES
    req_dtsg = fb_dtsg if fb_dtsg is not None else FB_DTSG
    from src.core.proxy_utils import rotate_static_proxy, is_proxy_infra_error, is_ip_blocked

    for attempt in range(1, max_retries + 1):
        try:
            r = requests.post(url, headers=headers, data=data, proxies=req_proxies, cookies=req_cookies, timeout=30)
            # Detect expired cookies — try refresh, then fallback to anonymous
            if r.status_code == 200 and _is_cookie_expired(r):
                if isinstance(req_cookies, dict) and req_cookies.get("c_user"):
                    print(f"  ⚠️ Cookies hết hạn (error 1357004). Đang thử refresh qua headless browser...")
                    try:
                        from src.core.group_fetcher import refresh_cookies_via_browser
                        new_cookies, new_cookie_str, new_dtsg, new_raw_json = refresh_cookies_via_browser(req_cookies, headless=True)
                        if new_cookies and new_cookies.get("c_user"):
                            req_cookies = new_cookies
                            req_dtsg = new_dtsg
                            # Cập nhật payload với cookies mới
                            data = {**data, "av": req_cookies.get("c_user", "0"), "__user": req_cookies.get("c_user", "0"), "fb_dtsg": req_dtsg or ""}
                            # Lưu cookies mới vào DB
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
                            r = requests.post(url, headers=headers, data=data, proxies=req_proxies, cookies=req_cookies, timeout=30)
                            if r.status_code == 200 and not _is_cookie_expired(r):
                                return r
                    except Exception as e:
                        print(f"  ⚠️ Refresh cookies thất bại: {e}")
                # Fallback: anonymous mode
                print(f"  🔓 Chuyển sang chế độ ẩn danh (không cookies)...")
                req_cookies = {}
                req_dtsg = ""
                data = {**data, "av": "0", "__user": "0", "fb_dtsg": ""}
                r = requests.post(url, headers=headers, data=data, proxies=req_proxies, cookies={}, timeout=30)
            if r.status_code == 200:
                return r
            if is_proxy_infra_error(status_code=r.status_code):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy auth failed (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    req_proxies = new_p
            elif is_ip_blocked(status_code=r.status_code, response_text=r.text):
                print(f"  🛑 Attempt {attempt}/{max_retries}: Facebook blocked this IP (HTTP {r.status_code}) — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    req_proxies = new_p
            else:
                print(f"  ⚠️ Attempt {attempt}/{max_retries}: Status {r.status_code}")
        except requests.exceptions.ProxyError:
            print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy unreachable — rotating static proxy...")
            new_p = rotate_static_proxy()
            if new_p:
                req_proxies = new_p
        except Exception as e:
            if is_proxy_infra_error(exc=e):
                print(f"  🚫 Attempt {attempt}/{max_retries}: Proxy connection error — rotating static proxy...")
                new_p = rotate_static_proxy()
                if new_p:
                    req_proxies = new_p
            else:
                print(f"  ⚠️ Attempt {attempt}/{max_retries}: {str(e)}")

        if attempt < max_retries:
            wait_time = attempt * 2
            print(f"  ⏳ Retrying in {wait_time} seconds...")
            time.sleep(wait_time)

    raise Exception(f"Failed after {max_retries} attempts")


def fetch_posts(limit=10, min_comments=0, batch_size=10, on_batch_complete=None, group_id=None, group_name=None, cookies=None, fb_dtsg=None, logger=None, target_count=None, cutoff_time=None, proxies=None):
    """Fetch posts from Facebook group (Thread-safe & Cutoff Time Support)
    
    Args:
        limit: Maximum number of posts to fetch
        min_comments: Minimum number of comments required for a post to be included (0 = no filter)
        batch_size: Number of posts to fetch before calling on_batch_complete callback
        on_batch_complete: Optional callback function(batch_posts, total_so_far, limit) called after each batch
        group_id: Optional Group ID
        group_name: Optional group name to associate with scraped posts
        cookies: Optional cookies dictionary
        fb_dtsg: Optional fb_dtsg token
        logger: Optional logging callback
        target_count: Alias for limit (for backward compatibility)
        cutoff_time: Optional Unix timestamp (seconds) - skip posts older than cutoff and stop
        proxies: Optional proxy dict
    """
    curr_limit = target_count if (target_count is not None and (limit == 10 or limit is None)) else (limit or 10)
    curr_group_id = str(group_id) if group_id else GROUP_ID
    curr_group_name = group_name.strip() if (group_name and str(group_name).strip()) else None
    curr_cookies = cookies if cookies is not None else COOKIES
    curr_dtsg = fb_dtsg if fb_dtsg is not None else FB_DTSG
    curr_proxies = proxies if proxies is not None else PROXIES

    def log(msg: str):
        if logger:
            logger(str(msg))
        else:
            print(str(msg))

    all_posts = []
    batch_posts = []
    cursor = None
    page_num = 1
    reached_cutoff = False
    
    if min_comments > 0:
        log(f"📊 Filtering posts with at least {min_comments} comments")
    
    if batch_size > 0 and batch_size < curr_limit:
        log(f"📦 Processing in batches of {batch_size} posts")

    if cutoff_time:
        cutoff_str = time.strftime('%d/%m/%Y %H:%M', time.localtime(int(cutoff_time)))
        log(f"⏰ Giới hạn thời gian bài viết: từ {cutoff_str} trở lại đây")
    
    headers = {
        "user-agent": "Mozilla/5.0",
        "content-type": "application/x-www-form-urlencoded",
        "origin": "https://www.facebook.com",
        "referer": f"https://www.facebook.com/groups/{curr_group_id}/",
    }

    while len(all_posts) < curr_limit and not reached_cutoff:
        log(f"📄 Đang tải trang bài viết {page_num} qua GraphQL (Nhóm ID: {curr_group_id})...")

        fetch_count = max(3, min(curr_limit - len(all_posts), 10))
        variables = {
            "count": fetch_count,
            "cursor": cursor,
            "feedLocation": "GROUP",
            "feedType": "DISCUSSION",
            "feedbackSource": 0,
            "filterTopicId": None,
            "focusCommentID": None,
            "privacySelectorRenderLocation": "COMET_STREAM",
            "renderLocation": "group",
            "scale": 2,
            "stream_initial_count": 1,
            "useDefaultActor": False,
            "id": curr_group_id,
        }

        payload = {
            "av": curr_cookies.get("c_user", "0") if isinstance(curr_cookies, dict) else "0",
            "__user": curr_cookies.get("c_user", "0") if isinstance(curr_cookies, dict) else "0",
            "__a": "1",
            "fb_dtsg": curr_dtsg if curr_dtsg else "",
            "doc_id": DOC_ID,
            "variables": json.dumps(variables),
        }

        # Retry loop for empty response handling
        max_empty_retries = 3
        empty_retry_count = 0
        data = []

        while empty_retry_count < max_empty_retries:
            try:
                r = retry_request(GRAPHQL_URL, headers, payload, curr_proxies, cookies=curr_cookies, fb_dtsg=curr_dtsg)
                r.raise_for_status()
            except requests.RequestException as e:
                log(f"❌ GraphQL Request failed: {e}")
                break

            # Parse the response
            data = parse_fb_response(r.text)

            if data and len(data) > 0:
                break
            else:
                empty_retry_count += 1
                if empty_retry_count < max_empty_retries:
                    log(f"  ⚠️ Facebook trả về dữ liệu rỗng, đang thử lại ({empty_retry_count}/{max_empty_retries})...")
                    time.sleep(2)
                else:
                    log(f"  ❌ Không nhận được dữ liệu sau {max_empty_retries} lần thử, bỏ qua trang")
        
        if not data or len(data) == 0:
            log("❌ Không nhận được phản hồi từ Facebook GraphQL sau khi thử lại.")
            break
        
        # Extract posts from the response array
        posts_found = 0
        next_cursor = None
        
        for item in data:
            if not isinstance(item, dict):
                continue
            
            node = item.get('node', {})
            node_typename = node.get('__typename')
            
            # Collect Story nodes from multiple sources
            story_nodes = []
            
            # Direct Story node
            if node_typename == 'Story':
                story_nodes.append(node)

            # Story nodes & page_info inside Group edges / group_feed
            elif node_typename == 'Group' or 'group_feed' in node or 'edges' in node:
                group_feed = node.get('group_feed', {}) if 'group_feed' in node else node
                edges = group_feed.get('edges', [])
                for edge in edges:
                    edge_node = edge.get('node', {}) if isinstance(edge, dict) else {}
                    if edge_node and edge_node.get('__typename') == 'Story':
                        story_nodes.append(edge_node)
                p_info = group_feed.get('page_info')
                if p_info and p_info.get('has_next_page'):
                    next_cursor = p_info.get('end_cursor')
            
            # Process all found Story nodes
            for story_node in story_nodes:
                # Skip reels and video posts
                if is_reel_or_video_post(story_node):
                    continue
                
                # Kiểm tra cutoff time
                if cutoff_time:
                    post_ts = extract_creation_time(story_node)
                    if post_ts:
                        try:
                            if int(post_ts) < int(cutoff_time):
                                t_str = time.strftime('%d/%m/%Y %H:%M', time.localtime(int(post_ts)))
                                log(f"  🛑 Bài viết cũ hơn mốc thời gian lọc (đăng lúc {t_str}) -> Dừng quét thêm.")
                                reached_cutoff = True
                                break
                        except Exception:
                            pass
                
                # Check comment count threshold
                comment_count = extract_comment_count(story_node)
                if min_comments > 0 and comment_count < min_comments:
                    log(f"  ⏭️ Bỏ qua bài viết chỉ có {comment_count} bình luận (yêu cầu tối thiểu {min_comments}+)")
                    continue
                
                # Extract group name from first post if not set
                if not curr_group_name:
                    curr_group_name = extract_group_name(story_node)
                    if curr_group_name:
                        log(f"📂 Tên nhóm: {curr_group_name}")
                
                # Check if post already exists
                temp_post_id = extract_story_post_id(story_node)
                is_existing = post_already_exists(temp_post_id) if temp_post_id else False
                if is_existing and temp_post_id:
                    log(f"  ℹ️ Bài viết {temp_post_id} đã có trong CSDL -> sẽ cào để cập nhật bình luận")
                
                post_data = extract_post_data(story_node, curr_group_name)
                if post_data:
                    post_data['is_existing'] = is_existing
                    batch_posts.append(post_data)
                    all_posts.append(post_data)
                    posts_found += 1
                    status_str = "đã tồn tại -> cập nhật" if is_existing else "mới"
                    log(f"  ✅ Tìm thấy bài viết: {post_data['post_id']} ({status_str}) - {comment_count} cmt")
                    
                    # Check if we should process this batch
                    if batch_size > 0 and len(batch_posts) >= batch_size and on_batch_complete:
                        log(f"📦 Hoàn thành nhóm bài: {len(batch_posts)} bài. Tổng: {len(all_posts)}/{curr_limit}")
                        on_batch_complete(batch_posts, len(all_posts), curr_limit)
                        batch_posts = []  # Reset batch
                    
                    if len(all_posts) >= curr_limit:
                        break
            
            # Break outer loop if limit reached
            if len(all_posts) >= curr_limit or reached_cutoff:
                break
            
            # Look for pagination info
            if 'page_info' in item:
                page_info = item['page_info']
                if page_info.get('has_next_page'):
                    next_cursor = page_info.get('end_cursor')
        
        log(f"   => Lấy được {posts_found} bài viết ở trang {page_num}")
        
        # Check if we should continue
        if reached_cutoff or not next_cursor or len(all_posts) >= curr_limit:
            log("🏁 Đã lấy đủ số lượng bài viết yêu cầu hoặc đã hết trang/đạt mốc thời gian.")
            break
        
        cursor = next_cursor
        page_num += 1
        time.sleep(1)  # Be nice to the server
    
    # Process any remaining posts in the final batch
    if batch_posts and on_batch_complete:
        log(f"📦 Xử lý nhóm bài cuối: {len(batch_posts)} bài.")
        on_batch_complete(batch_posts, len(all_posts), curr_limit)
    
    return all_posts


if __name__ == "__main__":
    count = int(input("How many posts to fetch? "))
    
    print(f"\nFetching {count} posts from group {GROUP_ID}...")
    posts = fetch_posts(count)
    
    # Save posts to file
    with open("group_posts.json", "w", encoding="utf-8") as f:
        json.dump(posts, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Saved {len(posts)} posts to group_posts.json")
    
    # Print summary
    print("\nSummary:")
    for i, post in enumerate(posts, 1):
        photos = len(post['photos'])
        videos = len(post['videos'])
        print(f"{i}. Post ID: {post['post_id']}")
        if photos:
            print(f"   📷 {photos} photo(s)")
        if videos:
            print(f"   🎥 {videos} video(s)")
        if post['message']:
            preview = post['message'][:100] + '...' if len(post['message']) > 100 else post['message']
            print(f"   {preview}")
