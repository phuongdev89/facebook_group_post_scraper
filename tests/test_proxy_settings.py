import os
import unittest
from src.database.repository import init_db, set_setting, get_setting
from src.core.proxy_utils import _get_configured_proxy, select_proxy, normalize_proxy_url


class TestProxySettings(unittest.TestCase):
    def test_normalize_proxy_url(self):
        """Kiểm tra hàm chuẩn hóa proxy URL với các định dạng khác nhau"""
        self.assertEqual(normalize_proxy_url("user:pass@127.0.0.1:8080"), "http://user:pass@127.0.0.1:8080")
        self.assertEqual(normalize_proxy_url("127.0.0.1:8080"), "http://127.0.0.1:8080")
        self.assertEqual(normalize_proxy_url("http://user:pass@127.0.0.1:8080"), "http://user:pass@127.0.0.1:8080")
        self.assertEqual(normalize_proxy_url("socks5://user:pass@127.0.0.1:1080"), "socks5://user:pass@127.0.0.1:1080")
        self.assertEqual(normalize_proxy_url(""), "")

    def test_proxy_from_sqlite_settings(self):
        """Kiểm tra proxy được nạp trực tiếp từ SQLite settings mà không cần .env"""
        set_setting("proxy", "testuser:testpass@127.0.0.1:8080")
        self.assertEqual(_get_configured_proxy("proxy"), "http://testuser:testpass@127.0.0.1:8080")

        # Test select_proxy
        proxies_with_cookies = select_proxy(has_cookies=True)
        self.assertIsNotNone(proxies_with_cookies)
        self.assertEqual(proxies_with_cookies["http"], "http://testuser:testpass@127.0.0.1:8080")

        proxies_without_cookies = select_proxy(has_cookies=False)
        self.assertIsNotNone(proxies_without_cookies)
        self.assertEqual(proxies_without_cookies["http"], "http://testuser:testpass@127.0.0.1:8080")

        # Test simple ip:port format
        set_setting("proxy", "103.150.12.34:8080")
        proxies_ip = select_proxy()
        self.assertIsNotNone(proxies_ip)
        self.assertEqual(proxies_ip["http"], "http://103.150.12.34:8080")

        # Clear proxy setting
        set_setting("proxy", "")
        set_setting("static_proxy", "")
        set_setting("rotating_proxy", "")


if __name__ == "__main__":
    unittest.main()

