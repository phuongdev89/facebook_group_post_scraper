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

    def test_parse_cookies_from_raw_string(self):
        cookie_text = "c_user=1000123456789; xs=2%3Aabc_xyz%3A2; datr=xyz123; fb_dtsg=NAcTOKEN123"
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(cookie_text)

        self.assertEqual(cookies_dict.get("c_user"), "1000123456789")
        self.assertEqual(cookies_dict.get("xs"), "2%3Aabc_xyz%3A2")
        self.assertEqual(cookies_dict.get("datr"), "xyz123")
        self.assertEqual(fb_dtsg, "NAcTOKEN123")
        self.assertIn("c_user=1000123456789", cookie_str)

    def test_parse_cookies_from_curl_command(self):
        curl_cmd = (
            "curl 'https://www.facebook.com/api/graphql/' \\\n"
            "  -H 'accept: */*' \\\n"
            "  -b 'datr=datr_val; c_user=987654321; xs=xs_val;' \\\n"
            "  --data-raw 'av=0&fb_dtsg=NAcSampleDtsgToken%3A99&lsd=lsd_val'"
        )
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(curl_cmd)

        self.assertEqual(cookies_dict.get("c_user"), "987654321")
        self.assertEqual(cookies_dict.get("xs"), "xs_val")
        self.assertEqual(cookies_dict.get("datr"), "datr_val")
        self.assertEqual(fb_dtsg, "NAcSampleDtsgToken:99")

    def test_parse_cookies_from_json_array(self):
        json_cookies = (
            '[{"name": "c_user", "value": "11223344"},'
            ' {"name": "xs", "value": "secret_xs"}]'
        )
        cookies_dict, cookie_str, fb_dtsg = parse_cookies_from_any(json_cookies)

        self.assertEqual(cookies_dict.get("c_user"), "11223344")
        self.assertEqual(cookies_dict.get("xs"), "secret_xs")
        self.assertIn("c_user=11223344", cookie_str)

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
        {"require":[["RelayModern", "preload", [], [{"__typename":"Group","id":"1001","name":"Group One","cover":{"id":"1"}},{"__typename":"Group","id":"1002","name":"Group Two","stats":{"members":500}}]]]}
        </script>
        <script>
        require("ServerJSDefine").handleDefines([[["GroupViewer", [], {"group_id":"1003","group_name":"Group Three"}]]]);
        </script>
        <a href="/groups/1004/">Group Four · 10K thành viên</a>
        <a href="https://www.facebook.com/groups/slug-group-five/">Group Five</a>
        """
        groups_map = {}
        _extract_groups_from_text(sample_html, groups_map)
        self.assertEqual(len(groups_map), 5)
        self.assertIn("https://www.facebook.com/groups/1001/", groups_map)
        self.assertEqual(groups_map["https://www.facebook.com/groups/1001/"]["name"], "Group One")

    @patch("requests.Session.get")
    def test_fetch_user_joined_groups_mock(self, mock_get):
        sample_resp = MagicMock(status_code=200, text="""
        <script type="application/json">
        [{"__typename":"Group","id":"111222333","name":"Nhóm Lập Trình Python"}]
        </script>
        <a href="/groups/cong-dong-ai/">Cộng Đồng AI Việt Nam</a>
        """)
        mock_get.return_value = sample_resp

    @patch("requests.Session.post")
    @patch("requests.Session.get")
    def test_fetch_user_joined_groups_graphql_pagination(self, mock_get, mock_post):
        # 1. Desktop Initial HTML returns 1 group and an end_cursor
        initial_html = """
        <script type="application/json">
        {"all_joined_groups": {"tab_groups_list": {"page_info": {"end_cursor": "cursor_page_1", "has_next_page": true}}}}
        </script>
        <script type="application/json">
        [{"__typename":"Group","id":"10001","name":"Group Page 0"}]
        </script>
        <input name="fb_dtsg" value="token_sample_123" />
        """
        mock_get.return_value = MagicMock(status_code=200, text=initial_html)

        # 2. GraphQL Pagination response returns page 2 group
        page1_resp = json.dumps({
            "data": {
                "viewer": {
                    "all_joined_groups": {
                        "tab_groups_list": {
                            "page_info": {"end_cursor": "cursor_page_2", "has_next_page": False},
                            "edges": [
                                {"node": {"__typename": "Group", "id": "10002", "name": "Group Page 1"}}
                            ]
                        }
                    }
                }
            }
        })
        mock_post.return_value = MagicMock(status_code=200, text=page1_resp)

        cookies = {"c_user": "1000", "xs": "abc"}
        groups = fetch_user_joined_groups(cookies, fb_dtsg="token_sample_123", max_pages=5)

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
