import unittest
import json
from unittest.mock import patch, MagicMock
from src.core.ai_analyzer import (
    format_post_and_comments_payload,
    analyze_post_with_fallback,
    is_thinking_model,
    verify_single_model_pure_json,
    verify_all_models_live
)


class TestAIAnalyzer(unittest.TestCase):
    def test_json_formatting(self):
        post = {"post_id": "123", "group_name": "Group A", "message": "Test post"}
        comments = [{"comment_id": "c1", "text": "Comment 1", "replies": []}]
        payload = format_post_and_comments_payload(post, comments)
        data = json.loads(payload)
        self.assertEqual(data["post_id"], "123")
        self.assertEqual(len(data["comments"]), 1)

    def test_is_thinking_model(self):
        self.assertTrue(is_thinking_model("deepseek-reasoner"))
        self.assertTrue(is_thinking_model("deepseek-ai/DeepSeek-R1"))
        self.assertTrue(is_thinking_model("gemini-2.0-flash-thinking-exp"))
        self.assertTrue(is_thinking_model("o1-mini"))
        self.assertTrue(is_thinking_model("o3-mini"))
        self.assertTrue(is_thinking_model("qwq-32b-preview"))
        self.assertFalse(is_thinking_model("gpt-4o-mini"))
        self.assertFalse(is_thinking_model("gemini-2.0-flash"))
        self.assertFalse(is_thinking_model("claude-3-5-sonnet-20241022"))

    @patch("src.core.ai_analyzer.requests.post")
    def test_verify_single_model_pure_json(self, mock_post):
        # 1. Test case: Pure JSON valid response
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "choices": [{"message": {"content": '{"status": "ok", "test": "passed", "model": "gpt-4o-mini"}'}}]
        }
        mock_post.return_value = mock_ok
        is_valid, is_thinking, msg, data = verify_single_model_pure_json("https://api.openai.com/v1", "key", "gpt-4o-mini")
        self.assertTrue(is_valid)
        self.assertFalse(is_thinking)
        self.assertEqual(data.get("status"), "ok")

        # 2. Test case: Non-JSON conversational text (should fail is_valid)
        mock_non_json = MagicMock()
        mock_non_json.status_code = 200
        mock_non_json.json.return_value = {
            "choices": [{"message": {"content": "Xin chào, tôi là AI hỗ trợ bạn!"}}]
        }
        mock_post.return_value = mock_non_json
        is_valid, is_thinking, msg, data = verify_single_model_pure_json("https://api.openai.com/v1", "key", "gpt-4o-mini")
        self.assertFalse(is_valid)

        # 3. Test case: Thinking model / reasoning content
        mock_thinking = MagicMock()
        mock_thinking.status_code = 200
        mock_thinking.json.return_value = {
            "choices": [{
                "message": {
                    "reasoning_content": "Thinking about test...",
                    "content": '{"status": "ok"}'
                }
            }]
        }
        mock_post.return_value = mock_thinking
        is_valid, is_thinking, msg, data = verify_single_model_pure_json("https://api.openai.com/v1", "key", "deepseek-reasoner")
        self.assertFalse(is_valid)
        self.assertTrue(is_thinking)

        # 4. Test case: HTTP Error 404 / 500
        mock_err = MagicMock()
        mock_err.status_code = 404
        mock_err.text = "Model not found"
        mock_post.return_value = mock_err
        is_valid, is_thinking, msg, data = verify_single_model_pure_json("https://api.openai.com/v1", "key", "unknown-model")
        self.assertFalse(is_valid)
        self.assertIn("404", msg)


    @patch("src.core.ai_analyzer.requests.post")
    def test_fallback(self, mock_post):
        mock_fail = MagicMock()
        mock_fail.status_code = 500
        mock_fail.text = "Server Error"

        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"should_notify": true, "device_name": "iPad Pro", "price": "15tr", "seller_type": "Chủ bài đăng", "seller_snippet": "Bán iPad", "reason": "Có bán"}'
                }
            }]
        }
        mock_post.side_effect = [mock_fail, mock_ok]

        should_notify, _, res, reason, model_used = analyze_post_with_fallback(
            base_url="https://api.openai.com/v1",
            api_key="key",
            models=["model1", "model2"],
            prompt="prompt",
            post_content="content",
            timeout=20
        )
        self.assertTrue(should_notify)
        self.assertEqual(res["device_name"], "iPad Pro")

    def test_normalize_ai_base_url(self):
        from src.core.ai_analyzer import normalize_ai_base_url, DEFAULT_OPENAI_BASE_URL, DEFAULT_GOOGLE_AI_BASE_URL
        # OpenAI default
        self.assertEqual(normalize_ai_base_url("", provider="openai"), DEFAULT_OPENAI_BASE_URL)
        # Google AI default
        self.assertEqual(normalize_ai_base_url("", provider="google_ai"), DEFAULT_GOOGLE_AI_BASE_URL)
        # Custom URL
        self.assertEqual(normalize_ai_base_url("https://my-proxy.com/v1/"), "https://my-proxy.com/v1")

    @patch("src.core.ai_analyzer.requests.post")
    def test_gemini_payload_standard_schema(self, mock_post):
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "choices": [{"message": {"content": '{"status": "ok"}'}}]
        }
        mock_post.return_value = mock_ok

        # Call with Gemini model via google_ai provider
        verify_single_model_pure_json("", "test_key", "gemini-2.0-flash", provider="google_ai")

        # Verify standard payload schema (no unknown thinking_config field)
        called_args, called_kwargs = mock_post.call_args
        payload = called_kwargs.get("json", {})
        self.assertNotIn("thinking_config", payload)
        self.assertNotIn("extra_body", payload)
        self.assertEqual(payload["model"], "gemini-2.0-flash")


    @patch("src.core.ai_analyzer.requests.get")
    def test_fetch_gemini_models_from_api(self, mock_get):
        from src.core.ai_analyzer import fetch_gemini_models_from_api
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "models": [
                {
                    "name": "models/gemini-2.0-flash",
                    "displayName": "Gemini 2.0 Flash",
                    "description": "Fast generation",
                    "supportedGenerationMethods": ["generateContent"]
                },
                {
                    "name": "models/gemini-1.5-pro",
                    "displayName": "Gemini 1.5 Pro",
                    "description": "Pro model",
                    "supportedGenerationMethods": ["generateContent"]
                },
                {
                    "name": "models/text-embedding-004",
                    "displayName": "Embedding",
                    "supportedGenerationMethods": ["embedContent"]
                }
            ]
        }
        mock_get.return_value = mock_resp

        ok, models, msg = fetch_gemini_models_from_api("AIzaSyFakeKey12345")
        self.assertTrue(ok)
        model_names = [m["name"] for m in models]
        self.assertIn("gemini-2.0-flash", model_names)
        self.assertIn("gemini-1.5-pro", model_names)
        # Embedding should be filtered out
        self.assertNotIn("text-embedding-004", model_names)

    def test_prompt_constants(self):
        from src.config.default_prompts import (
            DEFAULT_AI_PROMPT,
            DEFAULT_BUYER_AI_PROMPT,
            DEFAULT_RENTAL_AI_PROMPT,
            DEFAULT_JOB_AI_PROMPT
        )
        for p in [DEFAULT_AI_PROMPT, DEFAULT_BUYER_AI_PROMPT, DEFAULT_RENTAL_AI_PROMPT, DEFAULT_JOB_AI_PROMPT]:
            self.assertIn("should_notify", p)
            self.assertIn("target_name", p)
            self.assertIn("actor_role", p)

    @patch("src.core.ai_analyzer.requests.post")
    def test_test_ai_connection_summary_generalized(self, mock_post):
        from src.core.ai_analyzer import test_ai_connection
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "choices": [{
                "message": {
                    "content": '{"should_notify": true, "target_name": "Phòng trọ 30m2", "price": "4tr", "actor_role": "Chủ nhà", "matched_snippet": "Cho thuê phòng", "reason": "Cho thuê"}'
                }
            }]
        }
        mock_post.return_value = mock_ok

        ok, msg, res = test_ai_connection(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            models=["gpt-4o-mini"],
            prompt="test prompt",
            provider="openai"
        )
        self.assertTrue(ok)
        self.assertIn("Phòng trọ 30m2", msg)
        self.assertIn("Mục tiêu / Đối tượng", msg)
        self.assertIn("Chủ nhà", msg)



    @patch("src.core.ai_analyzer.requests.post")
    def test_ai_timeout_passed_to_requests(self, mock_post):
        from src.core.ai_analyzer import test_ai_connection
        mock_ok = MagicMock()
        mock_ok.status_code = 200
        mock_ok.json.return_value = {
            "choices": [{"message": {"content": '{"should_notify": true, "reason": "Match test"}'}}]
        }
        mock_post.return_value = mock_ok

        ok, msg, res = test_ai_connection(
            base_url="https://api.openai.com/v1",
            api_key="sk-test",
            models=["gpt-4o-mini"],
            prompt="Prompt test",
            provider="openai",
            timeout=45
        )
        self.assertTrue(ok)
        self.assertEqual(mock_post.call_args[1].get("timeout"), 45)


if __name__ == "__main__":
    unittest.main()





