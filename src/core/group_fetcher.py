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

    # Tạo cookie_str chuẩn
    if cookies_dict:
        parts = [f"{k}={v}" for k, v in cookies_dict.items() if k and v]
        cookie_str = "; ".join(parts)

    return cookies_dict, cookie_str, fb_dtsg


def parse_cookies_from_json(text: str) -> tuple[dict, str, str]:
    """Alias cho parse_cookies_from_any"""
    return parse_cookies_from_any(text)


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


def fetch_groups_via_browser(cookies: dict, logger=None, headless: bool = False, max_scrolls: int = 50) -> list[dict]:
    """
    Sử dụng trình duyệt tự động (Chrome Driver) gắn Cookie JSON của tài khoản,
    truy cập https://www.facebook.com/groups/joins/ và cuộn trang liên tục để tải toàn bộ 100% danh sách nhóm.
    """
    def log(msg: str):
        if logger:
            logger(msg)
        else:
            print(f"[BrowserGroupFetcher] {msg}")

    if not cookies or not isinstance(cookies, dict):
        log("❌ Không có Cookies hợp lệ để mở trình duyệt.")
        return []

    log("🌐 Đang khởi động trình duyệt Chrome gắn Cookie Facebook...")
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
    Gửi request tới Facebook qua tất cả các kênh (Desktop Relay all_joined_groups, GraphQL Pagination, mbasic seemore chain, và Browser Fallback)
    để lấy danh sách toàn bộ 100% tất cả các nhóm (100-200+ nhóm) mà tài khoản đã tham gia.

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

    user_id = str(cookies.get("c_user") or "")
    xs = str(cookies.get("xs") or "")
    if not user_id or not xs:
        log("❌ Cookies thiếu c_user hoặc xs. Vui lòng đăng nhập Facebook và xuất lại JSON từ extension.")
        return []

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

    log("🌐 Đang kết nối tới Facebook để lấy danh sách toàn bộ các nhóm bạn đã tham gia...")

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 1: Quét Desktop Joined Groups & Bóc tách Tokens / DocIDs / Cursors
    # --------------------------------------------------------------------------
    found_doc_ids = set()
    initial_joined_cursor = None
    all_cursors = []

    try:
        log("   📄 Đang tải trang Nhóm đã tham gia (Desktop)...")
        resp = session.get("https://www.facebook.com/groups/joins/", headers=headers_desktop, timeout=20)
        if "login.php" in resp.url or "checkpoint" in resp.url:
            log("   ⚠️ Phiên đăng nhập Facebook không hợp lệ hoặc đã hết hạn (chuyển hướng sang trang đăng nhập).")
        elif resp.status_code == 200:
            desktop_joins_html = resp.text
            _extract_groups_from_text(desktop_joins_html, groups_map)
            log(f"   ✅ Giao diện Desktop ban đầu: Đã trích xuất {len(groups_map)} nhóm.")

            # Bóc tách fb_dtsg từ mọi biến thể
            if not extracted_dtsg:
                for pattern in [
                    r'["\']DTSGInitialData["\'][^}]+?["\']token["\']\s*:\s*["\']([^"\']+)["\']',
                    r'["\']DTSGInitData["\'][^}]+?["\']token["\']\s*:\s*["\']([^"\']+)["\']',
                    r'["\']token["\']\s*:\s*["\']([a-zA-Z0-9:_-]{10,})["\']',
                    r'name=["\']fb_dtsg["\']\s+value=["\']([^"\']+)["\']',
                    r'["\']async_get_token["\']\s*:\s*["\']([^"\']+)["\']',
                    r'["\']DTSG_TOKEN["\']\s*:\s*["\']([^"\']+)["\']'
                ]:
                    dtsg_m = re.search(pattern, desktop_joins_html)
                    if dtsg_m:
                        extracted_dtsg = dtsg_m.group(1)
                        break

            # Bóc tách doc_id từ HTML nếu có
            for m in re.finditer(r'["\'](?:Groups(?:CometAllJoinedGroupsSection|CometJoinsRoot|TabJoined|CometLeftRail|Joined)[\w]*)PaginationQuery_facebookRelayOperation["\'][^}]+?["\']doc_id["\']\s*:\s*["\'](\d+)["\']', desktop_joins_html):
                found_doc_ids.add(m.group(1))
            for m in re.finditer(r'__d\(\"GroupsCometAllJoinedGroupsSectionPaginationQuery_facebookRelayOperation\"[^;]+?\\\"(\d+)\\\"', desktop_joins_html):
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
    # GIAI ĐOẠN 2: GraphQL Pagination (Lấy toàn bộ các trang nhóm tiếp theo qua Relay)
    # --------------------------------------------------------------------------
    if extracted_dtsg:
        log("🚀 Đang chạy GraphQL Pagination để lấy toàn bộ các trang nhóm tiếp theo...")
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
                    if line.startswith("for (;;);"):
                        line = line[len("for (;;);"):].strip()
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

                next_cursor = None
                has_next = False
                for line in g_resp.text.split("\n"):
                    line = line.strip()
                    if line.startswith("for (;;);"):
                        line = line[len("for (;;);"):].strip()
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
    # GIAI ĐOẠN 3: Quét Toàn Bộ Danh Mục mbasic Qua Chuỗi Seemore Link Chuyên Sâu
    # --------------------------------------------------------------------------
    categories = [
        ("membership", "Nhóm đã tham gia"),
        ("admin", "Nhóm bạn quản lý"),
        ("pinned", "Nhóm đã ghim"),
    ]

    log("🌐 Đang quét danh sách nhóm mbasic qua chuỗi liên kết xem thêm...")
    for cat_name, desc in categories:
        _crawl_mbasic_category(session, cat_name, desc, groups_map, headers_mobile, log)

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 4: Quét Thêm Mobile Web & Trang Nhóm User Profile
    # --------------------------------------------------------------------------
    extra_urls = [
        f"https://mbasic.facebook.com/{user_id}/groups/",
        f"https://m.facebook.com/groups/joins/",
        f"https://mbasic.facebook.com/groups/joins/",
    ]
    for e_url in extra_urls:
        try:
            prev_count = len(groups_map)
            resp = session.get(e_url, headers=headers_mobile, timeout=12)
            if resp.status_code == 200 and "login.php" not in resp.url:
                _extract_groups_from_mbasic_html(resp.text, groups_map)
                _extract_groups_from_text(resp.text, groups_map)
                new_found = len(groups_map) - prev_count
                if new_found > 0:
                    log(f"   ✅ Quét bổ sung ({e_url}): Thêm {new_found} nhóm (Tổng: {len(groups_map)} nhóm).")
        except Exception:
            pass

    # Khử trùng lặp đa tầng & sắp xếp danh sách nhóm
    raw_list = list(groups_map.values())
    result = _deduplicate_and_clean_groups(raw_list)

    # --------------------------------------------------------------------------
    # GIAI ĐOẠN 5: Browser Automation Fallback (Nếu HTTP bị Facebook giới hạn < 50 nhóm)
    # --------------------------------------------------------------------------
    if allow_browser_fallback and len(result) < 50:
        log(f"ℹ️ HTTP lấy được {len(result)} nhóm (< 50 nhóm). Đang tự động mở trình duyệt gắn Cookie để cuộn lấy 100% đầy đủ...")
        try:
            browser_result = fetch_groups_via_browser(cookies=cookies, logger=log, headless=True, max_scrolls=40)
            if len(browser_result) > len(result):
                result = browser_result
        except Exception as e:
            log(f"⚠️ Trình duyệt tự động gặp lỗi: {e}")

    log(f"🎉 Hoàn tất! Đã trích xuất thành công {len(result)} nhóm Facebook.")
    return result
