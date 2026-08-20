import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def get_app_version() -> str:
    """Lấy phiên bản hiện tại của ứng dụng từ file .version"""
    possible_paths = [
        os.path.join(PROJECT_ROOT, ".version"),
        os.path.join(getattr(sys, '_MEIPASS', ''), ".version") if hasattr(sys, '_MEIPASS') else "",
        os.path.join(os.path.dirname(sys.executable), ".version") if getattr(sys, 'frozen', False) else "",
        os.path.abspath(".version"),
    ]
    for p in possible_paths:
        if p and os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    ver = f.read().strip()
                    if ver:
                        return ver
            except Exception:
                pass
    return "1.0.2"

APP_VERSION = get_app_version()

# Data directory located in user's home folder ~/.facebook-notification
DATA_DIR = os.path.join(os.path.expanduser("~"), ".facebook-notification")
DEFAULT_DB_PATH = os.path.join(DATA_DIR, "facebook_scraper.sqlite")
CHROME_DATA_DIR = os.path.join(DATA_DIR, "chromedata")

# Legacy project data directory for backward-compatibility & auto-migration
LEGACY_DATA_DIR = os.path.join(PROJECT_ROOT, "data")
LEGACY_DB_PATH = os.path.join(LEGACY_DATA_DIR, "facebook_scraper.sqlite")

def ensure_data_dir() -> str:
    """Tạo thư mục DATA_DIR nếu chưa tồn tại"""
    os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


FACEBOOK_BASE_URL = "https://www.facebook.com"
GRAPHQL_ENDPOINT = "https://www.facebook.com/api/graphql/"

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

DEFAULT_HEADERS = {
    "User-Agent": DEFAULT_USER_AGENT,
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9,vi;q=0.8",
    "Origin": FACEBOOK_BASE_URL,
    "Referer": FACEBOOK_BASE_URL,
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty"
}
