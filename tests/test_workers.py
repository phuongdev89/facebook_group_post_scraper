import os
import sys
import time
import unittest
from unittest.mock import patch, MagicMock
from PyQt6.QtCore import QCoreApplication
from src.database.repository import init_db, save_or_update_post, get_ai_analysis_by_post_id
from src.ui.workers.ai_worker import AIAnalysisWorker

app = QCoreApplication.instance() or QCoreApplication(sys.argv)
TEST_DB = os.path.join(os.path.dirname(__file__), "test_worker.sqlite")

class TestWorkers(unittest.TestCase):
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

    @patch("requests.post")
    def test_ai_worker_and_hot_reload(self, mock_req):
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "ok": True,
            "choices": [{
                "message": {
                    "content": '{"should_notify": true, "device_name": "MacBook Pro", "price": "30tr", "seller_type": "Chủ bài", "seller_snippet": "Bán MacBook", "reason": "Bán"}'
                }
            }]
        }

        mock_req.return_value = mock_ok

        save_or_update_post("group_post", "777", {"post_id": "777", "group_name": "Mac", "message": "Bán MacBook"}, [])

        worker = AIAnalysisWorker(
            ai_config={"enabled": True, "base_url": "https://api.openai.com/v1", "api_key": "k", "models": ["gpt-4o-mini"], "prompt": "prompt 1"},
            telegram_config={"enabled": True, "token": "tok", "chat_id": "cid", "notify_on_keyword": True}
        )
        signals = []
        worker.analysis_completed_signal.connect(lambda d: signals.append(d))
        worker.start()

        worker.enqueue({"post_id": "777", "group_name": "Mac", "message": "Bán MacBook"}, [], "bán", "Bài viết")

        # Test hot reload
        worker.update_config(ai_config={"enabled": True, "base_url": "https://api.openai.com/v1", "api_key": "k", "models": ["gpt-4o-mini"], "prompt": "prompt updated"})

        time.sleep(0.5)
        QCoreApplication.processEvents()
        time.sleep(0.5)
        QCoreApplication.processEvents()

        worker.stop()
        worker.wait(2000)
        QCoreApplication.processEvents()

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["target_name"], "MacBook Pro")
        self.assertEqual(signals[0]["device_name"], "MacBook Pro")


if __name__ == "__main__":
    unittest.main()
