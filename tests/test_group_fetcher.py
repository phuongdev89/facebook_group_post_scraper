import unittest
import json
from unittest.mock import patch, MagicMock
from src.core.group_fetcher import (
    parse_cookies_from_any,
    fetch_user_joined_groups,
    _clean_group_name,
    _normalize_group_url,
    _extract_groups_from_text
)


class TestGroupFetcher(unittest.TestCase):

    def test_parse_cookies_from_json_array(self):
        # Cookie-Editor export as JSON format
        json_cookies = json.dumps([
            {"name": "sb", "value": "sb_123"},
            {"name": "datr", "value": "datr_456"},
            {"name": "c_user", "value": "1000123456789"},
            {"name": "xs", "value": "2%3Aabc_xyz%3A2"}
        ])
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(json_cookies)

        self.assertEqual(cookies_dict.get("c_user"), "1000123456789")
        self.assertEqual(cookies_dict.get("xs"), "2%3Aabc_xyz%3A2")
        self.assertEqual(cookies_dict.get("datr"), "datr_456")
        self.assertEqual(cookies_dict.get("sb"), "sb_123")
        self.assertIn("c_user=1000123456789", cookie_str)

    def test_parse_cookies_from_j2team_format(self):
        j2team_data = json.dumps({
            "url": "https://www.facebook.com",
            "cookies": [
                {"name": "c_user", "value": "1000998877"},
                {"name": "xs", "value": "2%3Asecret_xs_val"},
                {"name": "datr", "value": "datr_val"}
            ]
        })
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(j2team_data)
        self.assertEqual(cookies_dict.get("c_user"), "1000998877")
        self.assertEqual(cookies_dict.get("xs"), "2%3Asecret_xs_val")

    def test_parse_cookies_from_markdown_and_trailing_commas(self):
        raw_text = "```json\n[{'name': 'c_user', 'value': '1000123'}, {'name': 'xs', 'value': '2%3Aabc'}, ]\n```"
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(raw_text)
        self.assertEqual(cookies_dict.get("c_user"), "1000123")
        self.assertEqual(cookies_dict.get("xs"), "2%3Aabc")

    def test_parse_cookies_invalid_input(self):
        # Non-cookie string should return empty dict
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any("random plain string without cookies")
        self.assertEqual(cookies_dict, {})
        self.assertEqual(cookie_str, "")

    def test_extract_groups_filters_not_joined_state(self):
        # Non-joined / suggested groups should be ignored
        payload = """
        <script type="application/json">
        [
            {"__typename": "Group", "id": "11111", "name": "Joined Group", "viewer_joined_state": "MEMBER"},
            {"__typename": "Group", "id": "22222", "name": "Suggested Group 1", "viewer_joined_state": "NOT_JOINED"},
            {"__typename": "Group", "id": "33333", "name": "Suggested Group 2", "viewer_joined_state": "CANNOT_JOIN"},
            {"__typename": "Group", "id": "44444", "name": "Requested Group", "viewer_joined_state": "REQUESTED"}
        ]
        </script>
        """
        groups_map = {}
        _extract_groups_from_text(payload, groups_map)
        self.assertEqual(len(groups_map), 1)
        self.assertIn("https://www.facebook.com/groups/11111/", groups_map)
        self.assertEqual(groups_map["https://www.facebook.com/groups/11111/"]["name"], "Joined Group")

    def test_clean_group_name_and_normalize_url(self):
        raw_name = "  H&#7897;i Mua B&aacute;n &#272;&#7891; C&#361; &middot; 50K th&agrave;nh vi&ecirc;n  "
        clean = _clean_group_name(raw_name)
        self.assertIn("Hội Mua Bán Đồ Cũ", clean)

        url, gid = _normalize_group_url("123456789")
        self.assertEqual(url, "https://www.facebook.com/groups/123456789/")
        self.assertEqual(gid, "123456789")

        url_slug, gid_slug = _normalize_group_url("lap-trinh-python-vietnam")
        self.assertEqual(url_slug, "https://www.facebook.com/groups/lap-trinh-python-vietnam/")
        self.assertEqual(gid_slug, "")

    def test_extract_groups_from_text_deep(self):
        sample_html = """
        <script type="application/json">
        {"require":[["RelayModern", "preload", [], [{"__typename":"Group","id":"1001","name":"Group One","viewer_joined_state":"MEMBER"},{"__typename":"Group","id":"1002","name":"Group Two","viewer_joined_state":"MEMBER"}]]]}
        </script>
        <script>
        require("ServerJSDefine").handleDefines([[["GroupViewer", [], {"group_id":"1003","group_name":"Group Three"}]]]);
        </script>
        """
        groups_map = {}
        _extract_groups_from_text(sample_html, groups_map)
        self.assertEqual(len(groups_map), 3)
        self.assertIn("https://www.facebook.com/groups/1001/", groups_map)
        self.assertEqual(groups_map["https://www.facebook.com/groups/1001/"]["name"], "Group One")

    def test_extract_groups_from_mbasic_html(self):
        from src.core.group_fetcher import _extract_groups_from_mbasic_html
        sample_mbasic = """
        <table role="presentation">
            <tr><td><a href="/groups/99887766/">Nhóm Mua Bán Đồ Cũ</a></td></tr>
            <tr><td><a href="/groups/lap-trinh-python/">Cộng Đồng Python</a></td></tr>
            <tr><td><a href="/groups/create/">Tạo nhóm mới</a></td></tr>
            <tr><td><a href="/groups/?seemore">Xem thêm nhóm khác</a></td></tr>
        </table>
        """
        groups_map = {}
        _extract_groups_from_mbasic_html(sample_mbasic, groups_map)
        self.assertEqual(len(groups_map), 2)
        self.assertIn("https://www.facebook.com/groups/99887766/", groups_map)
        self.assertIn("https://www.facebook.com/groups/lap-trinh-python/", groups_map)

    @patch("requests.Session.get")
    def test_fetch_user_joined_groups_mock(self, mock_get):
        sample_resp = MagicMock(status_code=200, text="""
        <script type="application/json">
        [{"__typename":"Group","id":"111222333","name":"Nhóm Lập Trình Python","viewer_joined_state":"MEMBER"}]
        </script>
        """, url="https://www.facebook.com/groups/joins/")
        mock_get.return_value = sample_resp
        cookies = {"c_user": "1000", "xs": "abc"}
        groups = fetch_user_joined_groups(cookies, fb_dtsg="token_sample_123", max_pages=1, allow_browser_fallback=False)
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["group_id"], "111222333")

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_fetch_user_joined_groups_graphql_pagination(self, mock_get, mock_post):
        # 1. Desktop Initial HTML returns 1 group and an end_cursor
        initial_html = """
        <script type="application/json">
        {"all_joined_groups": {"tab_groups_list": {"page_info": {"end_cursor": "cursor_page_1", "has_next_page": true}}}}
        </script>
        <script type="application/json">
        [{"__typename":"Group","id":"10001","name":"Group Page 0","viewer_joined_state":"MEMBER"}]
        </script>
        <input name="fb_dtsg" value="token_sample_123" />
        """
        mock_get.return_value = MagicMock(status_code=200, text=initial_html, url="https://www.facebook.com/groups/joins/")

        # 2. GraphQL Pagination response returns page 2 group
        page1_resp = json.dumps({
            "data": {
                "viewer": {
                    "all_joined_groups": {
                        "tab_groups_list": {
                            "page_info": {"end_cursor": "cursor_page_2", "has_next_page": False},
                            "edges": [
                                {"node": {"__typename": "Group", "id": "10002", "name": "Group Page 1", "viewer_joined_state":"MEMBER"}}
                            ]
                        }
                    }
                }
            }
        })
        mock_post.return_value = MagicMock(status_code=200, text=page1_resp)

        cookies = {"c_user": "1000", "xs": "abc"}
        groups = fetch_user_joined_groups(cookies, fb_dtsg="token_sample_123", max_pages=5, allow_browser_fallback=False)
        self.assertEqual(len(groups), 2)

    def test_deduplicate_and_clean_groups(self):
        from src.core.group_fetcher import _deduplicate_and_clean_groups
        raw_list = [
            # Group 1 (by ID)
            {"name": "Cuồng Tai nghe True Wireless", "url": "https://www.facebook.com/groups/750279539095674/", "group_id": "750279539095674"},
            # Group 1 duplicate (by custom vanity URL)
            {"name": "Cuồng Tai nghe True Wireless", "url": "https://www.facebook.com/groups/cuongtruewireless/", "group_id": "cuongtruewireless"},
            # Group 2
            {"name": "BambuLab Vietnam", "url": "https://www.facebook.com/groups/870045794291111/", "group_id": "870045794291111"},
            # Group 2 duplicate
            {"name": "BambuLab Vietnam", "url": "https://www.facebook.com/groups/bambulabvietnam/", "group_id": "bambulabvietnam"},
        ]

        cleaned = _deduplicate_and_clean_groups(raw_list)
        self.assertEqual(len(cleaned), 2)
        urls = [g["url"] for g in cleaned]
        self.assertIn("https://www.facebook.com/groups/cuongtruewireless/", urls)
        self.assertIn("https://www.facebook.com/groups/bambulabvietnam/", urls)
        
        # Verify IDs are resolved to numeric ID
        g1 = next(g for g in cleaned if "cuong" in g["url"])
        self.assertEqual(g1["group_id"], "750279539095674")


if __name__ == "__main__":
    unittest.main()
