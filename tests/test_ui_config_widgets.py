import sys
import unittest
from PyQt6.QtWidgets import QApplication
from src.ui.components.tag_widget import ModelTagWidget, TagWidget

app = QApplication.instance() or QApplication(sys.argv)


class TestUIConfigWidgets(unittest.TestCase):
    def test_model_tag_widget_thinking_detection(self):
        widget = ModelTagWidget()
        widget.set_models_data(["gpt-4o-mini", "deepseek-reasoner", "gemini-2.0-flash"])

        # Active models should exclude deepseek-reasoner (thinking model)
        active = widget.get_active_models()
        self.assertIn("gpt-4o-mini", active)
        self.assertIn("gemini-2.0-flash", active)
        self.assertNotIn("deepseek-reasoner", active)

        all_data = widget.get_all_models_data()
        self.assertEqual(len(all_data), 3)

        # deepseek-reasoner should be flagged as thinking and invalid/disabled
        reasoner = next(m for m in all_data if m["name"] == "deepseek-reasoner")
        self.assertTrue(reasoner["is_thinking"])
        self.assertFalse(reasoner["is_valid"])

    def test_model_tag_widget_update_with_test_results(self):
        widget = ModelTagWidget()
        widget.set_models_data(["gpt-4o-mini", "claude-3-opus"])

        # Simulate test results where claude-3-opus failed (e.g. 404 or non-JSON)
        test_results = [
            {"name": "gpt-4o-mini", "is_valid": True, "is_thinking": False, "status": "ok", "message": "OK"},
            {"name": "claude-3-opus", "is_valid": False, "is_thinking": False, "status": "error", "message": "HTTP 404: Not Found"}
        ]
        widget.update_with_test_results(test_results)

        active = widget.get_active_models()
        self.assertEqual(active, ["gpt-4o-mini"])

        all_data = widget.get_all_models_data()
        opus = next(m for m in all_data if m["name"] == "claude-3-opus")
        self.assertFalse(opus["is_valid"])
        self.assertEqual(opus["status"], "error")

    def test_facebook_notification_ui_tabs(self):
        from src.ui.app import FacebookNotificationUI
        window = FacebookNotificationUI()
        self.assertIsNotNone(window.history_table)
        self.assertIsNotNone(window.ai_analysis_table)
        self.assertEqual(window.history_table.columnCount(), 8)
        self.assertEqual(window.ai_analysis_table.columnCount(), 12)

        # Check initial button states (disabled when no rows selected)
        self.assertFalse(window.btn_delete_selected_history.isEnabled())
        self.assertFalse(window.btn_update_selected_comments.isEnabled())
        self.assertFalse(window.btn_delete_selected_ai.isEnabled())
        self.assertFalse(window.btn_resend_telegram.isEnabled())

        # Test state change on selection
        window.selected_history_post_ids.add("123")
        window.update_history_buttons_state()
        self.assertTrue(window.btn_delete_selected_history.isEnabled())
        self.assertTrue(window.btn_update_selected_comments.isEnabled())
        self.assertIn("1", window.btn_delete_selected_history.text())

        window.selected_ai_analysis_ids.add(99)
        window.update_ai_buttons_state()
        self.assertTrue(window.btn_delete_selected_ai.isEnabled())
        self.assertTrue(window.btn_resend_telegram.isEnabled())
        self.assertIn("1", window.btn_delete_selected_ai.text())
        self.assertIn("1", window.btn_resend_telegram.text())

        if hasattr(window, 'telegram_dispatcher') and window.telegram_dispatcher:
            window.telegram_dispatcher.stop()
        if hasattr(window, 'ai_dispatcher') and window.ai_dispatcher:
            window.ai_dispatcher.stop()
        window.close()

    def test_gemini_model_selector_widget(self):
        from src.ui.components.gemini_model_selector import GeminiModelSelectorWidget
        widget = GeminiModelSelectorWidget()
        
        # Test defaults
        active = widget.get_active_models()
        self.assertIn("gemini-2.0-flash", active)
        self.assertIn("gemini-2.5-flash", active)

        # Test selecting/unselecting
        widget.set_selected_models(["gemini-1.5-pro"])
        self.assertEqual(widget.get_active_models(), ["gemini-1.5-pro"])

        # Test select all
        widget.select_all()
        self.assertGreaterEqual(len(widget.get_active_models()), 4)

    def test_ai_provider_toggle(self):
        from src.ui.app import FacebookNotificationUI
        window = FacebookNotificationUI()
        self.assertIsNotNone(window.ai_provider_combo)
        self.assertIsNotNone(window.gemini_model_selector)
        self.assertIsNotNone(window.openai_models_container)

        # Switch to Google AI Studio
        idx_google = window.ai_provider_combo.findData("google_ai")
        window.ai_provider_combo.setCurrentIndex(idx_google)
        self.assertEqual(window.get_current_ai_provider(), "google_ai")
        self.assertFalse(window.google_ai_guide_widget.isHidden())
        self.assertTrue(window.ai_base_url_input.isHidden())
        self.assertFalse(window.gemini_model_selector.isHidden())
        self.assertTrue(window.openai_models_container.isHidden())
        self.assertIn("generativelanguage.googleapis.com", window.get_resolved_ai_base_url())
        
        gemini_models = window.get_active_ai_models()
        self.assertTrue(any(m.startswith("gemini-") for m in gemini_models))

        # Switch to OpenAI
        idx_openai = window.ai_provider_combo.findData("openai")
        window.ai_provider_combo.setCurrentIndex(idx_openai)
        self.assertEqual(window.get_current_ai_provider(), "openai")
        self.assertTrue(window.google_ai_guide_widget.isHidden())
        self.assertFalse(window.ai_base_url_input.isHidden())
        self.assertTrue(window.gemini_model_selector.isHidden())
        self.assertFalse(window.openai_models_container.isHidden())
        self.assertIsNotNone(window.btn_fetch_openai_models)
        self.assertEqual(window.btn_fetch_openai_models.text(), "🔄 Tải Models từ API")
        
        # Default empty base_url resolves to OpenAI
        window.ai_base_url_input.clear()
        self.assertEqual(window.get_resolved_ai_base_url(), "https://api.openai.com/v1")
        if hasattr(window, 'telegram_dispatcher') and window.telegram_dispatcher:
            window.telegram_dispatcher.stop()
        if hasattr(window, 'ai_dispatcher') and window.ai_dispatcher:
            window.ai_dispatcher.stop()
    def test_openai_model_selector_widget(self):
        from src.ui.components.openai_model_selector import OpenAIModelSelectorWidget
        widget = OpenAIModelSelectorWidget()

        # Defaults should include gpt-4o-mini and gpt-4o
        active = widget.get_active_models()
        self.assertIn("gpt-4o-mini", active)
        self.assertIn("gpt-4o", active)

        # Test alphabetical sorting with custom model added
        widget.add_model("claude-3-5-sonnet")
        widget.add_model("deepseek-reasoner") # thinking model
        widget.add_model("anthropic-claude-3")

        all_names = [m["name"] for m in widget.models_list]
        # Check that deepseek-reasoner is at the end (group thinking) and others are sorted A-Z
        non_think = [m["name"] for m in widget.models_list if not m.get("is_thinking")]
        self.assertEqual(non_think, sorted(non_think, key=lambda s: s.lower()))

        # Active models should not include thinking model
        active_after = widget.get_active_models()
        self.assertNotIn("deepseek-reasoner", active_after)
        self.assertIn("claude-3-5-sonnet", active_after)

        # Test selecting/unselecting
        widget.set_selected_models(["gpt-4o-mini"])
        self.assertEqual(widget.get_active_models(), ["gpt-4o-mini"])

        # Test select all
        widget.toggle_select_all()
        self.assertGreaterEqual(len(widget.get_active_models()), 3)

        # Test update with live test results (marking model as invalid/error)
        test_results = [
            {"name": "gpt-4o-mini", "is_valid": True, "is_thinking": False, "status": "ok", "message": "OK"},
            {"name": "claude-3-5-sonnet", "is_valid": False, "is_thinking": False, "status": "error", "message": "HTTP 404"}
        ]
        widget.update_with_test_results(test_results)
        self.assertNotIn("claude-3-5-sonnet", widget.get_active_models())
        self.assertIn("gpt-4o-mini", widget.get_active_models())

        # Check that NO HTML <span> or <s> tags are present in any checkbox text
        for name, cb in widget.checkboxes.items():
            self.assertNotIn("<span", cb.text())
        # Test untested state (yellow/amber color)
        widget.add_model("custom-untested-model")
        untested_cb = widget.checkboxes["custom-untested-model"]
        self.assertIn("#D97706", untested_cb.styleSheet())
        self.assertEqual(untested_cb.text(), "custom-untested-model")

        # Test Clear All Models
        self.assertIsNotNone(widget.btn_clear_all)
        self.assertEqual(widget.btn_clear_all.text(), "🗑 Xóa tất cả")
        widget.clear_all_models()
        self.assertEqual(len(widget.models_list), 0)
        self.assertEqual(len(widget.checkboxes), 0)


if __name__ == "__main__":
    unittest.main()




