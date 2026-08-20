import os
import re
import random
import requests

STATIC_PORT_MIN = 10000
STATIC_PORT_MAX = 10000


def normalize_proxy_url(proxy_str: str) -> str:
    """
    Chuẩn hóa chuỗi proxy nhập vào theo định dạng requests hợp lệ.
    Hỗ trợ các định dạng:
      - username:password@ip_address:port -> http://username:password@ip_address:port
      - ip_address:port -> http://ip_address:port
      - http://... hoặc socks5://... (giữ nguyên protocol)
    """
    if not proxy_str:
        return ""
    p = proxy_str.strip()
    if not p:
        return ""
    
    # Kiểm tra xem đã có protocol (http://, https://, socks5://, socks4://) chưa
    if not re.match(r'^(?:http|https|socks4|socks5)://', p, re.IGNORECASE):
        p = f"http://{p}"
    return p


def _get_configured_proxy(key: str = 'proxy') -> str:
    """Lấy cấu hình proxy từ SQLite settings, fallback sang OS environment variables nếu có"""
    try:
        from src.database.repository import get_setting
        val = get_setting(key)
        if val and val.strip():
            return normalize_proxy_url(val.strip())
        # Fallback to alternative keys for backward compatibility
        if key == 'proxy':
            for alt_key in ('static_proxy', 'rotating_proxy'):
                alt_val = get_setting(alt_key)
                if alt_val and alt_val.strip():
                    return normalize_proxy_url(alt_val.strip())
    except Exception:
        pass

    env_val = os.getenv(key.upper(), '').strip()
    if env_val:
        return normalize_proxy_url(env_val)
    if key == 'proxy':
        for alt_env in ('STATIC_PROXY', 'ROTATING_PROXY'):
            val = os.getenv(alt_env, '').strip()
            if val:
                return normalize_proxy_url(val)
    return ""


def _replace_trailing_port(proxy_url: str, port: int) -> str:
    """Replace only the last :port part of a proxy URL if present."""
    head, sep, tail = proxy_url.rpartition(':')
    if not sep or not tail.isdigit():
        return proxy_url
    return f"{head}:{port}"


def _build_proxy_dict(proxy_url: str):
    norm = normalize_proxy_url(proxy_url)
    return {'http': norm, 'https': norm} if norm else None


def rotate_static_proxy():
    """
    Pick a brand-new random static port and return a fresh proxy dict.
    Call this whenever a static proxy appears blocked or unreachable.
    Returns None if proxy is not configured.
    """
    proxy_base = _get_configured_proxy('proxy')
    if not proxy_base:
        return None

    port = random.randint(STATIC_PORT_MIN, STATIC_PORT_MAX)
    proxy_url = _replace_trailing_port(proxy_base, port)
    print(f"  🔁 Proxy rotated → ({proxy_url})")
    return _build_proxy_dict(proxy_url)


def is_proxy_infra_error(exc=None, status_code=None) -> bool:
    """
    True when the *proxy itself* is broken / unreachable / rejected the conn.
    HTTP 407 = proxy auth required (credentials wrong or expired)
    ProxyError / tunnel / connection refused = proxy host down or port dead
    """
    if status_code == 407:
        return True
    if exc is not None:
        if isinstance(exc, (requests.exceptions.ProxyError,
                            requests.exceptions.ConnectionError)):
            return True
        msg = str(exc).lower()
        if any(k in msg for k in ('proxy', '407', 'tunnel', 'connection refused',
                                   'cannot connect to proxy', 'eof occurred')):
            return True
    return False


def is_ip_blocked(status_code=None, response_text=None) -> bool:
    """
    True when Facebook itself rejected the request due to the outgoing IP.
    403 = IP banned / geo-blocked
    429 = rate-limited / too many requests from this IP
    503 = service unavailable (often a soft IP block or overload)
    Facebook sometimes also returns 200 with a checkpoint/login-wall body.
    """
    if status_code in (403, 429, 503):
        return True
    if response_text:
        txt = response_text[:500].lower()
        if any(k in txt for k in ('checkpoint', 'login_required',
                                   'you must log in', 'blocked')):
            return True
    return False


# Keep old name as alias so callers we haven't updated yet still work
is_proxy_error = is_proxy_infra_error


def select_proxy(has_cookies: bool = False):
    """
    Trả về requests proxy dict từ cấu hình proxy đơn nhất (không cần phân biệt public hay cookie).
    Hỗ trợ định dạng: username:pass@ip_address:port hoặc ip_address:port.
    """
    proxy_url = _get_configured_proxy('proxy')
    if not proxy_url:
        return None

    print(f"🌐 Using proxy: {proxy_url}")
    return _build_proxy_dict(proxy_url)


