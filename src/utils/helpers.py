import re
import requests
from src.core.proxy_utils import select_proxy
from src.database.repository import save_or_update_post, save_media

def parse_cookies(cookie_string: str) -> dict:
    """Chuyển đổi chuỗi cookie định dạng key1=value1; key2=value2 thành dict"""
    cookies = {}
    if not cookie_string:
        return cookies
    for item in cookie_string.split(";"):
        item = item.strip()
        if "=" in item:
            k, v = item.split("=", 1)
            cookies[k.strip()] = v.strip()
    return cookies

def extract_user_id_from_url(url: str, cookies: dict = None) -> str:
    url_patterns = [
        r'profile\.php\?id=(\d+)',
        r'/profile/(\d+)',
        r'id=(\d+)'
    ]
    for pattern in url_patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        proxies = select_proxy(bool(cookies))
        resp = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=20)
        html = resp.text
        patterns = [
            r'"userID":"(\d+)"',
            r'"user_id":"(\d+)"',
            r'"actorID":"(\d+)"',
            r'"entity_id":"(\d+)"',
            r'/profile/(\d+)',
            r'profile\.php\?id=(\d+)'
        ]
        for p in patterns:
            m = re.search(p, html)
            if m:
                return m.group(1)
    except Exception:
        pass
    return None

def extract_clean_group_url(url: str) -> str:
    """
    Trích xuất URL gốc của group từ URL group hoặc URL bài viết trong group.
    """
    if not url:
        return ""
    url = url.strip()
    match = re.search(r'(https?://(?:www\.|m\.|web\.|mbasic\.)?facebook\.com/groups/[^/?#]+)', url)
    if match:
        return match.group(1).rstrip('/') + '/'
    match_slug = re.search(r'/groups/([^/?#]+)', url)
    if match_slug:
        return f"https://www.facebook.com/groups/{match_slug.group(1)}/"
    return url


def extract_group_id_from_url(url: str, cookies: dict = None) -> str:
    """Extract Facebook Group ID from a group URL or post URL (supports numeric ID and vanity/slug names)"""
    details = resolve_group_details(url, cookies=cookies)
    return details.get("group_id") or ""


def resolve_group_details(url: str, cookies: dict = None) -> dict:
    """
    Phân giải URL nhóm Facebook (kể cả dạng slug, share link, post link) thành ID số và tên nhóm.
    
    Returns:
        dict: {"group_id": str, "name": str, "url": str, "resolved": bool}
    """
    if not url:
        return {"group_id": "", "name": "", "url": "", "resolved": False}
    
    url = str(url).strip()
    
    # 1. Pure numeric ID (vd: 537025796854061)
    if url.isdigit() and len(url) >= 4:
        return {
            "group_id": url,
            "name": "",
            "url": f"https://www.facebook.com/groups/{url}/",
            "resolved": True
        }
    
    # 2. Check if URL contains direct numeric ID: /groups/123456789
    m_numeric = re.search(r'/groups/(\d{4,})(?:/|posts|permalink|\?|#|$)', url)
    if m_numeric:
        gid = m_numeric.group(1)
        return {
            "group_id": gid,
            "name": "",
            "url": f"https://www.facebook.com/groups/{gid}/",
            "resolved": True
        }

    # Query param group_id or gid
    m_param = re.search(r'[?&](?:group_id|gid)=(\d{4,})', url)
    if m_param:
        gid = m_param.group(1)
        return {
            "group_id": gid,
            "name": "",
            "url": f"https://www.facebook.com/groups/{gid}/",
            "resolved": True
        }

    # Extract slug
    slug = ""
    m_slug = re.search(r'/groups/([a-zA-Z0-9._-]+)', url)
    if m_slug:
        slug = m_slug.group(1).strip()
        if slug in ('create', 'discover', 'feed', 'notifications', 'joins'):
            return {"group_id": "", "name": "", "url": url, "resolved": False}
    elif not url.startswith("http") and not "/" in url:
        slug = url

    clean_url = f"https://www.facebook.com/groups/{slug}/" if slug else url

    # 3. Phân giải slug qua request HTTP (Mobile endpoint trước vì nhẹ và có deep links)
    proxies = select_proxy(bool(cookies))
    mobile_headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    desktop_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    found_id = ""
    found_name = ""

    def parse_html_for_group(html: str):
        nonlocal found_id, found_name
        if not html:
            return

        # Tìm ID nhóm
        id_patterns = [
            r'fb://group/(?:id=|\?id=)?(\d{4,})',
            r'fb://group/(\d{4,})',
            r'al:android:url"\s+content="fb://group/(\d{4,})"',
            r'al:ios:url"\s+content="fb://group/(\d{4,})"',
            r'"groupID":"(\d{4,})"',
            r'"group_id":"(\d{4,})"',
            r'"groupID":(\d{4,})',
            r'"group_id":(\d{4,})',
            r'"entity_id":"(\d{4,})"',
            r'"targetID":"(\d{4,})"',
            r'"id":"(\d{4,})","__typename":"Group"',
            r'{"id":"(\d{4,})","name":"[^"]+","__typename":"Group"',
            r'/groups/(\d{4,})/'
        ]
        for pat in id_patterns:
            m = re.search(pat, html)
            if m:
                found_id = m.group(1)
                break

        # Tìm Tên nhóm
        if not found_name:
            name_patterns = [
                r'<meta\s+property="og:title"\s+content="([^"]+)"',
                r'<title>([^<]+)</title>',
                r'"name":"([^"]+)","__typename":"Group"',
                r'"group_name":"([^"]+)"'
            ]
            for pat in name_patterns:
                m = re.search(pat, html)
                if m:
                    import html
                    raw_title = html.unescape(m.group(1)).strip()
                    # Làm sạch title Facebook (vd: "Cộng Đồng In 3D | Facebook")
                    raw_title = re.sub(r'\s*\|\s*Facebook\s*$', '', raw_title, flags=re.IGNORECASE)
                    raw_title = re.sub(r'^\(\d+\)\s*', '', raw_title)
                    if raw_title and not raw_title.lower().startswith("facebook"):
                        found_name = raw_title
                        break

    # Thử qua mobile URL
    target_m_url = f"https://m.facebook.com/groups/{slug}/" if slug else url.replace("www.facebook.com", "m.facebook.com")
    try:
        r_m = requests.get(target_m_url, headers=mobile_headers, cookies=cookies, proxies=proxies, timeout=12)
        if r_m.status_code == 200:
            parse_html_for_group(r_m.text)
    except Exception:
        pass

    # Fallback qua desktop URL nếu chưa tìm thấy ID
    if not found_id:
        target_d_url = f"https://www.facebook.com/groups/{slug}/" if slug else url
        try:
            r_d = requests.get(target_d_url, headers=desktop_headers, cookies=cookies, proxies=proxies, timeout=15)
            if r_d.status_code == 200:
                parse_html_for_group(r_d.text)
        except Exception:
            pass

    # Fallback qua Headless Browser nếu HTTP vẫn chưa tìm thấy ID hoặc tên (dành cho nhóm riêng tư / login wall)
    if not found_id or not found_name:
        try:
            import time
            from seleniumbase import Driver
            browser_driver = Driver(browser="chrome", headless=True, uc=True)
            try:
                if cookies and isinstance(cookies, dict):
                    browser_driver.get("https://www.facebook.com/404")
                    for c_name, c_val in cookies.items():
                        try:
                            browser_driver.add_cookie({
                                "name": c_name,
                                "value": c_val,
                                "domain": ".facebook.com",
                                "path": "/"
                            })
                        except Exception:
                            pass
                b_url = f"https://www.facebook.com/groups/{slug}/" if slug else url
                browser_driver.get(b_url)
                time.sleep(2.5)
                b_html = browser_driver.page_source
                parse_html_for_group(b_html)
                if not found_name:
                    b_title = browser_driver.title or ""
                    import html
                    b_title = html.unescape(b_title)
                    b_title = re.sub(r'\s*\|\s*Facebook\s*$', '', b_title, flags=re.IGNORECASE)
                    b_title = re.sub(r'^\(\d+\)\s*', '', b_title).strip()
                    if b_title and not b_title.lower().startswith("facebook"):
                        found_name = b_title
            finally:
                browser_driver.quit()
        except Exception:
            pass

    resolved_id = found_id if found_id else (slug if slug.isdigit() else "")
    canonical_url = f"https://www.facebook.com/groups/{resolved_id}/" if resolved_id else clean_url

    return {
        "group_id": resolved_id,
        "name": found_name,
        "url": canonical_url,
        "resolved": bool(resolved_id)
    }

def extract_post_id_from_url(url: str) -> str:
    patterns = [
        r'posts/(\d+)',
        r'permalink/(\d+)',
        r'story_fbid=([^&]+)',
        r'fbid=(\d+)',
        r'/(\d+)/\?mibextid'
    ]
    for p in patterns:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None

def save_post_data(post_type: str, post_id: str, post_data: dict, comments_data: list = None, db_path: str = None) -> dict:
    return save_or_update_post(post_type, post_id, post_data, comments_data, db_path=db_path)


def get_app_icon_path() -> str:
    """Trả về đường dẫn tuyệt đối đến file icon ứng dụng (.ico, .png, hoặc .svg)"""
    import os
    import sys
    # Support PyInstaller bundle directory or dev source directory
    base_dir = getattr(sys, '_MEIPASS', os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    for name in ("icon.ico", "icon.png", "icon.svg"):
        candidate = os.path.join(base_dir, "assets", name)
        if os.path.exists(candidate):
            return candidate
    return ""


def get_app_icon():
    """Trả về đối tượng QIcon cho cửa sổ ứng dụng"""
    from PyQt6.QtGui import QIcon
    icon_path = get_app_icon_path()
    if icon_path:
        return QIcon(icon_path)
    return QIcon()

