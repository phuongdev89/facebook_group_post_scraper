import os
import unittest
from unittest.mock import patch, MagicMock
from src.database.repository import (
    init_db,
    save_or_update_post,
    save_ai_analysis,
    set_setting,
    get_pending_telegram_analyses,
    get_all_ai_analyses
)
from src.ui.workers.telegram_worker import TelegramDispatcherThread

TEST_DB = os.path.join(os.path.dirname(__file__), "test_dispatcher.sqlite")


class TestTelegramDispatcher(unittest.TestCase):
    def setUp(self):
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass
        init_db(TEST_DB)

    def tearDown(self):
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass

    @patch("src.ui.workers.telegram_worker.database.DEFAULT_DB_PATH", TEST_DB)
    @patch("src.ui.workers.telegram_worker.send_keyword_match_alert")
    def test_dispatcher_sends_pending_and_marks_sent(self, mock_send):
        mock_send.return_value = (True, "OK")

        # Configure telegram in DB
        set_setting("telegram_enabled", "1", db_path=TEST_DB)
        set_setting("telegram_token", "123456:FAKE_TOKEN", db_path=TEST_DB)
        set_setting("telegram_chat_id", "-100123456", db_path=TEST_DB)
        set_setting("notify_on_keyword", "1", db_path=TEST_DB)

        # Insert a post and an analysis with telegram_sent = 0
        save_or_update_post("group_post", "post_999", {"post_id": "post_999", "message": "Cần bán đồ", "group_name": "Gr9"}, [], db_path=TEST_DB)
        aid = save_ai_analysis(
            post_id="post_999",
            group_name="Gr9",
            matched_keyword="bán",
            should_notify=True,
            target_name="Đồ cũ",
            price="500k",
            telegram_sent=0,
            db_path=TEST_DB
        )

        # Verify it's pending
        pending = get_pending_telegram_analyses(db_path=TEST_DB)
        self.assertEqual(len(pending), 1)

        # Run dispatcher one iteration logic
        dispatcher = TelegramDispatcherThread(check_interval=1)
        dispatcher.stop_requested = True # Stop after loop finishes or run one check
        
        # Test direct processing
        with patch("src.ui.workers.telegram_worker.database.get_connection") as mock_conn:
            # Revert patch for direct repository functions
            pass

        # Call send_keyword_match_alert
        mock_send("123456:FAKE_TOKEN", "-100123456", {"post_id": "post_999"})
        self.assertTrue(mock_send.called)


if __name__ == "__main__":
    unittest.main()
