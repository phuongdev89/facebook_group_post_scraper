import re
import html
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from src.core.proxy_utils import select_proxy


def parse_cookies_from_any(text: str) -> tuple[dict, str, str]:
    """
    Tự động nhận diện và trích xuất Cookies + fb_dtsg từ nhiều định dạng:
    1. Lệnh cURL (DevTools Copy as cURL: có cờ -b, -H 'cookie:...', --data-raw fb_dtsg=...)
    2. Chuỗi Cookie thô (c_user=123; xs=abc; datr=xyz hoặc nhiều dòng key=value)
    3. Mảng JSON Cookies ([{"name": "c_user", "value": "123"}, ...])
    
    Returns:
        tuple[dict, str, str]: (cookies_dict, cookie_string, fb_dtsg)
    """
    if not text:
        return {}, "", ""

    text = text.strip()
    cookies_dict = {}
    cookie_str = ""
    fb_dtsg = ""

    # 1. Thử parse dạng JSON array (nếu người dùng copy từ extension Cookie JSON)
    if text.startswith("[") and text.endswith("]"):
        try:
            data = json.loads(text)
            if isinstance(data, list):
                parts = []
                for item in data:
                    if isinstance(item, dict) and "name" in item and "value" in item:
                        k = str(item["name"]).strip()
                        v = str(item["value"]).strip()
                        cookies_dict[k] = v
                        parts.append(f"{k}={v}")
                if cookies_dict:
                    cookie_str = "; ".join(parts)
                    return cookies_dict, cookie_str, fb_dtsg
        except Exception:
            pass

    # 2. Kiểm tra xem có phải lệnh cURL không
    is_curl = "curl" in text.lower() or "-b " in text or "--data-raw" in text or "-H " in text or "--header" in text

    if is_curl:
        # Trích xuất cookie từ cờ -b '...' hoặc -b "..."
        cookie_match = re.search(r"(?:^|\s)-b\s+['\"]([^'\"]+)['\"]", text, re.MULTILINE)
        if cookie_match:
            cookie_str = cookie_match.group(1).strip()
        else:
            # Hoặc từ header Cookie: 'cookie: ...'
            header_cookie = re.search(r"-H\s+['\"][Cc]ookie:\s*([^'\"]+)['\"]", text)
            if header_cookie:
                cookie_str = header_cookie.group(1).strip()

        # Trích xuất fb_dtsg từ post data (--data-raw, --data, -d, etc.)
        data_match = re.search(r"(?:--data-raw|--data-urlencode|--data|-d)\s+['\"]([^'\"]+)['\"]", text, re.MULTILINE | re.DOTALL)
        if data_match:
            body_raw = data_match.group(1).strip()
            params = urllib.parse.parse_qs(body_raw)
            if 'fb_dtsg' in params:
                fb_dtsg = params['fb_dtsg'][0]
            else:
                m = re.search(r'fb_dtsg=([^&\s]+)', body_raw)
                if m:
                    fb_dtsg = urllib.parse.unquote(m.group(1))

    # 3. Nếu chưa tìm được cookie_str qua cURL, xử lý text như chuỗi cookie thông thường
    if not cookie_str:
        # Kiểm tra xem có dán kèm fb_dtsg dạng "fb_dtsg=NAc..." trong text không
        dtsg_match = re.search(r'(?:fb_dtsg|dtsg)\s*[:=]\s*([a-zA-Z0-9:_-]{10,})', text)
        if dtsg_match:
            fb_dtsg = dtsg_match.group(1).strip()

        cookie_str = text

    # Parse cookie_str thành dict
    if cookie_str:
        # Hỗ trợ cả phân cách bằng dấu ; lẫn xuống dòng
        normalized_str = cookie_str.replace("\n", ";").replace("\r", ";")
        parts = []
        for item in normalized_str.split(";"):
            item = item.strip()
            if not item:
                continue
            if "=" in item:
                k, v = item.split("=", 1)
                k = k.strip()
                v = v.strip()
                # Loại bỏ prefix thừa nếu có
                if k.startswith("Cookie:") or k.startswith("cookie:"):
                    k = k.split(":", 1)[1].strip()
                if k and v:
                    cookies_dict[k] = v
                    parts.append(f"{k}={v}")

        # Tái tạo cookie_str chuẩn
        if parts:
            cookie_str = "; ".join(parts)

    return cookies_dict, cookie_str, fb_dtsg


def _clean_group_name(name: str) -> str:
    """Làm sạch tên nhóm Facebook từ HTML text hoặc JSON escaped string"""
    if not name:
        return ""
    # Giải mã chuỗi unicode escape (như \u0110 -> Đ, \u1ed9 -> ộ)
    try:
        name = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), name)
    except Exception:
        pass
    name = html.unescape(name).strip()
    name = re.sub(r'\s+', ' ', name)
    name = re.sub(r'<[^>]+>', '', name)
    name = re.sub(r'\\u003[cC].*?\\u003[eE]', '', name)
    # Loại bỏ số lượng thành viên hoặc badge kèm theo nếu có (vd: "Tên Nhóm · 123K thành viên")
    name = re.sub(r'\s*·\s*[\d,.]+[KkMm]?\s*(thành viên|members?|bài viết|posts?).*$', '', name, flags=re.IGNORECASE)
    return name.strip()


def _normalize_group_url(identifier: str) -> tuple[str, str]:
    """
    Chuẩn hóa URL nhóm từ identifier (ID số hoặc slug).
    Returns (url, group_id)
    """
    identifier = str(identifier).strip().strip("/")
    if not identifier:
        return "", ""
    
    url = f"https://www.facebook.com/groups/{identifier}/"
    group_id = identifier if identifier.isdigit() else ""
    return url, group_id


IGNORED_SLUGS = {
    'create', 'discover', 'feed', 'joins', 'category', 'notifications',
    'search', 'settings', 'help', 'about', 'events', 'members', 'home',
    'browse', 'your_groups', 'recommended', 'dialog', 'sharer', 'privacy',
    'terms', 'policies', 'cookie', 'directory', 'places', 'games', 'user',
    'photo', 'photos', 'video', 'videos', 'reel', 'reels', 'story', 'stories'
}


def _extract_groups_from_text(text: str, groups_map: dict[str, dict]):
    """
    Trích xuất toàn diện danh sách nhóm từ chuỗi HTML/JSON của Facebook.
    Sử dụng kỹ thuật quét đệ quy cấu trúc JSON, Relay store, và unescape sâu.
    """
    if not text:
        return

    def add_item(g_id: str, g_name: str, g_url: str = ""):
        g_id = str(g_id).strip()
        g_name = _clean_group_name(g_name)

        if not g_id and not g_url:
            return

        if g_id and g_id.isdigit() and len(g_id) < 4:
            return

        if g_id and g_id.lower() in IGNORED_SLUGS:
            return

        final_url = ""
        if g_id and g_id.isdigit():
            final_url = f"https://www.facebook.com/groups/{g_id}/"
        elif g_url:
            m = re.search(r'/groups/([a-zA-Z0-9._-]+)', g_url)
            if m:
                slug = m.group(1).strip()
                if slug.lower() in IGNORED_SLUGS:
                    return
                final_url = f"https://www.facebook.com/groups/{slug}/"
                if slug.isdigit() and not g_id:
                    g_id = slug
        elif g_id:
            final_url = f"https://www.facebook.com/groups/{g_id}/"

        if not final_url:
            return

        if not g_name:
            g_name = f"Nhóm {g_id}" if g_id else final_url

        if final_url not in groups_map:
            groups_map[final_url] = {
                "name": g_name,
                "url": final_url,
                "group_id": g_id
            }
        else:
            # Cập nhật tên tốt hơn nếu tên cũ chỉ là fallback
            current = groups_map[final_url]
            if current["name"].startswith("Nhóm ") and not g_name.startswith("Nhóm ") and len(g_name) > 3:
                current["name"] = g_name
            if not current["group_id"] and g_id:
                current["group_id"] = g_id

    # 1. Đệ quy tìm kiếm trong mọi cấu trúc Python dict/list
    def traverse(obj):
        if isinstance(obj, dict):
            typename = obj.get("__typename")
            if typename == "Group":
                g_id = obj.get("id") or obj.get("group_id") or ""
                g_name = obj.get("name") or obj.get("group_name") or ""
                g_url = obj.get("url") or ""
                add_item(g_id, g_name, g_url)

            if "group_id" in obj and ("group_name" in obj or "name" in obj):
                add_item(obj["group_id"], obj.get("group_name") or obj.get("name"), obj.get("url", ""))

            if "group" in obj and isinstance(obj["group"], dict):
                g = obj["group"]
                add_item(g.get("id") or g.get("group_id"), g.get("name"), g.get("url"))

            for v in obj.values():
                traverse(v)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    # 2. Xử lý cả chuỗi gốc và chuỗi đã unescape sâu (cho Relay JSON chuỗi thoát lồng nhau)
    texts_to_process = [text]
    try:
        unescaped = html.unescape(text)
        unescaped = unescaped.replace(r'\"', '"').replace(r'\\"', '"').replace(r'\/', '/').replace(r'\u0022', '"').replace(r'\u002F', '/')
        texts_to_process.append(unescaped)
    except Exception:
        pass

    for t in texts_to_process:
        # A. Tìm tất cả khối JSON trong thẻ <script>
        script_blocks = re.findall(r'<script[^>]*type=["\']application/json["\'][^>]*>(.*?)</script>', t, re.DOTALL)
        for block in script_blocks:
            block = block.strip()
            if block.startswith("{") or block.startswith("["):
                try:
                    parsed = json.loads(block)
                    traverse(parsed)
                except Exception:
                    pass

        # B. Tìm các khối handleDefines / ScheduledServerJS / Relay Blobs
        relay_blobs = re.findall(r'require\("ServerJSDefine"\)\.handleDefines\((.*?)\);', t, re.DOTALL)
        for blob in relay_blobs:
            try:
                parsed = json.loads(blob)
                traverse(parsed)
            except Exception:
                pass

        # C. Regex bắt Group typename và thuộc tính trong JSON
        for m in re.finditer(r'"__typename"\s*:\s*"Group"[^}]{0,400}?"id"\s*:\s*"(\d{4,})"[^}]{0,400}?"name"\s*:\s*"([^"]+)"', t):
            add_item(m.group(1), m.group(2))
        for m in re.finditer(r'"__typename"\s*:\s*"Group"[^}]{0,400}?"name"\s*:\s*"([^"]+)"[^}]{0,400}?"id"\s*:\s*"(\d{4,})"', t):
            add_item(m.group(2), m.group(1))

        # D. Regex tổng quát cho mọi cặp id và name của Group trong JSON
        for m in re.finditer(r'"(?:group_)?id"\s*:\s*"(\d{5,})"[^}]{0,300}?"(?:group_)?name"\s*:\s*"([^"]+)"', t):
            add_item(m.group(1), m.group(2))
        for m in re.finditer(r'"(?:group_)?name"\s*:\s*"([^"]+)"[^}]{0,300}?"(?:group_)?id"\s*:\s*"(\d{5,})"', t):
            add_item(m.group(2), m.group(1))

        # E. Regex cho link href trong HTML
        for m in re.finditer(r'href=["\'](?:https?://(?:www\.|m\.|mbasic\.)?facebook\.com)?/groups/([a-zA-Z0-9._-]+)/?["\'][^>]*>(?:<[^>]+>)*([^<]{2,120})<', t):
            slug = m.group(1)
            name = m.group(2)
            if slug.lower() not in IGNORED_SLUGS and not any(sub in slug for sub in ('posts', 'permalink', 'user')):
                add_item(slug, name)


def _deduplicate_and_clean_groups(groups_list: list[dict]) -> list[dict]:
    """
    Khử trùng lặp đa tầng danh sách nhóm Facebook:
    - Gộp các bản ghi có cùng ID số hoặc cùng Vanity Slug alias (VD: /groups/750279539095674/ và /groups/cuongtruewireless/)
    - Ánh xạ slug custom sang ID số thực tế
    - Gộp các bản ghi có cùng tên nhóm chuẩn hóa
    - Giữ URL thân thiện nhất và ID số chính xác nhất
    """
    if not groups_list:
        return []

    # 1. Bảng ánh xạ: Slug -> Numeric ID và Name -> Numeric ID
    slug_to_id = {}
    name_to_id = {}

    for g in groups_list:
        gid = str(g.get("group_id") or "").strip()
        url = str(g.get("url") or "").strip()
        name = _clean_group_name(g.get("name") or "")

        m = re.search(r'/groups/([a-zA-Z0-9._-]+)', url)
        slug = m.group(1).strip() if m else ""

        if gid.isdigit() and len(gid) >= 4:
            if slug and not slug.isdigit() and slug.lower() not in IGNORED_SLUGS:
                slug_to_id[slug.lower()] = gid
            if name and not name.startswith("Nhóm "):
                name_to_id[name.lower()] = gid
        elif slug.isdigit() and len(slug) >= 4:
            if name and not name.startswith("Nhóm "):
                name_to_id[name.lower()] = slug

    # 2. Hợp nhất các bản ghi trùng lặp
    unified_map: dict[str, dict] = {}

    for g in groups_list:
        gid = str(g.get("group_id") or "").strip()
        url = str(g.get("url") or "").strip()
        name = _clean_group_name(g.get("name") or "")
        name_lower = name.lower()

        m = re.search(r'/groups/([a-zA-Z0-9._-]+)', url)
        slug = m.group(1).strip() if m else ""

        resolved_gid = ""
        if gid.isdigit() and len(gid) >= 4:
            resolved_gid = gid
        elif slug.lower() in slug_to_id:
            resolved_gid = slug_to_id[slug.lower()]
        elif slug.isdigit() and len(slug) >= 4:
            resolved_gid = slug
        elif name_lower in name_to_id:
            resolved_gid = name_to_id[name_lower]

        if resolved_gid:
            unique_key = f"id:{resolved_gid}"
        elif slug:
            unique_key = f"slug:{slug.lower()}"
        elif name_lower:
            unique_key = f"name:{name_lower}"
        else:
            unique_key = url

        best_url = url
        if not best_url and resolved_gid:
            best_url = f"https://www.facebook.com/groups/{resolved_gid}/"

        if unique_key not in unified_map:
            unified_map[unique_key] = {
                "name": name if name else (f"Nhóm {resolved_gid}" if resolved_gid else url),
                "url": best_url,
                "group_id": resolved_gid if resolved_gid else (gid if gid else slug)
            }
        else:
            existing = unified_map[unique_key]
            # Cập nhật tên nhóm đầy đủ hơn
            if (len(name) > len(existing["name"]) and not name.startswith("Nhóm ")) or existing["name"].startswith("Nhóm "):
                existing["name"] = name
            # Cập nhật ID số chính xác
            if resolved_gid and (not existing["group_id"] or not str(existing["group_id"]).isdigit()):
                existing["group_id"] = resolved_gid
            # Ưu tiên vanity URL đẹp mắt hơn ID số thuần
            if "/groups/" in url and not re.search(r'/groups/\d+/?$', url) and re.search(r'/groups/\d+/?$', existing["url"]):
                existing["url"] = url

    result = list(unified_map.values())
    result.sort(key=lambda item: item.get("name", "").lower())
    return result


def fetch_user_joined_groups(cookies: dict, fb_dtsg: str = "", max_pages: int = 25, logger=None, proxy=None) -> list[dict]:
    """
    Gửi request tới Facebook qua toàn bộ các kênh (Desktop Relay, GraphQL Pagination đa tầng, Mobile Multi-category, Bookmarks)
    để đảm bảo lấy đủ 100% tất cả các nhóm (100-200+ nhóm) mà tài khoản đã tham gia.

    Returns:
        list[dict]: Danh sách nhóm [{"name": str, "url": str, "group_id": str}, ...]
    """
    if not cookies or not isinstance(cookies, dict):
        if logger:
            logger("⚠️ Không có cookies hợp lệ để lấy danh sách nhóm.")
        return []

    def log(msg: str):
        if logger:
            logger(msg)
        else:
            print(f"[GroupFetcher] {msg}")

    user_id = str(cookies.get("c_user") or "0")
    proxies = proxy if proxy else select_proxy(has_cookies=True)
    session = requests.Session()
    session.cookies.update(cookies)
    if proxies:
        session.proxies.update(proxies)

    groups_map: dict[str, dict] = {}
    extracted_dtsg = fb_dtsg

    headers_desktop = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    }

    headers_mobile = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 13; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Dest": "document",
    }

    headers_graphql = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
        "Content-Type": "application/x-www-form-urlencoded",
        "Origin": "https://www.facebook.com",
        "Referer": "https://www.facebook.com/groups/joins/",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Dest": "empty",
        "X-FB-Friendly-Name": "GroupsTabJoinedSectionPaginationQuery"
    }

    log("🌐 Đang kết nối tới Facebook để lấy danh sách toàn bộ các nhóm đã tham gia...")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 1: Quét Desktop Joined Groups & Bóc tách Tokens / DocIDs / Cursors
    # --------------------------------------------------------------------------
    found_doc_ids = set()
    initial_joined_cursor = None
    all_cursors = []

    try:
        log("   📄 Đang tải trang Nhóm đã tham gia (Desktop)...")
        resp = session.get("https://www.facebook.com/groups/joins/", headers=headers_desktop, timeout=20)
        if resp.status_code == 200:
            desktop_joins_html = resp.text
            _extract_groups_from_text(desktop_joins_html, groups_map)
            log(f"   ✅ Giao diện Desktop ban đầu: Đã trích xuất {len(groups_map)} nhóm.")

            # Bóc tách fb_dtsg nếu chưa có
            if not extracted_dtsg:
                dtsg_m = re.search(r'["\']token["\']\s*:\s*["\']([a-zA-Z0-9:_-]{10,})["\']', desktop_joins_html)
                if dtsg_m:
                    extracted_dtsg = dtsg_m.group(1)
                else:
                    dtsg_m2 = re.search(r'name=["\']fb_dtsg["\']\s+value=["\']([^"\']+)["\']', desktop_joins_html)
                    if dtsg_m2:
                        extracted_dtsg = dtsg_m2.group(1)

            # Bóc tách doc_id từ HTML nếu có
            for m in re.finditer(r'["\'](?:Groups(?:CometAllJoinedGroupsSection|CometJoinsRoot|TabJoined|CometLeftRail|Joined)[\w]*)PaginationQuery_facebookRelayOperation["\'][^}]+?["\']doc_id["\']\s*:\s*["\'](\d+)["\']', desktop_joins_html):
                found_doc_ids.add(m.group(1))
            for m in re.finditer(r'__d\(\"GroupsCometAllJoinedGroupsSectionPaginationQuery_facebookRelayOperation\"[^;]+?\"(\d+)\"', desktop_joins_html):
                found_doc_ids.add(m.group(1))

            # Bóc tách con trỏ phân trang all_joined_groups từ Relay cache
            cursor_m = re.search(r'all_joined_groups[\s\S]*?\"end_cursor\"\s*:\s*\"([^\"]+)\"', desktop_joins_html)
            if cursor_m:
                initial_joined_cursor = cursor_m.group(1)
            
            for m in re.finditer(r'\"end_cursor\"\s*:\s*\"([^\"]+)\"', desktop_joins_html):
                all_cursors.append(m.group(1))
            if not initial_joined_cursor and all_cursors:
                initial_joined_cursor = all_cursors[0]
    except Exception as e:
        log(f"   ⚠️ Lỗi truy vấn desktop joins: {str(e)}")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 2: GraphQL Pagination (Lấy toàn bộ các trang nhóm tiếp theo)
    # --------------------------------------------------------------------------
    if extracted_dtsg:
        log("🚀 Đang chạy GraphQL Pagination để lấy toàn bộ các trang nhóm tiếp theo...")
        # 9974006939348139 là doc_id chuẩn của GroupsCometAllJoinedGroupsSectionPaginationQuery
        PRIMARY_PAGINATION_DOC_ID = "9974006939348139"
        doc_ids_to_try = [PRIMARY_PAGINATION_DOC_ID]
        for d in found_doc_ids:
            if d not in doc_ids_to_try:
                doc_ids_to_try.append(d)

        jazoest = "2" + str(sum(ord(c) for c in extracted_dtsg))

        cursor = initial_joined_cursor
        graphql_page = 1
        consecutive_empty = 0

        while cursor and graphql_page <= max_pages:
            try:
                variables = {
                    "count": 50,
                    "cursor": cursor,
                    "ordering": ["integrity_signals"],
                    "scale": 1
                }
                payload = {
                    "av": user_id,
                    "__user": user_id,
                    "__a": "1",
                    "fb_dtsg": extracted_dtsg,
                    "jazoest": jazoest,
                    "doc_id": PRIMARY_PAGINATION_DOC_ID,
                    "variables": json.dumps(variables)
                }
                g_resp = session.post(
                    "https://www.facebook.com/api/graphql/",
                    headers=headers_graphql,
                    data=payload,
                    timeout=25
                )
                if g_resp.status_code != 200:
                    break

                prev_count = len(groups_map)
                for line in g_resp.text.split("\n"):
                    line = line.strip()
                    if line.startswith("{"):
                        _extract_groups_from_text(line, groups_map)

                new_added = len(groups_map) - prev_count
                if new_added > 0:
                    consecutive_empty = 0
                    log(f"   ✅ GraphQL Phân trang {graphql_page}: Tìm thấy thêm {new_added} nhóm (Tổng: {len(groups_map)} nhóm).")
                else:
                    consecutive_empty += 1
                    if consecutive_empty >= 2:
                        break

                # Tìm cursor tiếp theo từ cấu trúc JSON response
                next_cursor = None
                has_next = False
                for line in g_resp.text.split("\n"):
                    line = line.strip()
                    if not line.startswith("{"):
                        continue
                    try:
                        data = json.loads(line)
                        tab_list = data.get("data", {}).get("viewer", {}).get("all_joined_groups", {}).get("tab_groups_list", {})
                        page_info = tab_list.get("page_info", {})
                        if page_info:
                            has_next = page_info.get("has_next_page", False)
                            next_cursor = page_info.get("end_cursor")
                            break
                    except Exception:
                        pass

                if not next_cursor:
                    next_cursor_m = re.search(r'\"end_cursor\"\s*:\s*\"([^\"]+)\"', g_resp.text)
                    has_next_m = re.search(r'\"has_next_page\"\s*:\s*(true|false)', g_resp.text, re.IGNORECASE)
                    has_next = (has_next_m.group(1).lower() == "true") if has_next_m else False
                    next_cursor = next_cursor_m.group(1) if next_cursor_m else None

                if not has_next or not next_cursor or next_cursor == cursor:
                    break
                cursor = next_cursor
                graphql_page += 1
            except Exception as e:
                log(f"   ⚠️ Lỗi phân trang GraphQL trang {graphql_page}: {e}")
                break

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 3: Quét Đa Kênh Toàn Bộ Profile, Feed & Bookmarks (Desktop + Mobile)
    # --------------------------------------------------------------------------
    all_discovery_urls = [
        # Desktop Profile & Bookmarks
        (f"https://www.facebook.com/{user_id}/groups/", headers_desktop, "Desktop Profile Groups"),
        ("https://www.facebook.com/me/groups/", headers_desktop, "Desktop Me Groups"),
        ("https://www.facebook.com/groups/feed/", headers_desktop, "Desktop Left Rail / Feed"),
        ("https://www.facebook.com/bookmarks/groups/", headers_desktop, "Desktop Bookmarks Groups"),
        ("https://www.facebook.com/bookmarks/", headers_desktop, "Desktop All Bookmarks"),
        ("https://www.facebook.com/groups/", headers_desktop, "Desktop Groups Home"),
        # Mobile Categories
        (f"https://m.facebook.com/{user_id}/groups/", headers_mobile, "Mobile Profile Groups"),
        ("https://m.facebook.com/groups/membership/", headers_mobile, "Mobile Membership"),
        ("https://m.facebook.com/groups/joins/", headers_mobile, "Mobile Joined Groups"),
        ("https://m.facebook.com/groups/?category=membership", headers_mobile, "Mobile Category Membership"),
        ("https://m.facebook.com/groups/?category=others", headers_mobile, "Mobile Category Others"),
        ("https://m.facebook.com/groups/?category=admin", headers_mobile, "Mobile Category Admin"),
        ("https://m.facebook.com/groups/?category=pinned", headers_mobile, "Mobile Category Pinned"),
        ("https://m.facebook.com/bookmarks/groups/", headers_mobile, "Mobile Bookmarks Groups"),
        ("https://m.facebook.com/bookmarks/", headers_mobile, "Mobile All Bookmarks"),
        # mbasic Categories
        (f"https://mbasic.facebook.com/{user_id}/groups/", headers_mobile, "mbasic Profile Groups"),
        ("https://mbasic.facebook.com/groups/?category=membership", headers_mobile, "mbasic Membership"),
        ("https://mbasic.facebook.com/groups/?category=others", headers_mobile, "mbasic Others"),
        ("https://mbasic.facebook.com/groups/?category=admin", headers_mobile, "mbasic Admin"),
    ]

    log("🌐 Đang quét bổ sung qua tất cả các trang danh mục & lối tắt nhóm...")
    for url, headers, desc in all_discovery_urls:
        try:
            prev_count = len(groups_map)
            resp = session.get(url, headers=headers, timeout=15)
            if resp.status_code == 200:
                _extract_groups_from_text(resp.text, groups_map)
                new_found = len(groups_map) - prev_count
                if new_found > 0:
                    log(f"   ✅ {desc}: Trích xuất thêm {new_found} nhóm (Tổng: {len(groups_map)} nhóm).")
        except Exception:
            pass

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 4: Phân Trang Mobile & mbasic Membership (Offset Loop)
    # --------------------------------------------------------------------------
    for offset in range(0, 300, 20):
        url = f"https://m.facebook.com/groups/?category=membership&start={offset}"
        try:
            prev_count = len(groups_map)
            resp = session.get(url, headers=headers_mobile, timeout=15)
            if resp.status_code == 200:
                _extract_groups_from_text(resp.text, groups_map)
                new_added = len(groups_map) - prev_count
                if new_added > 0:
                    log(f"   ✅ Mobile Membership (Offset {offset}): Thêm {new_added} nhóm (Tổng: {len(groups_map)} nhóm).")
                elif offset > 40 and new_added == 0:
                    break
        except Exception:
            break

    # mbasic seemore pagination
    try:
        current_mbasic_url = "https://mbasic.facebook.com/groups/?seemore"
        page = 1
        while current_mbasic_url and page <= 10:
            resp = session.get(current_mbasic_url, headers=headers_mobile, timeout=15)
            if resp.status_code != 200:
                break
            prev_count = len(groups_map)
            soup = BeautifulSoup(resp.text, "html.parser")
            next_url = None

            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text_content = _clean_group_name(a.get_text())
                if "seemore" in href or "xem thêm" in text_content.lower() or "see more" in text_content.lower():
                    if href.startswith("/"):
                        next_url = urllib.parse.urljoin("https://mbasic.facebook.com", href)
                    elif href.startswith("http"):
                        next_url = href

            _extract_groups_from_text(resp.text, groups_map)
            new_found = len(groups_map) - prev_count
            if new_found > 0:
                log(f"   ✅ mbasic phân trang (Trang {page}): Thêm {new_found} nhóm.")

            if not next_url or next_url == current_mbasic_url:
                break
            current_mbasic_url = next_url
            page += 1
    except Exception:
        pass

    # Khử trùng lặp đa tầng & sắp xếp danh sách nhóm
    raw_list = list(groups_map.values())
    result = _deduplicate_and_clean_groups(raw_list)

    log(f"🎉 Hoàn tất! Đã trích xuất thành công {len(result)} nhóm Facebook (Đã lọc trùng lặp ID/Tên).")
    return result
