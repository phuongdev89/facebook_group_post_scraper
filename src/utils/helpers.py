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

def extract_group_id_from_url(url: str, cookies: dict = None) -> str:
    m = re.search(r'groups/(\d+)', url)
    if m:
        return m.group(1)
    m = re.search(r'facebook\.com/groups/([^/?]+)', url)
    if not m:
        return None
    slug = m.group(1)
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        proxies = select_proxy(bool(cookies))
        resp = requests.get(url, headers=headers, cookies=cookies, proxies=proxies, timeout=20)
        html = resp.text
        patterns = [
            r'"groupID":"(\d+)"',
            r'"group_id":"(\d+)"',
            r'"entity_id":"(\d+)"',
            r'"target_id":"(\d+)"',
            r'/groups/(\d+)'
        ]
        for p in patterns:
            match = re.search(p, html)
            if match:
                return match.group(1)
    except Exception:
        pass
    return slug

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
