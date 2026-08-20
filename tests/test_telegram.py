import unittest
from unittest.mock import patch, MagicMock
from src.core.telegram_notifier import send_keyword_match_alert, send_finish_notification

class TestTelegram(unittest.TestCase):
    @patch("requests.post")
    def test_alert_formatting(self, mock_tg):
        mock_tg.return_value.status_code = 200
        mock_tg.return_value.json.return_value = {"ok": True}

        post = {"post_id": "555", "group_name": "Test Group", "message": "Bán máy"}
        ai_res = {
            "should_notify": True,
            "device_name": "Canon 2900",
            "price": "1.5tr",
            "seller_type": "Tác giả bài viết",
            "seller_snippet": "Bán máy Canon",
            "reason": "Bán máy"
        }


        ok, msg = send_keyword_match_alert(
            token="token",
            chat_id="chat_id",
            post_data=post,
            matched_keyword="bán",
            ai_result=ai_res,
            model_used="gpt-4o-mini"
        )
        self.assertTrue(ok)
        call_args = mock_tg.call_args[1]["json"]
        self.assertIn("Canon 2900", call_args["text"])
        self.assertIn("gpt-4o-mini", call_args["text"])

    @patch("requests.post")
    def test_generalized_target_alert(self, mock_tg):
        mock_tg.return_value.status_code = 200
        mock_tg.return_value.json.return_value = {"ok": True}

        post = {"post_id": "777", "group_name": "Tìm Nhà Trọ HN", "message": "Cho thuê phòng 25m2 Cầu Giấy"}
        ai_res = {
            "should_notify": True,
            "target_name": "Phòng trọ 25m2 Cầu Giấy",
            "price": "3.5tr/tháng",
            "actor_role": "Chủ nhà",
            "matched_snippet": "Cho thuê phòng 25m2 Cầu Giấy",
            "reason": "Tin cho thuê trực tiếp"
        }

        ok, msg = send_keyword_match_alert(
            token="token",
            chat_id="chat_id",
            post_data=post,
            matched_keyword="phòng",
            ai_result=ai_res,
            model_used="gemini-2.0-flash"
        )
        self.assertTrue(ok)
        call_args = mock_tg.call_args[1]["json"]
        self.assertIn("Phòng trọ 25m2 Cầu Giấy", call_args["text"])
        self.assertIn("3.5tr/tháng", call_args["text"])
        self.assertIn("Chủ nhà", call_args["text"])
        self.assertIn("gemini-2.0-flash", call_args["text"])


if __name__ == "__main__":
    unittest.main()
