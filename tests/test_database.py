import os
import unittest
from src.database.repository import (
    init_db,
    save_or_update_post,
    get_post_by_id,
    save_ai_analysis,
    get_ai_analyses_count,
    get_all_ai_analyses,
    get_ai_analysis_by_post_id,
    delete_ai_analysis_by_id,
    get_distinct_group_names
)

TEST_DB = os.path.join(os.path.dirname(__file__), "test_data.sqlite")

class TestDatabase(unittest.TestCase):
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

    def test_post_and_ai_crud(self):
        post_data = {
            "post_id": "111",
            "group_name": "Chợ Test",
            "message": "Cần bán iPhone 15 Pro",
            "permalink": "https://facebook.com/111"
        }
        res = save_or_update_post("group_post", "111", post_data, [], db_path=TEST_DB)
        self.assertTrue(res.get("post_created") or res.get("post_updated"))

        p = get_post_by_id("111", db_path=TEST_DB)
        self.assertIsNotNone(p)
        self.assertEqual(p["group_name"], "Chợ Test")

        ai_id = save_ai_analysis(
            post_id="111",
            group_name="Chợ Test",
            matched_keyword="bán",
            model_used="gpt-4o-mini",
            should_notify=True,
            target_name="iPhone 15 Pro",
            price="20tr",
            actor_role="Chủ bài đăng",
            matched_snippet="Cần bán iPhone 15 Pro",
            reason="Rao bán trực tiếp",
            db_path=TEST_DB
        )

        self.assertGreater(ai_id, 0)

        count = get_ai_analyses_count(filters={"should_notify": 1}, db_path=TEST_DB)
        self.assertEqual(count, 1)

        analyses = get_all_ai_analyses(limit=10, offset=0, filters={"should_notify": 1}, db_path=TEST_DB)
        self.assertEqual(len(analyses), 1)
        self.assertEqual(analyses[0]["device_name"], "iPhone 15 Pro")
        self.assertEqual(analyses[0]["target_name"], "iPhone 15 Pro")
        self.assertEqual(analyses[0]["actor_role"], "Chủ bài đăng")
        self.assertEqual(analyses[0]["matched_snippet"], "Cần bán iPhone 15 Pro")

        # Test filtering by target_name
        filtered = get_all_ai_analyses(filters={"target_name": "iPhone"}, db_path=TEST_DB)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["target_name"], "iPhone 15 Pro")

        del_ok = delete_ai_analysis_by_id(ai_id, db_path=TEST_DB)
        self.assertTrue(del_ok)
        count_after = get_ai_analyses_count(filters={"should_notify": 1}, db_path=TEST_DB)
        self.assertEqual(count_after, 0)

    def test_seed_default_settings_ai_timeout(self):
        from src.database.repository import get_setting
        ai_timeout = get_setting("ai_timeout", db_path=TEST_DB)
        self.assertEqual(ai_timeout, "20")

    def test_update_post_group_name_if_previously_empty(self):
        # 1. Insert post with empty group name
        post_data_empty = {
            "post_id": "222",
            "group_name": "",
            "message": "Post without group",
            "permalink": "https://facebook.com/222"
        }
        save_or_update_post("group_post", "222", post_data_empty, [], db_path=TEST_DB)
        p1 = get_post_by_id("222", db_path=TEST_DB)
        self.assertEqual(p1["group_name"], "")

        # 2. Update same post with non-empty group name
        post_data_with_name = {
            "post_id": "222",
            "group_name": "Hội Máy In 3D",
            "message": "Post with group now",
            "permalink": "https://facebook.com/222"
        }
        save_or_update_post("group_post", "222", post_data_with_name, [], db_path=TEST_DB)
        p2 = get_post_by_id("222", db_path=TEST_DB)
        self.assertEqual(p2["group_name"], "Hội Máy In 3D")

    def test_logs_table_and_cleanup(self):
        from src.database.repository import add_log, get_logs, cleanup_old_logs, get_connection
        
        # Test adding logs
        log_id1 = add_log("Khởi động scraper", level="INFO", module="APP", db_path=TEST_DB)
        log_id2 = add_log("Phát hiện từ khóa", level="DEBUG", module="SCRAPER", db_path=TEST_DB)
        self.assertGreater(log_id1, 0)
        self.assertGreater(log_id2, 0)

        logs = get_logs(db_path=TEST_DB)
        self.assertEqual(len(logs), 2)
        self.assertEqual(logs[0]["message"], "Phát hiện từ khóa")
        self.assertEqual(logs[1]["message"], "Khởi động scraper")

        # Test log filtering
        scraper_logs = get_logs(module="SCRAPER", db_path=TEST_DB)
        self.assertEqual(len(scraper_logs), 1)

        # Insert an old log (> 1 day ago)
        with get_connection(TEST_DB) as conn:
            conn.execute("INSERT INTO logs (level, message, module, created_at) VALUES ('INFO', 'Old log', 'OLD', datetime('now', '-2 days'))")
            conn.commit()

        logs_before_cleanup = get_logs(db_path=TEST_DB)
        self.assertEqual(len(logs_before_cleanup), 3)

        # Cleanup > 1 day
        deleted = cleanup_old_logs(days=1, db_path=TEST_DB)
        self.assertEqual(deleted, 1)

        logs_after_cleanup = get_logs(db_path=TEST_DB)
        self.assertEqual(len(logs_after_cleanup), 2)

    def test_export_diagnostics_sql_excludes_settings(self):
        from src.database.repository import export_diagnostics_sql, set_setting
        import tempfile

        # Put sensitive info in settings
        set_setting("ai_api_key", "SECRET_KEY_12345", db_path=TEST_DB)
        set_setting("telegram_token", "SECRET_BOT_TOKEN_XYZ", db_path=TEST_DB)

        # Put a post
        save_or_update_post("group_post", "333", {"post_id": "333", "message": "Test diagnose dump", "group_name": "Gr1"}, [], db_path=TEST_DB)

        temp_diag = os.path.join(tempfile.gettempdir(), "test_unit.diagnose")
        if os.path.exists(temp_diag):
            os.remove(temp_diag)

        ok, msg, count = export_diagnostics_sql(temp_diag, db_path=TEST_DB)
        self.assertTrue(ok)
        self.assertGreater(count, 0)
        self.assertTrue(os.path.exists(temp_diag))

        with open(temp_diag, "r", encoding="utf-8") as f:
            content = f.read()

        # Sensitive table and keys MUST NOT be dumped
        self.assertNotIn("CREATE TABLE `settings`", content)
        self.assertNotIn("CREATE TABLE settings", content)
        self.assertNotIn("SECRET_KEY_12345", content)
        self.assertNotIn("SECRET_BOT_TOKEN_XYZ", content)

        # Non-settings tables MUST be in dump
        self.assertIn("CREATE TABLE posts", content)
        self.assertIn("Test diagnose dump", content)

        os.remove(temp_diag)

    def test_telegram_sent_status_and_pending_analyses(self):
        from src.database.repository import (
            save_ai_analysis,
            get_pending_telegram_analyses,
            mark_telegram_analysis_sent,
            get_all_ai_analyses
        )

        # 1. Save post and analysis
        save_or_update_post("group_post", "444", {"post_id": "444", "message": "Bài cần gửi Telegram", "group_name": "Gr2"}, [], db_path=TEST_DB)
        
        aid = save_ai_analysis(
            post_id="444",
            group_name="Gr2",
            matched_keyword="mua",
            should_notify=True,
            target_name="Xe đạp",
            price="3tr",
            telegram_sent=0,
            db_path=TEST_DB
        )

        # Check pending
        pending = get_pending_telegram_analyses(db_path=TEST_DB)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], aid)
        self.assertEqual(pending[0]["post_id"], "444")
        self.assertEqual(pending[0]["target_name"], "Xe đạp")

        # Mark sent
        ok = mark_telegram_analysis_sent(aid, status=1, db_path=TEST_DB)
        self.assertTrue(ok)

        # Check pending again (should be 0)
        pending_after = get_pending_telegram_analyses(db_path=TEST_DB)
        self.assertEqual(len(pending_after), 0)

        # Check get_all_ai_analyses returns telegram_sent = 1
        all_res = get_all_ai_analyses(db_path=TEST_DB)
        self.assertEqual(all_res[0]["telegram_sent"], 1)


if __name__ == "__main__":
    unittest.main()
