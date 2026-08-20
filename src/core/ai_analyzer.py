import json
import re
import random
import requests
from typing import Any


def parse_json_from_response(text: str) -> dict:
    """
    Trích xuất và phân tích JSON siêu bền bỉ từ chuỗi phản hồi của LLM:
    - Lọc bỏ khối <think>...</think> / <reasoning>...</reasoning>
    - Bóc tách code block ```json ... ``` (kể cả khi không có fence đóng ```)
    - Hỗ trợ unescaped newlines/tabs trong chuỗi (strict=False)
    - Sửa lỗi trailing commas và chuỗi dạng Python dict
    - Tìm và bóc tách object {...} chính xác
    """
    if not text:
        return {}

    cleaned = text.strip()

    # 0. Loại bỏ thẻ <think>...</think> hoặc <reasoning>...</reasoning>
    cleaned = re.sub(r'<think>[\s\S]*?</think>', '', cleaned, flags=re.IGNORECASE).strip()
    cleaned = re.sub(r'<reasoning>[\s\S]*?</reasoning>', '', cleaned, flags=re.IGNORECASE).strip()

    # 1. Bóc tách markdown code block (hỗ trợ cả có fence đóng hoặc bị cắt ngang không có fence đóng)
    if "```" in cleaned:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', cleaned, re.IGNORECASE)
        if match:
            cleaned = match.group(1).strip()
        else:
            match_open = re.search(r'```(?:json)?\s*([\s\S]*)', cleaned, re.IGNORECASE)
            if match_open:
                cleaned = match_open.group(1).strip()

    # 2. Thử parse trực tiếp với strict=False
    try:
        res = json.loads(cleaned, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # 3. Thử sửa trailing comma: ví dụ `{"a": 1,}` -> `{"a": 1}`
    cleaned_no_trailing = re.sub(r',\s*([\}\]])', r'\1', cleaned)
    try:
        res = json.loads(cleaned_no_trailing, strict=False)
        if isinstance(res, dict):
            return res
    except Exception:
        pass

    # 4. Tìm cặp ngoặc { ... } lớn nhất
    match_brace = re.search(r'(\{[\s\S]*\})', cleaned)
    if match_brace:
        candidate = match_brace.group(1).strip()
        try:
            res = json.loads(candidate, strict=False)
            if isinstance(res, dict):
                return res
        except Exception:
            candidate_clean = re.sub(r',\s*([\}\]])', r'\1', candidate)
            try:
                res = json.loads(candidate_clean, strict=False)
                if isinstance(res, dict):
                    return res
            except Exception:
                pass

    # 5. Thử parse dạng Python dict (nháy đơn hoặc boolean True/False)
    try:
        import ast
        cand = cleaned
        m = re.search(r'(\{[\s\S]*\})', cleaned)
        if m:
            cand = m.group(1).strip()
        parsed_ast = ast.literal_eval(cand)
        if isinstance(parsed_ast, dict):
            return parsed_ast
    except Exception:
        pass

    return {}


def extract_chat_completion_response(response_input: Any) -> tuple[dict, str, str]:
    """
    Trích xuất kết quả từ phản hồi OpenAI / OpenAI-compatible / Gemini.
    Hỗ trợ mạnh mẽ 4 định dạng:
    1. requests.Response object (gọi .json() trước, fallback sang .text)
    2. Dictionary dữ liệu
    3. Chuỗi JSON chuẩn
    4. SSE Streaming chunks (data: {...} chunks)
    
    Trả về: (raw_dict: dict, content_str: str, reasoning_str: str)
    """
    if response_input is None:
        return {}, "", ""

    # 1. Nếu là requests.Response object
    if hasattr(response_input, "json") and callable(response_input.json):
        try:
            data = response_input.json()
            if isinstance(data, dict):
                choices = data.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    c0 = choices[0]
                    msg_obj = c0.get("message") or c0.get("delta") or {}
                    content = msg_obj.get("content") or ""
                    reasoning = msg_obj.get("reasoning_content") or msg_obj.get("reasoning") or ""
                    return data, str(content), str(reasoning)
        except Exception:
            pass

    # 2. Nếu là dictionary
    if isinstance(response_input, dict):
        choices = response_input.get("choices") or []
        if choices and isinstance(choices[0], dict):
            c0 = choices[0]
            msg_obj = c0.get("message") or c0.get("delta") or {}
            content = msg_obj.get("content") or ""
            reasoning = msg_obj.get("reasoning_content") or msg_obj.get("reasoning") or ""
            return response_input, str(content), str(reasoning)

    # 3. Lấy raw_text từ response.text hoặc string
    if hasattr(response_input, "text") and isinstance(response_input.text, str):
        raw_text = response_input.text.strip()
    elif isinstance(response_input, str):
        raw_text = response_input.strip()
    else:
        raw_text = str(response_input).strip()

    if not raw_text:
        return {}, "", ""

    # Thử parse JSON chuẩn từ raw_text
    try:
        data = json.loads(raw_text, strict=False)
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                c0 = choices[0]
                msg_obj = c0.get("message") or c0.get("delta") or {}
                content = msg_obj.get("content") or ""
                reasoning = msg_obj.get("reasoning_content") or msg_obj.get("reasoning") or ""
                return data, str(content), str(reasoning)
    except Exception:
        pass

    # 4. Xử lý Server-Sent Events (SSE) Streaming response chunks (data: {...})
    if "data:" in raw_text or "data :" in raw_text:
        assembled_content = []
        assembled_reasoning = []
        parsed_chunks = []

        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("event:") or line.startswith("id:") or line.startswith(":"):
                continue
            if line.startswith("data:"):
                chunk_data = line[5:].strip()
            elif line.startswith("data :"):
                chunk_data = line[6:].strip()
            else:
                continue

            if chunk_data == "[DONE]" or chunk_data == "[done]":
                continue

            try:
                chunk_obj = json.loads(chunk_data, strict=False)
                parsed_chunks.append(chunk_obj)
                choices = chunk_obj.get("choices") or []
                if choices and isinstance(choices[0], dict):
                    c0 = choices[0]
                    delta = c0.get("delta") or c0.get("message") or {}
                    c_piece = delta.get("content") or ""
                    r_piece = delta.get("reasoning_content") or delta.get("reasoning") or ""
                    if c_piece:
                        assembled_content.append(str(c_piece))
                    if r_piece:
                        assembled_reasoning.append(str(r_piece))
            except Exception:
                continue

        if assembled_content or parsed_chunks:
            full_content = "".join(assembled_content)
            full_reasoning = "".join(assembled_reasoning)
            synthesized_data = {
                "choices": [{
                    "message": {
                        "content": full_content,
                        "reasoning_content": full_reasoning
                    }
                }],
                "streamed": True
            }
            return synthesized_data, full_content, full_reasoning

    # 5. Fallback: Nếu không phải JSON hay SSE chuẩn, thử parse_json_from_response trên raw text
    fallback_data = parse_json_from_response(raw_text)
    if fallback_data:
        return {"choices": [{"message": {"content": raw_text}}]}, raw_text, ""

    return {}, "", ""


def format_post_and_comments_payload(post_data: dict, comments_data: list = None) -> str:
    """
    Đóng gói dữ liệu bài viết và toàn bộ bình luận/phản hồi thành chuỗi JSON có cấu trúc rõ ràng.
    """
    post_data = post_data or {}
    comments_data = comments_data or []

    post_id = str(post_data.get("post_id") or post_data.get("id") or "N/A")
    group_name = post_data.get("group_name") or post_data.get("page_name") or "Facebook Post"
    post_message = post_data.get("message") or post_data.get("text") or ""
    permalink = post_data.get("permalink") or f"https://www.facebook.com/{post_id}"

    formatted_comments = []
    for c in comments_data:
        if not isinstance(c, dict):
            continue
        c_id = str(c.get("comment_id") or "")
        c_text = c.get("text") or ""
        
        formatted_replies = []
        for r in c.get("replies", []):
            if isinstance(r, dict) and r.get("text"):
                formatted_replies.append({
                    "reply_id": str(r.get("reply_id") or ""),
                    "text": r.get("text", "").strip()
                })

        if c_text or formatted_replies:
            formatted_comments.append({
                "comment_id": c_id,
                "text": c_text.strip(),
                "replies": formatted_replies
            })

    payload_dict = {
        "post_id": post_id,
        "group_name": group_name,
        "permalink": permalink,
        "post_message": post_message.strip(),
        "total_comments_extracted": len(formatted_comments),
        "comments": formatted_comments
    }

    return json.dumps(payload_dict, ensure_ascii=False, indent=2)


DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_GOOGLE_AI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


def normalize_ai_base_url(base_url: str = "", provider: str = "openai") -> str:
    """
    Chuẩn hóa Base URL:
    - Nếu provider là google_ai / google_ai_studio: mặc định 'https://generativelanguage.googleapis.com/v1beta/openai'
    - Nếu provider là openai và base_url rỗng: mặc định 'https://api.openai.com/v1'
    - Cắt bỏ các endpoint thừa nếu người dùng dán vào như /chat/completions hoặc /models
    - Chuẩn hóa https://api.openai.com -> https://api.openai.com/v1
    """
    if provider in ("google_ai", "google_ai_studio", "google"):
        return DEFAULT_GOOGLE_AI_BASE_URL
    if not base_url or not base_url.strip():
        return DEFAULT_OPENAI_BASE_URL

    clean = base_url.strip().rstrip('/')
    if clean.endswith("/chat/completions"):
        clean = clean[:-len("/chat/completions")].rstrip('/')
    elif clean.endswith("/models"):
        clean = clean[:-len("/models")].rstrip('/')

    if clean in ("https://api.openai.com", "http://api.openai.com"):
        clean = "https://api.openai.com/v1"

    return clean if clean else DEFAULT_OPENAI_BASE_URL


DEFAULT_GEMINI_MODELS = [
    {"name": "gemini-2.0-flash", "display_name": "gemini-2.0-flash (Khuyên dùng - Nhanh, chuẩn JSON)", "description": "Tốc độ phản hồi cực nhanh, không thinking"},
    {"name": "gemini-2.5-flash", "display_name": "gemini-2.5-flash (Tự động tắt Thinking)", "description": "Model mới nhất, tự động set thinking_budget = 0"},
    {"name": "gemini-1.5-flash", "display_name": "gemini-1.5-flash (Ổn định, tiết kiệm)", "description": "Nhẹ, độ ổn định cao"},
    {"name": "gemini-1.5-pro", "display_name": "gemini-1.5-pro (Chính xác cao)", "description": "Phân tích chuyên sâu"},
    {"name": "gemini-2.0-flash-lite", "display_name": "gemini-2.0-flash-lite", "description": "Bản rút gọn siêu tốc"},
    {"name": "gemini-2.5-pro", "display_name": "gemini-2.5-pro", "description": "Thế hệ 2.5 Pro"}
]


DEFAULT_OPENAI_MODELS = [
    {"name": "gpt-4o-mini", "display_name": "gpt-4o-mini (Khuyên dùng - Nhanh, rẻ, chuẩn JSON)", "description": "Model OpenAI tối ưu tốc độ và độ chính xác", "status": "untested"},
    {"name": "gpt-4o", "display_name": "gpt-4o (Độ chính xác cao)", "description": "Model đa năng thông minh nhất", "status": "untested"},
    {"name": "deepseek-chat", "display_name": "deepseek-chat (DeepSeek V3)", "description": "DeepSeek V3 non-thinking siêu nhanh", "status": "untested"},
    {"name": "claude-3-5-sonnet-20241022", "display_name": "claude-3-5-sonnet", "description": "Claude 3.5 Sonnet", "status": "untested"},
    {"name": "llama-3.3-70b-instruct", "display_name": "llama-3.3-70b-instruct", "description": "Meta Llama 3.3 70B", "status": "untested"},
    {"name": "qwen-2.5-72b-instruct", "display_name": "qwen-2.5-72b-instruct", "description": "Qwen 2.5 72B", "status": "untested"}
]


def fetch_gemini_models_from_api(api_key: str, timeout: int = 8) -> tuple[bool, list[dict], str]:
    """
    Gọi Google AI Studio API để tự động lấy danh sách các model Gemini khả dụng cho API Key.
    Trả về: (thành_công: bool, danh_sách_models: list[dict], thông_điệp: str)
    Mỗi phần tử: {"name": str, "display_name": str, "description": str}
    """
    if not api_key or not api_key.strip():
        return False, DEFAULT_GEMINI_MODELS.copy(), "Chưa nhập API Key"

    key = api_key.strip()

    # 1. Thử endpoint chính thống của Google Generative Language
    url_v1beta = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        resp = requests.get(url_v1beta, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            models_raw = data.get("models", [])
            extracted = []
            for m in models_raw:
                raw_name = m.get("name", "")
                clean_name = raw_name.replace("models/", "").strip()
                methods = m.get("supportedGenerationMethods", [])
                
                # Chỉ lấy các model Gemini hỗ trợ tạo nội dung văn bản (generateContent)
                if "gemini" in clean_name.lower() and "generateContent" in methods:
                    # Bỏ qua embedding, aqa, imagen, learnlm
                    if any(skip in clean_name.lower() for skip in ["embedding", "aqa", "imagen", "learnlm"]):
                        continue
                    disp_name = m.get("displayName") or clean_name
                    desc = m.get("description", "")
                    
                    label = clean_name
                    if "2.0-flash" in clean_name and "lite" not in clean_name:
                        label = f"{clean_name} (Khuyên dùng - Siêu tốc)"
                    elif "2.5-flash" in clean_name:
                        label = f"{clean_name} (Tự động tắt Thinking)"
                    elif disp_name != clean_name:
                        label = f"{clean_name} ({disp_name})"

                    extracted.append({
                        "name": clean_name,
                        "display_name": label,
                        "description": desc
                    })
            if extracted:
                # Sắp xếp theo alphabet (A-Z)
                extracted.sort(key=lambda item: item["name"].lower())
                return True, extracted, f"Đã tự động tải {len(extracted)} models Gemini từ Google AI Studio"
    except Exception:
        pass

    # 2. Thử endpoint OpenAI-compatible models của Google
    url_openai = "https://generativelanguage.googleapis.com/v1beta/openai/models"
    headers = {"Authorization": f"Bearer {key}"}
    try:
        resp = requests.get(url_openai, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            models_data = data.get("data", [])
            extracted = []
            for m in models_data:
                mid = m.get("id", "").strip()
                if "gemini" in mid.lower():
                    extracted.append({
                        "name": mid,
                        "display_name": mid,
                        "description": ""
                    })
            if extracted:
                return True, extracted, f"Đã tải {len(extracted)} models Gemini từ OpenAI-compatible endpoint"
    except Exception as e:
        return False, DEFAULT_GEMINI_MODELS.copy(), f"Lỗi kết nối API Google: {str(e)[:100]}"

    return False, DEFAULT_GEMINI_MODELS.copy(), "Không lấy được danh sách từ API (sử dụng danh sách mặc định)"


def fetch_openai_models_from_api(base_url: str = "", api_key: str = "", timeout: int = 8) -> tuple[bool, list[dict], str]:
    """
    Gọi OpenAI hoặc LLM Proxy / Endpoint tương thích để lấy danh sách models khả dụng.
    Hỗ trợ cả OpenAI chính hãng, OpenRouter, DeepSeek, Groq, Ollama, LM Studio, vLLM, Together...
    Trả về: (thành_công: bool, danh_sách_models: list[dict], thông_điệp: str)
    Mỗi phần tử: {
        "name": str,
        "display_name": str,
        "description": str,
        "is_thinking": bool,
        "is_valid": bool,
        "enabled": bool,
        "status": str,
        "message": str
    }
    """
    resolved_base_url = normalize_ai_base_url(base_url, provider="openai")
    endpoints_to_try = [
        f"{resolved_base_url}/models",
    ]
    if not resolved_base_url.endswith("/v1"):
        endpoints_to_try.append(f"{resolved_base_url}/v1/models")

    headers = {"Content-Type": "application/json"}
    if api_key and api_key.strip():
        headers["Authorization"] = f"Bearer {api_key.strip()}"

    last_error = ""
    for url in endpoints_to_try:
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code != 200:
                last_error = f"HTTP {resp.status_code}: {resp.text[:100]}"
                continue

            try:
                data = resp.json()
            except Exception:
                last_error = f"API không trả về JSON hợp lệ từ {url}"
                continue

            raw_models = []
            if isinstance(data, dict):
                raw_models = data.get("data") or data.get("models") or []
            elif isinstance(data, list):
                raw_models = data

            if not raw_models:
                last_error = "Không tìm thấy danh sách models trong phản hồi API"
                continue

            extracted = []
            excluded_keywords = [
                "embedding", "embed", "text-embedding",
                "dall-e", "image", "stable-diffusion", "midjourney",
                "tts", "whisper", "audio", "transcription", "speech", "sound", "voice",
                "moderation", "guardrail", "safety",
                "realtime", "rerank", "babbage", "davinci", "curie", "ada",
                "canary", "benchmark"
            ]

            for item in raw_models:
                if isinstance(item, dict):
                    mid = str(item.get("id") or item.get("name") or "").strip()
                    owned_by = str(item.get("owned_by") or "")
                else:
                    mid = str(item).strip()
                    owned_by = ""

                if not mid:
                    continue

                mid_lower = mid.lower()

                # Bỏ qua các model không phải chat / LLM
                if any(ex in mid_lower for ex in excluded_keywords):
                    continue

                thinking = is_thinking_model(mid)
                display_label = mid
                if thinking:
                    desc = "Model suy luận (Thinking / Reasoner) — Đã đánh dấu loại trừ"
                    status = "thinking"
                    msg = "Model tư duy (Thinking) — Loại trừ"
                else:
                    desc = f"Owner: {owned_by}" if owned_by else "Model Chat / Completion"
                    status = "untested"
                    msg = "Chưa test thực tế qua API"

                extracted.append({
                    "name": mid,
                    "display_name": display_label,
                    "description": desc,
                    "is_thinking": thinking,
                    "is_valid": not thinking,
                    "enabled": not thinking,
                    "status": status,
                    "message": msg
                })

            if extracted:
                # Sắp xếp theo alphabet (A-Z), gom nhóm model Thinking ở phía sau
                def sort_key(item):
                    n = item.get("name", "").lower()
                    is_think = item.get("is_thinking", False)
                    return (1 if is_think else 0, n)

                extracted.sort(key=sort_key)
                return True, extracted, f"Đã tự động tải {len(extracted)} models từ {resolved_base_url}"

        except requests.exceptions.Timeout:
            last_error = f"Quá thời gian chờ ({timeout}s) khi kết nối tới {url}"
        except requests.exceptions.RequestException as e:
            last_error = f"Lỗi kết nối mạng: {str(e)[:100]}"
        except Exception as e:
            last_error = f"Lỗi xử lý: {str(e)[:100]}"

    return False, DEFAULT_OPENAI_MODELS.copy(), f"Không tải được models từ API: {last_error}"


def is_thinking_model(model_name: str) -> bool:
    """
    Kiểm tra xem tên model có thuộc các dòng model suy luận / tư duy (Thinking / Reasoner) thuần túy
    không hỗ trợ tắt thinking hay không (ví dụ DeepSeek R1, OpenAI o1/o3, QwQ).
    Đối với các dòng Gemini (như gemini-2.5-flash), hệ thống tự động truyền thinking_budget: 0
    để tắt chế độ suy luận nên không bị xem là thinking model bị loại trừ.
    """
    if not model_name:
        return False
    name_lower = model_name.strip().lower()

    # Dòng model Gemini tự động tắt thinking bằng thinking_budget = 0
    if name_lower.startswith("gemini-"):
        if "thinking-exp" in name_lower:
            return True
        return False

    thinking_keywords = [
        "thinking",
        "reasoner",
        "deepseek-r1",
        "-r1",
        "/r1",
        "r1-",
        "o1-",
        "o1",
        "o3-",
        "o3",
        "qwq"
    ]
    return any(kw in name_lower for kw in thinking_keywords)


def verify_single_model_pure_json(
    base_url: str,
    api_key: str,
    model_name: str = None,
    prompt: str = None,
    timeout: int = 15,
    provider: str = "openai",
    model: str = None
) -> tuple[bool, bool, str, dict]:
    """
    Kiểm tra thực tế qua API xem model có hoạt động và trả về JSON thuần chuẩn hay không.
    Trả về: (is_valid: bool, is_thinking: bool, status_message: str, parsed_data: dict)
      - is_valid=True khi model trả về HTTP 200 và kết quả parse được thành JSON thuần hợp lệ.
      - is_valid=False khi model gặp lỗi hoặc không trả về JSON thuần hoặc là model thinking.
    """
    actual_model = model_name or model or ""
    actual_model = str(actual_model).strip()
    if not actual_model:
        return False, False, "Tên model trống", {}
    model_name = actual_model
    if not api_key or not api_key.strip():
        return False, False, "Thiếu AI API Key", {}

    resolved_base_url = normalize_ai_base_url(base_url, provider=provider)
    endpoint = f"{resolved_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    test_system = (
        "Bạn là hệ thống kiểm tra API. Hãy trả về DUY NHẤT 1 JSON object hợp lệ theo định dạng:\n"
        '{"status": "ok", "test": "passed", "model": "' + model_name + '"}\n'
        "Tuyệt đối không giải thích, không viết thêm chữ nào ngoài JSON."
    )
    test_user = "Trả về JSON kiểm tra ngay."

    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": test_system},
            {"role": "user", "content": test_user}
        ],
        "temperature": 0.1,
        "max_tokens": 1000,
        "stream": False
    }

    try:
        response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)

        # Nếu model không hỗ trợ role 'system' (ví dụ o1/o3 hoặc một số proxy), thử lại với role 'user'
        if response.status_code == 400 and any(kw in response.text.lower() for kw in ["system", "developer", "messages[0].role", "unsupported value"]):
            fallback_payload = {
                "model": model_name,
                "messages": [
                    {"role": "user", "content": f"{test_system}\n\n{test_user}"}
                ],
                "max_tokens": 1000,
                "stream": False
            }
            response = requests.post(endpoint, headers=headers, json=fallback_payload, timeout=timeout)

        if response.status_code != 200:
            err_msg = f"HTTP {response.status_code}: {response.text[:120]}"
            return False, False, err_msg, {}

        res_json, raw_content, reasoning_content = extract_chat_completion_response(response)
        if not raw_content and not res_json:
            return False, False, f"API không trả về nội dung chat hợp lệ: {str(getattr(response, 'text', ''))[:100]}", {}

        # Kiểm tra dấu hiệu thinking (reasoning_content, <think> tags, hoặc model name)
        is_thinking = bool(
            reasoning_content
            or "<think>" in raw_content.lower()
            or is_thinking_model(model_name)
        )

        parsed_data = parse_json_from_response(raw_content)

        # Kiểm tra JSON thuần: parse được thành công và không bị rỗng
        if not parsed_data:
            return False, is_thinking, f"Không trả về JSON thuần: {raw_content[:80]}", {}

        if is_thinking:
            return False, True, "Model tư duy (Thinking) / Chứa khối suy luận — Đã gạch ngang loại trừ", parsed_data

        return True, False, "Phản hồi JSON thuần hợp lệ (OK)", parsed_data

    except requests.exceptions.Timeout:
        return False, False, f"Quá thời gian chờ ({timeout}s)", {}
    except requests.exceptions.RequestException as e:
        return False, False, f"Lỗi kết nối: {str(e)[:120]}", {}
    except Exception as e:
        return False, False, f"Lỗi xử lý: {str(e)[:120]}", {}


# Alias
test_single_model_pure_json = verify_single_model_pure_json


def verify_all_models_live(
    base_url: str,
    api_key: str,
    models: list,
    prompt: str = None,
    timeout: int = 15,
    logger=None,
    provider: str = "openai"
) -> list[dict]:
    """
    Kiểm tra thực tế toàn bộ danh sách model qua API.
    Trả về danh sách kết quả chi tiết từng model:
    [
      {
        "name": str,
        "is_valid": bool,
        "is_thinking": bool,
        "status": "ok" | "thinking" | "error",
        "message": str,
        "response": dict
      }
    ]
    """
    results = []
    for item in models:
        if isinstance(item, dict):
            m_name = item.get("name", "")
        else:
            m_name = str(item)
        m_name = m_name.strip()
        if not m_name:
            continue

        if logger:
            try:
                logger(f"🧪 Đang test model '{m_name}'...")
            except Exception:
                pass

        is_valid, is_thinking, msg, data = verify_single_model_pure_json(
            base_url=base_url,
            api_key=api_key,
            model_name=m_name,
            prompt=prompt,
            timeout=timeout,
            provider=provider
        )

        status_type = "ok" if is_valid else ("thinking" if is_thinking else "error")
        results.append({
            "name": m_name,
            "is_valid": is_valid,
            "is_thinking": is_thinking,
            "status": status_type,
            "message": msg,
            "response": data
        })

        if logger:
            try:
                icon = "✅" if is_valid else ("🧠" if is_thinking else "❌")
                logger(f"  {icon} Model '{m_name}': {msg}")
            except Exception:
                pass

    return results


# Alias
test_all_models_live = verify_all_models_live



def analyze_post_with_fallback(
    base_url: str,
    api_key: str,
    models: list[str | dict] | str,
    prompt: str,
    post_content: str,
    timeout: int = 20,
    logger=None,
    provider: str = "openai"
) -> tuple[bool, bool, dict, str, str]:
    """
    Gửi nội dung bài viết qua AI API với cơ chế Multi-Model Fallback:
    - Lọc bỏ các model tư duy (Thinking) hoặc bị vô hiệu hóa.
    - Tự động tắt thinking (thinking_budget: 0) cho các model Gemini.
    - Chọn ngẫu nhiên model trong danh sách hợp lệ.
    - Timeout mỗi lần gọi là 20s.
    - Nếu một model bị lỗi hoặc timeout, tự động chọn ngẫu nhiên model khác chưa thử.
    - Chỉ khi tất cả các model đều thất bại thì mới trả về lỗi.
    """
    def log(msg: str):
        if logger:
            try:
                logger(msg)
            except Exception:
                pass

    if not api_key or not api_key.strip():
        return False, False, {}, "Thiếu AI API Key", ""

    resolved_base_url = normalize_ai_base_url(base_url, provider=provider)

    # Xử lý danh sách models
    raw_list = []
    if isinstance(models, str):
        raw_list = [m.strip() for m in models.replace("\n", ",").split(",") if m.strip()]
    elif isinstance(models, (list, tuple, set)):
        raw_list = list(models)
    else:
        raw_list = []

    model_list = []
    for item in raw_list:
        if isinstance(item, dict):
            name = item.get("name", "").strip()
            # Bỏ qua nếu bị tắt hoặc đánh dấu thinking / invalid
            if item.get("enabled", True) is False or item.get("is_thinking", False) is True or item.get("is_valid", True) is False:
                continue
            if name:
                model_list.append(name)
        elif isinstance(item, str):
            name = item.strip()
            if name and not is_thinking_model(name):
                model_list.append(name)

    # Nếu sau khi lọc không còn model nào, fallback về danh sách thô
    if not model_list:
        fallback_names = []
        for item in raw_list:
            n = item.get("name", "").strip() if isinstance(item, dict) else str(item).strip()
            if n:
                fallback_names.append(n)
        default_fallback = "gemini-2.0-flash" if "googleapis.com" in resolved_base_url else "gpt-4o-mini"
        model_list = fallback_names if fallback_names else [default_fallback]

    # Trộn ngẫu nhiên danh sách model để gọi ngẫu nhiên
    models_pool = model_list.copy()
    random.shuffle(models_pool)

    if not prompt or not prompt.strip():
        prompt = "Bạn là chuyên gia phân tích dữ liệu Facebook."

    endpoint = f"{resolved_base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key.strip()}",
        "Content-Type": "application/json"
    }

    user_message = f"Dữ liệu bài viết và bình luận cần phân tích:\n{post_content.strip()}"
    errors = []

    for attempt_idx, current_model in enumerate(models_pool, 1):
        log(f"🤖 Đang gọi AI model '{current_model}' (lần thử {attempt_idx}/{len(models_pool)}, timeout {timeout}s)...")
        
        payload = {
            "model": current_model,
            "messages": [
                {"role": "system", "content": prompt.strip()},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.1,
            "max_tokens": 2000,
            "stream": False
        }

        try:
            response = requests.post(endpoint, headers=headers, json=payload, timeout=timeout)

            # Nếu model không hỗ trợ role 'system' (ví dụ o1/o3 hoặc một số proxy), thử lại với role 'user'
            if response.status_code == 400 and any(kw in response.text.lower() for kw in ["system", "developer", "messages[0].role", "unsupported value"]):
                fallback_payload = {
                    "model": current_model,
                    "messages": [
                        {"role": "user", "content": f"{prompt.strip()}\n\n{user_message}"}
                    ],
                    "max_tokens": 2000,
                    "stream": False
                }
                response = requests.post(endpoint, headers=headers, json=fallback_payload, timeout=timeout)

            if response.status_code != 200:
                err_text = f"HTTP {response.status_code}: {response.text[:180]}"
                log(f"  ⚠️ Model '{current_model}' trả về lỗi: {err_text}")
                errors.append(f"Model '{current_model}': {err_text}")
                continue

            res_json, raw_content, _ = extract_chat_completion_response(response)
            if not raw_content and not res_json:
                err_text = f"API không trả về nội dung chat hợp lệ: {str(getattr(response, 'text', ''))[:100]}"
                log(f"  ⚠️ Model '{current_model}' trả về lỗi: {err_text}")
                errors.append(f"Model '{current_model}': {err_text}")
                continue

            parsed_data = parse_json_from_response(raw_content)

            if not parsed_data:
                err_text = f"Không parse được JSON từ phản hồi: {raw_content[:100]}"
                log(f"  ⚠️ Model '{current_model}': {err_text}")
                errors.append(f"Model '{current_model}': {err_text}")
                continue

            # Thành công! Bóc tách các trường
            should_notify = bool(parsed_data.get("should_notify", False))
            reason = parsed_data.get("reason", "")

            log(f"  ✅ Phân tích thành công bằng model '{current_model}' (should_notify={should_notify})")
            return should_notify, should_notify, parsed_data, reason, current_model

        except requests.exceptions.Timeout:
            err_text = f"Quá thời gian chờ {timeout}s (Timeout)"
            log(f"  ⏱️ Model '{current_model}' bị Timeout ({timeout}s). Chuyển sang model ngẫu nhiên khác...")
            errors.append(f"Model '{current_model}': {err_text}")
            continue
        except requests.exceptions.RequestException as e:
            err_text = f"Lỗi kết nối: {str(e)[:150]}"
            log(f"  ⚠️ Model '{current_model}' gặp lỗi mạng: {err_text}")
            errors.append(f"Model '{current_model}': {err_text}")
            continue
        except Exception as e:
            err_text = f"Lỗi xử lý: {str(e)[:150]}"
            log(f"  ⚠️ Model '{current_model}' lỗi: {err_text}")
            errors.append(f"Model '{current_model}': {err_text}")
            continue

    # Tất cả các model đều thất bại
    summary_err = f"Toàn bộ {len(models_pool)} model AI đều thất bại: " + " | ".join(errors)
    log(f"❌ {summary_err}")
    return False, False, {}, summary_err, ""


def analyze_post(base_url: str, api_key: str, model: str | list[str], prompt: str, post_content: str, timeout: int = 20, provider: str = "openai") -> tuple[bool, dict, str]:
    """
    Wrapper tương thích ngược với code cũ.
    Trả về: (should_notify: bool, ai_data: dict, error_or_reason: str)
    """
    should_notify, _, parsed_data, reason, model_used = analyze_post_with_fallback(
        base_url=base_url,
        api_key=api_key,
        models=model,
        prompt=prompt,
        post_content=post_content,
        timeout=timeout,
        provider=provider
    )
    return should_notify, parsed_data, reason


def test_ai_connection(base_url: str, api_key: str, models: str | list[str], prompt: str, provider: str = "openai", timeout: int = 20) -> tuple[bool, str, dict]:
    """
    Kiểm tra kết nối tới AI API bằng một bài viết mẫu kèm bình luận.
    Trả về: (thành_công: bool, thông_điệp: str, kết_quả_parse: dict)
    """
    sample_post = {
        "post_id": "test_123456",
        "group_name": "Cộng Đồng Máy In 3D Việt Nam",
        "message": "Ai có máy in 3D cũ cần nâng cấp không ạ?",
        "permalink": "https://www.facebook.com/groups/test/posts/123456"
    }
    sample_comments = [
        {
            "comment_id": "cmt_01",
            "text": "Mình dư con Bambu Lab A1 Combo mới 99% đầy đủ phụ kiện giá 8.5tr ở HN nhé bác nào cần ới em.",
            "replies": []
        }
    ]
    payload = format_post_and_comments_payload(sample_post, sample_comments)

    logs = []
    should_notify, _, result, reason, model_used = analyze_post_with_fallback(
        base_url=base_url,
        api_key=api_key,
        models=models,
        prompt=prompt,
        post_content=payload,
        timeout=timeout,
        logger=lambda m: logs.append(m),
        provider=provider
    )

    if result and ("should_notify" in result or should_notify):
        target = result.get("target_name") or result.get("device_name") or "N/A"
        actor = result.get("actor_role") or result.get("seller_type") or "N/A"
        price_val = result.get("price") or result.get("price_or_budget") or "N/A"
        snippet = result.get("matched_snippet") or result.get("seller_snippet") or "N/A"
        ai_reason_text = result.get("reason", reason)

        msg = (
            f"✅ Kết nối AI ({provider.upper()}) thành công!\n"
            f"• Model phản hồi: {model_used}\n"
            f"• Gửi thông báo (should_notify): {should_notify}\n"
            f"• Đánh giá khớp: {'KHỚP THÔNG BÁO' if should_notify else 'BỎ QUA (Không thông báo)'}\n"
            f"• Mục tiêu / Đối tượng: {target}\n"
            f"• Giá / Ngân sách / Lương: {price_val}\n"
            f"• Vai trò phát hiện: {actor}\n"
            f"• Trích đoạn: {snippet}\n"
            f"• Lý do AI: {ai_reason_text}"
        )
        return True, msg, result

    elif result:
        return True, f"✅ Kết nối AI thành công (Model: {model_used}) nhưng phản hồi khác schema: {reason}", result
    else:
        return False, f"❌ Kết nối AI thất bại: {reason}", {}



