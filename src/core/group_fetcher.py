import re
import html
import json
import urllib.parse
import requests
from bs4 import BeautifulSoup
from src.core.proxy_utils import select_proxy


def parse_cookies_from_any(text: str) -> tuple[dict, str, str]:
    """
    Nhận diện và trích xuất Cookies + fb_dtsg từ chuỗi JSON copy từ tiện ích mở rộng (Cookie-Editor, J2Team, EditThisCookie...).
    
    Hỗ trợ đa dạng cấu trúc JSON:
    - Mảng JSON: [{"name": "c_user", "value": "1000..."}, {"name": "xs", "value": "..."}]
    - Đối tượng lồng: {"url": "...", "cookies": [{"name": "c_user", ...}]} (J2TEAM Cookies)
    - Đối tượng Key-Value: {"c_user": "1000...", "xs": "..."}
    - Chuỗi JSON có dấu phẩy thừa (trailing comma), nháy đơn (single quote), hoặc bọc trong markdown codeblock.
    
    Returns:
        tuple[dict, str, str]: (cookies_dict, cookie_string, fb_dtsg)
    """
    if not text:
        return {}, "", ""

    text = text.strip()
    # Loại bỏ codeblock markdown nếu có (```json ... ```)
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"\s*```$", "", text).strip()

    cookies_dict = {}
    cookie_str = ""
    fb_dtsg = ""

    def extract_from_obj(obj):
        if isinstance(obj, list):
            for item in obj:
                extract_from_obj(item)
        elif isinstance(obj, dict):
            # Nếu là cookie item dạng {"name": "...", "value": "..."}
            name = str(obj.get("name") or obj.get("key") or "").strip()
            value = str(obj.get("value") or "").strip()
            if name and value and name not in cookies_dict:
                # Bỏ qua các thuộc tính metadata không phải cookie
                if name.lower() not in ["url", "cookies", "data", "items", "domain", "path", "samesite"]:
                    cookies_dict[name] = value

            # Nếu dict chứa danh sách cookies con (ví dụ J2TEAM export: {"url": "...", "cookies": [...]})
            for sub_key in ["cookies", "data", "items", "cookie"]:
                if sub_key in obj and isinstance(obj[sub_key], (list, dict)):
                    extract_from_obj(obj[sub_key])

            # Nếu là dict dạng {"c_user": "1000...", "xs": "..."}
            for k, v in obj.items():
                if isinstance(v, (str, int, float)) and k not in ["url", "domain", "path", "expirationDate", "storeId", "sameSite"]:
                    k_str = str(k).strip()
                    v_str = str(v).strip()
                    if k_str and v_str and k_str not in cookies_dict:
                        cookies_dict[k_str] = v_str

    # 1. Thử parse với json.loads chuẩn
    parsed_successfully = False
    try:
        data = json.loads(text)
        extract_from_obj(data)
        if "c_user" in cookies_dict or len(cookies_dict) > 0:
            parsed_successfully = True
    except Exception:
        pass

    # 2. Nếu json.loads lỗi, sửa dấu phẩy thừa (trailing commas)
    if not parsed_successfully:
        try:
            cleaned_json = re.sub(r",\s*([\]}])", r"\1", text)
            data = json.loads(cleaned_json)
            extract_from_obj(data)
            if "c_user" in cookies_dict or len(cookies_dict) > 0:
                parsed_successfully = True
        except Exception:
            pass

    # 3. Nếu vẫn lỗi, thử parse với ast.literal_eval (xử lý nháy đơn 'name': 'c_user')
    if not parsed_successfully:
        try:
            import ast
            data = ast.literal_eval(text)
            extract_from_obj(data)
            if "c_user" in cookies_dict or len(cookies_dict) > 0:
                parsed_successfully = True
        except Exception:
            pass

    # 4. Fallback Regex bóc tách trực tiếp các cặp key/name/value trong JSON
    if not cookies_dict or "c_user" not in cookies_dict:
        # Bóc tách {"name": "c_user", "value": "1000..."}
        for m in re.finditer(r'["\'](?:name|key)["\']\s*:\s*["\']([^"\']+)["\']\s*,\s*["\']value["\']\s*:\s*["\']([^"\']*)["\']', text):
            k, v = m.group(1).strip(), m.group(2).strip()
            if k and v:
                cookies_dict[k] = v

        for m in re.finditer(r'["\']value["\']\s*:\s*["\']([^"\']*)["\']\s*,\s*["\'](?:name|key)["\']\s*:\s*["\']([^"\']+)["\']', text):
            v, k = m.group(1).strip(), m.group(2).strip()
            if k and v:
                cookies_dict[k] = v

        # Bóc tách trực tiếp c_user, xs, datr, sb nếu vẫn chưa có
        for field in ["c_user", "xs", "datr", "sb", "fr", "dpr", "wd", "presence"]:
            if field not in cookies_dict:
                m_field = re.search(r'["\']' + field + r'["\']\s*:\s*["\']([^"\']+)["\']', text)
                if m_field:
                    cookies_dict[field] = m_field.group(1).strip()

    # 5. Fallback nếu text là dạng cookie header string: 'c_user=123; xs=abc; ...'
    if not cookies_dict:
        for part in text.split(';'):
            part = part.strip()
            if '=' in part:
                k, v = part.split('=', 1)
                k_clean = k.strip().strip('"\'')
                v_clean = v.strip().strip('"\'')
                if k_clean and v_clean and k_clean not in cookies_dict:
                    cookies_dict[k_clean] = v_clean

    # Tạo cookie_str chuẩn
    if cookies_dict:
        parts = [f"{k}={v}" for k, v in cookies_dict.items() if k and v]
        cookie_str = "; ".join(parts)

    return cookies_dict, cookie_str, fb_dtsg


def parse_cookies_from_json(text: str) -> tuple[dict, str, str]:
    """Alias cho parse_cookies_from_any"""
    return parse_cookies_from_any(text)


def _clean_group_name(name: str) -> str:
    """
    Làm sạch tên nhóm Facebook từ HTML/DOM text:
    Loại bỏ triệt để các chuỗi rác như 'Chưa đọc', 'Lần hoạt động gần nhất:...',
    mốc thời gian, số lượng thành viên, badge thông báo, v.v.
    """
    if not name:
        return ""
    # Giải mã chuỗi unicode escape (như \u0110 -> Đ, \u1ed9 -> ộ)
    try:
        name = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m.group(1), 16)), name)
    except Exception:
        pass
    name = html.unescape(name).strip()
    
    # Nếu text nhiều dòng (do DOM innerText lấy cả thẻ con), dòng đầu tiên là tên nhóm
    lines = [line.strip() for line in name.splitlines() if line.strip()]
    if lines:
        name = lines[0]

    name = re.sub(r'<[^>]+>', '', name)
    name = re.sub(r'\\u003[cC].*?\\u003[eE]', '', name)

    # Danh sách các pattern chuỗi thừa cần loại bỏ triệt để
    garbage_patterns = [
        # Hoạt động gần nhất / Active status
        r'[\(\[]?\s*(?:Lần\s+)?hoạt\s+động\s+gần\s+(?:nhất|đây)\s*:\s*[^)\]]+[\)\]]?',
        r'[\(\[]?\s*(?:Last\s+)?active(?:\s*:|\s+\d+)[^)\]]*[\)\]]?',
        r'[\(\[]\s*(?:Last\s+)?active\s+[^)\]]+[\)\]]',
        r'[\(\[]\s*hoạt\s+động\s+[^)\]]+[\)\]]',

        # Nhóm/Thành viên/Quyền riêng tư
        r'\s*·\s*[\d,.]+[KkMm]?\s*(thành viên|members?|bài viết|posts?).*$',
        r'\s*·\s*(Nhóm công khai|Nhóm riêng tư|Public group|Private group).*$',
        r'\s*·\s*(Chưa đọc|Chưa xem|Mới|Unread|New).*$',
        
        # Thông báo quyền đăng/bình luận (vd: "Từ giờ, bạn có thể đăng bài và bình luận trong... 6 phút")
        r'[\s·•\-_|:]*(?:Từ giờ|Bây giờ|Hiện tại|You can now)[\s\S]*?(?:đăng bài|bình luận|post|comment)[\s\S]*$',
        r'Chào mừng bạn đến với[\s\S]*?(?:đăng bài|kết nối|post|connect)[\s\S]*$',
        r'[\s·•\-_|:]*Xem nhóm$',
        r'[\s·•\-_|:]*View group$',

        # Mốc thời gian (vd: 2 giờ trước, 5 ngày trước, Hôm qua lúc...)
        r'\s*·?\s*\d+\s*(phút|giờ|ngày|tuần|tháng|năm|mins?|minutes?|hours?|hrs?|days?|weeks?|months?|years?)\s*(trước|ago).*$',
        r'\s*·?\s*(Hôm qua lúc|Yesterday at|Vừa xong|Just now).*$',
        
        # Bài viết mới / Trạng thái đọc
        r'\s*·?\s*\d+\+?\s*(bài viết mới|new posts?|tin mới).*$',
        r'^\s*(Chưa đọc|Chưa xem|Mới|Unread|New)\s*·?\s*',
        r'\s*·?\s*(Chưa đọc|Chưa xem|Mới|Unread|New)\s*$',
        
        # Badge số thông báo ví dụ (5) Tên nhóm
        r'^\s*\(\d+\)\s*'
    ]

    for pat in garbage_patterns:
        name = re.sub(pat, '', name, flags=re.IGNORECASE).strip()

    # Dọn dẹp dấu chấm giữa thừa hoặc gạch ngang ở đầu/cuối
    name = re.sub(r'^[\s·•\-_|:]+|[\s·•\-_|:]+$', '', name).strip()
    name = re.sub(r'\s+', ' ', name)
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
                v_state = str(obj.get("viewer_joined_state") or obj.get("viewer_status") or obj.get("membership_state") or "").upper()
                if v_state in ["NOT_JOINED", "CANNOT_JOIN", "REQUESTED", "NONE"]:
                    return
                g_id = obj.get("id") or obj.get("group_id") or ""
                g_name = obj.get("name") or obj.get("group_name") or ""
                g_url = obj.get("url") or ""
                add_item(g_id, g_name, g_url)

            if "group_id" in obj and ("group_name" in obj or "name" in obj):
                v_state = str(obj.get("viewer_joined_state") or obj.get("viewer_status") or obj.get("membership_state") or "").upper()
                if v_state not in ["NOT_JOINED", "CANNOT_JOIN", "REQUESTED", "NONE"]:
                    add_item(obj["group_id"], obj.get("group_name") or obj.get("name"), obj.get("url", ""))

            if "group" in obj and isinstance(obj["group"], dict):
                g = obj["group"]
                v_state = str(g.get("viewer_joined_state") or g.get("viewer_status") or g.get("membership_state") or "").upper()
                if v_state not in ["NOT_JOINED", "CANNOT_JOIN", "REQUESTED", "NONE"]:
                    add_item(g.get("id") or g.get("group_id"), g.get("name"), g.get("url"))

            for v in obj.values():
                traverse(v)
        elif isinstance(obj, list):
            for item in obj:
                traverse(item)

    # 2. Xử lý cả chuỗi gốc và chuỗi đã unescape sâu
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

        # C. Regex bắt Group typename và thuộc tính trong JSON (chỉ lấy nếu không có cờ NOT_JOINED / CANNOT_JOIN / REQUESTED)
        for m in re.finditer(r'\{[^{}]*?"__typename"\s*:\s*"Group"[^{}]*?\}', t):
            block = m.group(0)
            if any(s in block for s in ['"NOT_JOINED"', '"CANNOT_JOIN"', '"REQUESTED"']):
                continue
            id_m = re.search(r'"(?:id|group_id)"\s*:\s*"(\d{4,})"', block)
            name_m = re.search(r'"(?:name|group_name)"\s*:\s*"([^"]+)"', block)
            if id_m and name_m:
                add_item(id_m.group(1), name_m.group(1))


def _extract_groups_from_mbasic_html(html_text: str, groups_map: dict[str, dict]):
    """
    Bóc tách danh sách nhóm từ trang HTML của mbasic/mobile Facebook.
    Chỉ lấy các link nhóm hợp lệ, bỏ qua link điều hướng menu, tạo nhóm, khám phá.
    """
    if not html_text:
        return
    try:
        soup = BeautifulSoup(html_text, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            m = re.search(r'/groups/([a-zA-Z0-9._-]+)', href)
            if not m:
                continue
            slug = m.group(1).strip()
            if slug.lower() in IGNORED_SLUGS or any(sub in slug for sub in ('posts', 'permalink', 'user', 'chats', 'messages', 'direct', 'threads', 'thread', 'feed', 'create', 'search', 'notifications', 'settings')):
                continue
            name = _clean_group_name(a.get_text())
            if not name or len(name) < 2:
                continue
            if any(k in name.lower() for k in ['xem thêm', 'see more', 'tạo nhóm', 'create group', 'khám phá', 'discover', 'thông báo', 'bảng tin']):
                continue
            url = f"https://www.facebook.com/groups/{slug}/"
            gid = slug if slug.isdigit() else ""
            if url not in groups_map:
                groups_map[url] = {
                    "name": name,
                    "url": url,
                    "group_id": gid
                }
            else:
                existing = groups_map[url]
                if existing["name"].startswith("Nhóm ") and not name.startswith("Nhóm "):
                    existing["name"] = name
                if not existing["group_id"] and gid:
                    existing["group_id"] = gid
    except Exception:
        pass


def _deduplicate_and_clean_groups(groups_list: list[dict]) -> list[dict]:
    """
    Khử trùng lặp đa tầng danh sách nhóm Facebook:
    - Gộp các bản ghi có cùng ID số hoặc cùng Vanity Slug alias
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




def _crawl_mbasic_category(session: requests.Session, category_name: str, desc: str, groups_map: dict[str, dict], headers_mobile: dict, log):
    """
    Duyệt tuần tự theo chuỗi liên kết 'seemore' (Xem thêm) thực tế của Facebook mbasic
    để lấy sạch 100% tất cả các trang nhóm mà không bị dừng sớm.
    """
    base_url = f"https://mbasic.facebook.com/groups/?seemore&category={category_name}"
    current_url = base_url
    page = 1
    visited_urls = set()
    
    while current_url and page <= 50:
        if current_url in visited_urls:
            break
        visited_urls.add(current_url)
        
        try:
            prev_count = len(groups_map)
            resp = session.get(current_url, headers=headers_mobile, timeout=15)
            if resp.status_code != 200 or "login.php" in resp.url or "checkpoint" in resp.url:
                break
            
            _extract_groups_from_mbasic_html(resp.text, groups_map)
            new_found = len(groups_map) - prev_count
            if new_found > 0:
                log(f"   ✅ mbasic {desc} (Trang {page}): Thêm {new_found} nhóm (Tổng: {len(groups_map)} nhóm).")
            
            # Tìm link 'Xem thêm' / 'seemore' tiếp theo trong HTML
            soup = BeautifulSoup(resp.text, "html.parser")
            next_url = None
            for a in soup.find_all("a", href=True):
                href = a.get("href", "")
                text_content = a.get_text().strip().lower()
                # Link trang tiếp theo trên mbasic chứa seemore hoặc start= hoặc refid
                if "category=" in href and category_name in href:
                    if "start=" in href or "seemore" in href or "xem thêm" in text_content or "see more" in text_content:
                        full_href = urllib.parse.urljoin("https://mbasic.facebook.com", href)
                        if full_href not in visited_urls:
                            next_url = full_href
                            break
                elif ("start=" in href and "category=" not in href) or "seemore" in href:
                    if "xem thêm" in text_content or "see more" in text_content:
                        full_href = urllib.parse.urljoin("https://mbasic.facebook.com", href)
                        if full_href not in visited_urls:
                            next_url = full_href
                            break

            if not next_url:
                # Thử offset tiếp theo nếu không tìm thấy thẻ a seemore trực tiếp
                next_offset = page * 20
                fallback_offset_url = f"https://mbasic.facebook.com/groups/?seemore&category={category_name}&start={next_offset}"
                if fallback_offset_url not in visited_urls and (new_found > 0 or page == 1):
                    next_url = fallback_offset_url
                else:
                    break

            current_url = next_url
            page += 1
        except Exception as e:
            log(f"   ⚠️ Lỗi tải trang {page} {desc}: {e}")
            break


def fetch_groups_via_browser(cookies: dict, logger=None, headless: bool = True, max_scrolls: int = 40) -> list[dict]:
    """
    Sử dụng trình duyệt Headless (SeleniumBase Chrome Driver) gắn Cookie Facebook,
    truy cập trực tiếp https://www.facebook.com/groups/joins/, cuộn trang để tải toàn bộ danh sách nhóm
    và trích xuất tên nhóm sạch sẽ (loại bỏ mọi từ rác).
    """
    def log(msg: str):
        if logger:
            logger(msg)
        else:
            print(f"[BrowserGroupFetcher] {msg}")

    if not cookies or not isinstance(cookies, dict):
        log("❌ Không có Cookies hợp lệ để mở trình duyệt.")
        return []

    log("🌐 Đang khởi động trình duyệt Headless gắn Cookie Facebook...")
    import time
    from seleniumbase import Driver

    driver = None
    groups_map = {}
    try:
        driver = Driver(browser="chrome", headless=headless, uc=True)
        # Truy cập facebook trước để nạp cookie cho đúng domain
        driver.get("https://www.facebook.com/404")
        time.sleep(1)

        # Gắn cookies vào trình duyệt
        for name, value in cookies.items():
            try:
                driver.add_cookie({
                    "name": name,
                    "value": value,
                    "domain": ".facebook.com",
                    "path": "/"
                })
            except Exception:
                pass

        log("🚀 Đang mở trang Nhóm đã tham gia (https://www.facebook.com/groups/joins/)...")
        driver.get("https://www.facebook.com/groups/joins/")
        time.sleep(3)

        if "login.php" in driver.current_url or "checkpoint" in driver.current_url:
            log("⚠️ Facebook chuyển hướng sang trang đăng nhập. Cookie có thể đã hết hạn.")

        # Cuộn trang tự động để tải toàn bộ danh sách nhóm
        log("📜 Đang cuộn trang tự động để tải toàn bộ danh sách nhóm...")
        last_count = 0
        no_new_cycles = 0

        for scroll_idx in range(1, max_scrolls + 1):
            # 1. Trích xuất trực tiếp từ các thẻ DOM bằng JavaScript
            try:
                dom_items = driver.execute_script("""
                    const results = [];
                    // Chỉ lấy các nhóm nằm trong vùng xem trước nhóm chính
                    const container = document.querySelector('div[aria-label="Bản xem trước nhóm"][role="main"]') || document;
                    const elements = container.querySelectorAll('a[href*="/groups/"]');
                    for (const el of elements) {
                        const href = el.getAttribute('href') || el.href || '';
                        const text = el.innerText || el.textContent || '';
                        // Loại bỏ các nút action/link điều hướng không phải tên nhóm
                        if (href.includes('/groups/') && text.trim() && text.trim() !== 'Xem nhóm' && text.trim() !== 'View group') {
                            results.push({href: href, text: text});
                        }
                    }
                    return results;
                """)
                if dom_items:
                    for item in dom_items:
                        href = item.get("href", "")
                        raw_text = item.get("text", "")
                        m = re.search(r'/groups/([a-zA-Z0-9._-]+)', href)
                        if not m:
                            continue
                        slug = m.group(1).strip()
                        if slug.lower() in IGNORED_SLUGS or any(sub in slug.lower() for sub in ('posts', 'permalink', 'user', 'chats', 'messages', 'direct', 'threads', 'thread', 'feed', 'create', 'search', 'notifications', 'settings', 'joins', 'discover')):
                            continue
                        
                        clean_name = _clean_group_name(raw_text)
                        url = f"https://www.facebook.com/groups/{slug}/"
                        gid = slug if slug.isdigit() else ""
                        if url not in groups_map:
                            groups_map[url] = {
                                "name": clean_name if clean_name else (f"Nhóm {gid}" if gid else url),
                                "url": url,
                                "group_id": gid
                            }
                        elif clean_name and (groups_map[url]["name"].startswith("Nhóm ") or len(clean_name) > len(groups_map[url]["name"])):
                            groups_map[url]["name"] = clean_name
            except Exception:
                pass

            # 2. Bóc tách bổ sung từ page_source
            page_html = driver.page_source
            _extract_groups_from_text(page_html, groups_map)
            _extract_groups_from_mbasic_html(page_html, groups_map)

            current_count = len(groups_map)
            if current_count > last_count:
                log(f"   ✅ Đã tải được {current_count} nhóm (Cuộn lần {scroll_idx})...")
                last_count = current_count
                no_new_cycles = 0
            else:
                no_new_cycles += 1
                if no_new_cycles >= 4:
                    # Đã cuộn đến đáy trang
                    break

            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1.5)

        raw_list = list(groups_map.values())
        result = _deduplicate_and_clean_groups(raw_list)
        log(f"🎉 Hoàn tất quét trình duyệt! Đã lấy thành công {len(result)} nhóm Facebook.")
        return result
    except Exception as e:
        log(f"❌ Lỗi khi quét qua trình duyệt: {str(e)}")
        raw_list = list(groups_map.values())
        return _deduplicate_and_clean_groups(raw_list)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def fetch_user_joined_groups(cookies: dict, fb_dtsg: str = "", max_pages: int = 40, logger=None, proxy=None, allow_browser_fallback: bool = True) -> list[dict]:
    """
    Lấy danh sách toàn bộ các nhóm Facebook đã tham gia bằng trình duyệt Headless mở trực tiếp https://www.facebook.com/groups/joins/
    """
    return fetch_groups_via_browser(cookies=cookies, logger=logger, headless=True, max_scrolls=max_pages)
