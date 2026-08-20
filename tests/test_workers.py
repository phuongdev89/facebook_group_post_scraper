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
        import src.database.repository
        import src.config.constants
        self.orig_db = src.database.repository.DEFAULT_DB_PATH
        self.orig_const_db = src.config.constants.DEFAULT_DB_PATH
        src.database.repository.DEFAULT_DB_PATH = TEST_DB
        src.config.constants.DEFAULT_DB_PATH = TEST_DB
        if os.path.exists(TEST_DB):
            try:
                os.remove(TEST_DB)
            except Exception:
                pass
        init_db(TEST_DB)

    def tearDown(self):
        import src.database.repository
        import src.config.constants
        src.database.repository.DEFAULT_DB_PATH = self.orig_db
        src.config.constants.DEFAULT_DB_PATH = self.orig_const_db
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

        time.sleep(0.3)
        QCoreApplication.processEvents()

        worker.stop()
        worker.wait(1000)
        QCoreApplication.processEvents()

        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0]["target_name"], "MacBook Pro")
        self.assertEqual(signals[0]["device_name"], "MacBook Pro")

    @patch("requests.post")
    def test_ai_worker_deduplication_and_role_change(self, mock_req):
        from src.database.repository import save_or_update_post, get_ai_analysis_by_post_id

        save_or_update_post("group_post", "888", {"post_id": "888", "group_name": "Test", "message": "Bài 888"}, [])

        # 1. First analysis -> Role: "Người bán"
        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = {
            "ok": True,
            "choices": [{
                "message": {
                    "content": '{"should_notify": true, "target_name": "Xe máy", "price": "10tr", "actor_role": "Người bán", "reason": "Bán xe"}'
                }
            }]
        }
        mock_req.return_value = mock_resp1

        worker = AIAnalysisWorker(
            ai_config={"enabled": True, "base_url": "https://api.openai.com/v1", "api_key": "k", "models": ["gpt-4o-mini"]},
            telegram_config={"enabled": True, "token": "tok", "chat_id": "cid", "notify_on_keyword": True}
        )
        worker.start()

        worker.enqueue({"post_id": "888", "group_name": "Test", "message": "Bài 888"}, [], "bán", "Bài viết")
        time.sleep(0.3)
        QCoreApplication.processEvents()

        first_analysis = get_ai_analysis_by_post_id("888")
        self.assertIsNotNone(first_analysis)
        self.assertEqual(first_analysis["actor_role"], "Người bán")
        self.assertEqual(first_analysis["telegram_sent"], 0) # Needs to be sent

        # 2. Re-analysis with UNCHANGED role ("Người bán") -> telegram_sent must be 1 (suppressed)
        worker.enqueue({"post_id": "888", "group_name": "Test", "message": "Bài 888"}, [{"text": "Bình luận mới"}], "bán", "Bình luận")
        time.sleep(0.3)
        QCoreApplication.processEvents()

        second_analysis = get_ai_analysis_by_post_id("888")
        self.assertEqual(second_analysis["actor_role"], "Người bán")
        self.assertEqual(second_analysis["telegram_sent"], 1) # Unchanged role -> suppressed!

        # 3. Re-analysis with CHANGED role ("Người mua") -> telegram_sent must be 0 (re-sent)
        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {
            "ok": True,
            "choices": [{
                "message": {
                    "content": '{"should_notify": true, "target_name": "Xe máy", "price": "10tr", "actor_role": "Người mua", "reason": "Tìm mua xe"}'
                }
            }]
        }
        mock_req.return_value = mock_resp2

        worker.enqueue({"post_id": "888", "group_name": "Test", "message": "Bài 888"}, [{"text": "Bình luận tìm mua"}], "mua", "Bình luận")
        time.sleep(0.3)
        QCoreApplication.processEvents()

        third_analysis = get_ai_analysis_by_post_id("888")
        self.assertEqual(third_analysis["actor_role"], "Người mua")
        self.assertEqual(third_analysis["telegram_sent"], 0) # Role changed -> trigger new Telegram alert!

        worker.stop()
        worker.wait(1000)

    @patch("requests.post")
    def test_ai_worker_processes_sqlite_pending_queue(self, mock_req):
        from src.database.repository import (
            save_or_update_post,
            mark_post_ai_pending,
            get_ai_analysis_by_post_id,
            get_post_by_id
        )

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "choices": [{
                "message": {
                    "content": '{"should_notify": true, "target_name": "Combo Phím Chuột", "price": "500k", "actor_role": "Người bán", "reason": "Bán combo"}'
                }
            }]
        }
        mock_req.return_value = mock_resp

        save_or_update_post(
            "group_post",
            "999",
            {"post_id": "999", "group_name": "Gear", "message": "Bán combo phím chuột"},
            [{"comment_id": "c1", "text": "Còn không shop?", "replies": [{"reply_id": "r1", "text": "Dạ còn ạ"}]}]
        )
        mark_post_ai_pending("999", "combo", "Bài viết")

        worker = AIAnalysisWorker(
            ai_config={"enabled": True, "base_url": "https://api.openai.com/v1", "api_key": "k", "models": ["gpt-4o-mini"]},
            telegram_config={"enabled": True, "token": "tok", "chat_id": "cid", "notify_on_keyword": True},
            check_interval=1
        )
        worker.start()
        worker.trigger_check_now()

        time.sleep(0.5)
        QCoreApplication.processEvents()

        worker.stop()
        worker.wait(1000)

        analysis = get_ai_analysis_by_post_id("999")
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis["target_name"], "Combo Phím Chuột")
        self.assertEqual(analysis["actor_role"], "Người bán")
        self.assertEqual(analysis["telegram_sent"], 0)

    @patch("requests.post")
    def test_test_ai_models_worker(self, mock_req):
        from src.ui.workers.ai_worker import TestAIModelsWorker

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"ok": true, "message": "Test successful"}'}}]
        }
        mock_req.return_value = mock_resp

        worker = TestAIModelsWorker(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            models=["gpt-4o-mini", "deepseek-reasoner"],
            timeout=5,
            provider="openai"
        )

        started_models = []
        tested_results = []
        progress_updates = []
        all_results = []

        worker.model_testing_started.connect(lambda name: started_models.append(name))
        worker.model_tested_single.connect(lambda res: tested_results.append(res))
        worker.progress_signal.connect(lambda cur, tot, name: progress_updates.append((cur, tot, name)))
        worker.finished_all_signal.connect(lambda res: all_results.extend(res))

        worker.start()
        worker.wait(2000)
        QCoreApplication.processEvents()

        self.assertEqual(started_models, ["gpt-4o-mini", "deepseek-reasoner"])
        self.assertEqual(len(tested_results), 2)
        self.assertEqual(len(all_results), 2)
        # gpt-4o-mini should be valid
        self.assertTrue(tested_results[0]["is_valid"])
        # deepseek-reasoner should be detected as thinking
        self.assertTrue(tested_results[1]["is_thinking"])

    @patch("requests.post")
    def test_test_ai_models_worker_stop(self, mock_req):
        from src.ui.workers.ai_worker import TestAIModelsWorker

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": '{"ok": true}'}}]
        }
        def slow_post(*args, **kwargs):
            time.sleep(0.05)
            return mock_resp

        mock_req.side_effect = slow_post

        worker = TestAIModelsWorker(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            models=["model1", "model2", "model3", "model4", "model5"],
            timeout=5,
            provider="openai"
        )
        tested = []
        worker.model_tested_single.connect(lambda res: tested.append(res))

        worker.start()
        time.sleep(0.08)
        worker.stop()
        worker.wait(2000)
        QCoreApplication.processEvents()

        # Should have stopped after 1 or 2 models, not running all 5
        self.assertLess(len(tested), 5)


if __name__ == "__main__":
    unittest.main()
