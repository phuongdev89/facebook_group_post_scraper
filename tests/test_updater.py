import unittest
from unittest.mock import patch, MagicMock
from src.core.updater import parse_version, is_newer_version, check_github_update, download_update_file


class TestUpdater(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(parse_version("1.0.2"), (1, 0, 2))
        self.assertEqual(parse_version("v1.0.3"), (1, 0, 3))
        self.assertEqual(parse_version("v2.1.0-beta"), (2, 1, 0))
        self.assertEqual(parse_version(""), (0, 0, 0))
        self.assertEqual(parse_version(None), (0, 0, 0))

    def test_is_newer_version(self):
        self.assertTrue(is_newer_version("1.0.3", "1.0.2"))
        self.assertTrue(is_newer_version("v2.0.0", "1.9.9"))
        self.assertTrue(is_newer_version("1.1.0", "1.0.9"))
        self.assertFalse(is_newer_version("1.0.2", "1.0.2"))
        self.assertFalse(is_newer_version("1.0.1", "1.0.2"))
        self.assertFalse(is_newer_version("0.9.9", "1.0.0"))

    @patch("requests.get")
    def test_check_github_update_with_release_api(self, mock_get):
        # Mock successful GitHub release API response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "tag_name": "v1.5.0",
            "name": "Bản phát hành v1.5.0",
            "body": "- Sửa lỗi Telegram\n- Thêm bảng logs",
            "published_at": "2026-08-20T10:00:00Z",
            "html_url": "https://github.com/phuongdev89/facebook_post_comment_scraper/releases/tag/v1.5.0",
            "assets": [
                {
                    "name": "FacebookNotification_Patch_v1.5.0.zip",
                    "browser_download_url": "https://github.com/phuongdev89/facebook_post_comment_scraper/releases/download/v1.5.0/patch.zip"
                }
            ]
        }
        mock_get.return_value = mock_resp

        has_update, update_info, msg = check_github_update(current_version="1.0.2")
        self.assertTrue(has_update)
        self.assertEqual(update_info["latest_version"], "1.5.0")
        self.assertEqual(update_info["current_version"], "1.0.2")
        self.assertEqual(update_info["source"], "github_release")
        self.assertIn("1.5.0", msg)
        self.assertEqual(update_info["download_url"], "https://github.com/phuongdev89/facebook_post_comment_scraper/releases/download/v1.5.0/patch.zip")

    @patch("requests.get")
    def test_check_github_update_fallback_raw_json(self, mock_get):
        # First call (releases/latest) returns 404
        resp_404 = MagicMock()
        resp_404.status_code = 404

        # Second call (raw version.json) returns 200
        resp_json = MagicMock()
        resp_json.status_code = 200
        resp_json.json.return_value = {
            "version": "1.2.0",
            "release_date": "2026-08-20",
            "changelog": "Cập nhật qua raw json",
            "download_url": "https://github.com/test/download.zip"
        }
        mock_get.side_effect = [resp_404, resp_json]

        has_update, update_info, msg = check_github_update(current_version="1.0.2")
        self.assertTrue(has_update)
        self.assertEqual(update_info["latest_version"], "1.2.0")
        self.assertEqual(update_info["source"], "version_json")


if __name__ == "__main__":
    unittest.main()
