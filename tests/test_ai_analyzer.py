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

    def test_parse_json_from_response_robustness(self):
        from src.core.ai_analyzer import parse_json_from_response

        # 1. Normal JSON
        res = parse_json_from_response('{"status": "ok", "should_notify": true}')
        self.assertEqual(res.get("status"), "ok")

        # 2. Markdown fenced JSON
        res = parse_json_from_response('```json\n{"status": "ok", "should_notify": true}\n```')
        self.assertEqual(res.get("status"), "ok")

        # 3. Truncated markdown without closing backticks
        res = parse_json_from_response('```json\n{"status": "ok", "should_notify": true}')
        self.assertEqual(res.get("status"), "ok")

        # 4. Unescaped newlines in JSON strings (which caused Line 1 JSONDecodeError)
        raw_with_newlines = '{\n  "should_notify": true,\n  "reason": "Line 1: Người bán đăng\nLine 2: Giá 500k"\n}'
        res = parse_json_from_response(raw_with_newlines)
        self.assertTrue(res.get("should_notify"))
        self.assertIn("Line 1", res.get("reason", ""))

        # 5. Trailing commas
        res = parse_json_from_response('{"should_notify": true, "target_name": "iPhone 14",}')
        self.assertTrue(res.get("should_notify"))
        self.assertEqual(res.get("target_name"), "iPhone 14")

        # 6. Response containing <think> tags
        res = parse_json_from_response('<think>\nI will analyze this.\n</think>\n```json\n{"should_notify": false, "reason": "No seller"}\n```')
        self.assertFalse(res.get("should_notify"))
        self.assertEqual(res.get("reason"), "No seller")

        # 7. Python dict with single quotes
        res = parse_json_from_response("{'should_notify': True, 'target_name': 'Máy in 3D'}")
        self.assertTrue(res.get("should_notify"))
        self.assertEqual(res.get("target_name"), "Máy in 3D")

        # 8. Extra introductory/conclusion text around JSON
        res = parse_json_from_response('Kết quả phân tích như sau:\n{"should_notify": true, "target_name": "Bambu A1"}\nHy vọng câu trả lời hữu ích!')
        self.assertTrue(res.get("should_notify"))
        self.assertEqual(res.get("target_name"), "Bambu A1")

    @patch("src.core.ai_analyzer.requests.get")
    def test_fetch_openai_models_from_api(self, mock_get):
        from src.core.ai_analyzer import fetch_openai_models_from_api

        # 1. Standard OpenAI response
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "object": "list",
            "data": [
                {"id": "gpt-4o", "owned_by": "openai"},
                {"id": "gpt-4o-mini", "owned_by": "openai"},
                {"id": "text-embedding-3-small", "owned_by": "openai"},
                {"id": "dall-e-3", "owned_by": "openai"},
                {"id": "tts-1", "owned_by": "openai"},
                {"id": "whisper-1", "owned_by": "openai"},
                {"id": "deepseek-chat", "owned_by": "deepseek"},
                {"id": "deepseek-reasoner", "owned_by": "deepseek"},
                {"id": "o3-mini", "owned_by": "openai"}
            ]
        }
        mock_get.return_value = mock_resp

        ok, models, msg = fetch_openai_models_from_api("https://api.openai.com/v1", "sk-test12345")
        self.assertTrue(ok)
        names = [m["name"] for m in models]

        # Valid chat models should be included
        self.assertIn("gpt-4o", names)
        self.assertIn("gpt-4o-mini", names)
        self.assertIn("deepseek-chat", names)

        # Embedding, audio, dall-e should be filtered out
        self.assertNotIn("text-embedding-3-small", names)
        self.assertNotIn("dall-e-3", names)
        self.assertNotIn("tts-1", names)
        self.assertNotIn("whisper-1", names)

        # Thinking models should be marked as thinking
        reasoner_item = next(m for m in models if m["name"] == "deepseek-reasoner")
        self.assertTrue(reasoner_item["is_thinking"])
        self.assertFalse(reasoner_item["is_valid"])

        o3_item = next(m for m in models if m["name"] == "o3-mini")
        self.assertTrue(o3_item["is_thinking"])

    def test_normalize_ai_base_url_comprehensive(self):
        from src.core.ai_analyzer import normalize_ai_base_url
        self.assertEqual(normalize_ai_base_url("https://api.openai.com"), "https://api.openai.com/v1")
        self.assertEqual(normalize_ai_base_url("https://api.openai.com/v1/chat/completions"), "https://api.openai.com/v1")
        self.assertEqual(normalize_ai_base_url("https://api.openai.com/v1/models"), "https://api.openai.com/v1")
        self.assertEqual(normalize_ai_base_url("https://openrouter.ai/api/v1/"), "https://openrouter.ai/api/v1")
        self.assertEqual(normalize_ai_base_url("https://api.deepseek.com/chat/completions"), "https://api.deepseek.com")

    @patch("src.core.ai_analyzer.requests.post")
    def test_verify_single_model_html_error_handled_cleanly(self, mock_post):
        # When proxy returns HTTP 200 with HTML (e.g. login required or 502 HTML)
        mock_html = MagicMock()
        mock_html.status_code = 200
        mock_html.text = "<!DOCTYPE html><html><body>Error</body></html>"
        mock_html.json.side_effect = json.JSONDecodeError("Expecting value", "doc", 0)
        mock_post.return_value = mock_html

        is_valid, is_thinking, msg, data = verify_single_model_pure_json("https://api.openai.com/v1", "key", "gpt-4o-mini")
        self.assertFalse(is_valid)
        # Should return user-friendly message, not crash with unhandled traceback
        self.assertIn("nội dung chat", msg)

    def test_extract_chat_completion_response_sse_stream(self):
        from src.core.ai_analyzer import extract_chat_completion_response
        
        # User reported SSE streaming response format:
        sse_text = (
            'data: {"id":"93fdcb3e4d29475999e6c8baf782513a","object":"chat.completion.chunk","created":1787238902,"model":"gpt-4o-mini","choices":[{"index":0,"delta":{"content":"{\\"status\\": "},"logprobs":null,"finish_reason":null}]}\n\n'
            'data: {"id":"93fdcb3e4d29475999e6c8baf782513a","object":"chat.completion.chunk","created":1787238902,"model":"gpt-4o-mini","choices":[{"index":0,"delta":{"content":"\\"ok\\", \\"test\\": \\"passed\\"}"},"logprobs":null,"finish_reason":"stop"}]}\n\n'
            'data: [DONE]\n'
        )

        res_dict, content, reasoning = extract_chat_completion_response(sse_text)
        self.assertEqual(content, '{"status": "ok", "test": "passed"}')
        self.assertTrue(res_dict.get("streamed"))

    @patch("src.core.ai_analyzer.requests.post")
    def test_verify_single_model_sse_stream_success(self, mock_post):
        # When proxy returns SSE chunks with data: {...}
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = (
            'data: {"id":"93fdcb3e4d29475999e6c8baf782513a","object":"chat.completion.chunk","created":1787238902,"model":"gpt-4o-mini","choices":[{"index":0,"delta":{"content":"{\\"status\\": \\"ok\\", \\"test\\": \\"passed\\", \\"model\\": \\"gpt-4o-mini\\"}"},"logprobs":null,"finish_reason":"stop"}]}\n\n'
            'data: [DONE]\n'
        )
        mock_post.return_value = mock_resp

        is_valid, is_thinking, msg, data = verify_single_model_pure_json("https://api.openai.com/v1", "key", "gpt-4o-mini")
        self.assertTrue(is_valid)
        self.assertFalse(is_thinking)
        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("model"), "gpt-4o-mini")


if __name__ == "__main__":
    unittest.main()






