import sqlite3
import os
import shutil
import json
from contextlib import contextmanager
from datetime import datetime

from src.config.constants import DEFAULT_DB_PATH, LEGACY_DB_PATH, DATA_DIR
from src.config.default_prompts import (
    DEFAULT_AI_PROMPT,
    DEFAULT_BUYER_AI_PROMPT,
    DEFAULT_RENTAL_AI_PROMPT,
    DEFAULT_JOB_AI_PROMPT,
)


def migrate_legacy_database(target_db_path: str = None, legacy_db_path: str = None) -> bool:
    """
    Tự động chuyển đổi dữ liệu từ vị trí cũ (data/facebook_scraper.sqlite)
    sang vị trí mới (~/.facebook-notification/facebook_scraper.sqlite) nếu database mới chưa tồn tại.
    """
    if target_db_path is None:
        target_db_path = DEFAULT_DB_PATH
    if legacy_db_path is None:
        legacy_db_path = LEGACY_DB_PATH

    if not os.path.exists(target_db_path) and os.path.exists(legacy_db_path):
        try:
            os.makedirs(os.path.dirname(os.path.abspath(target_db_path)), exist_ok=True)
            shutil.copy2(legacy_db_path, target_db_path)
            for ext in ["-wal", "-shm"]:
                legacy_extra = legacy_db_path + ext
                target_extra = target_db_path + ext
                if os.path.exists(legacy_extra):
                    shutil.copy2(legacy_extra, target_extra)
            print(f"[DB Migration] Successfully migrated database from '{legacy_db_path}' to '{target_db_path}'")
            return True
        except Exception as e:
            print(f"[DB Migration] Warning: Failed to migrate legacy database: {e}")
            return False
    return False


@contextmanager
def get_connection(db_path: str = None):
    """Tạo kết nối SQLite với Row factory và bật foreign keys, WAL mode, tự động commit và close"""
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: str = None):
    """Khởi tạo cấu trúc các bảng và index cho SQLite database"""
    if db_path is None:
        migrate_legacy_database()
        db_path = DEFAULT_DB_PATH
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Bảng posts
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                post_id TEXT PRIMARY KEY,
                story_id TEXT,
                post_type TEXT,
                message TEXT,
                comment_count INTEGER DEFAULT 0,
                group_name TEXT,
                page_name TEXT,
                permalink TEXT,
                creation_time INTEGER,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)

        # 2. Bảng comments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                comment_id TEXT PRIMARY KEY,
                post_id TEXT NOT NULL,
                text TEXT,
                reaction_count TEXT DEFAULT '0',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            );
        """)

        # 3. Bảng replies
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS replies (
                reply_id TEXT PRIMARY KEY,
                comment_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                text TEXT,
                reaction_count TEXT DEFAULT '0',
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (comment_id) REFERENCES comments(comment_id) ON DELETE CASCADE,
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            );
        """)

        # 4. Bảng media (ảnh và video)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                media_type TEXT DEFAULT 'photo',
                media_id TEXT,
                url TEXT,
                saved_as TEXT,
                width INTEGER,
                height INTEGER,
                thumbnail TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            );
        """)

        # 5. Bảng settings (lưu toàn bộ cấu hình app, URLs, Telegram, AI)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)

        # 6. Bảng facebook_groups (lưu danh sách nhóm Facebook động)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS facebook_groups (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                url TEXT,
                group_id TEXT,
                last_scraped_at TEXT,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                updated_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)

        # 7. Bảng ai_analyses (lưu lịch sử phân tích AI cho bài viết + comment)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ai_analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id TEXT NOT NULL,
                comment_id TEXT,
                group_name TEXT,
                matched_keyword TEXT,
                matched_source TEXT,
                model_used TEXT,
                should_notify INTEGER DEFAULT 0,
                is_seller INTEGER DEFAULT 0,
                device_name TEXT,
                price TEXT,
                seller_type TEXT,
                seller_snippet TEXT,
                reason TEXT,
                raw_response TEXT,
                telegram_sent INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
            );
        """)

        # 8. Bảng logs (lưu lịch sử hoạt động, tự dọn dẹp > 1 ngày)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                level TEXT DEFAULT 'INFO',
                message TEXT,
                module TEXT DEFAULT 'APP',
                created_at TEXT DEFAULT (datetime('now', 'localtime'))
            );
        """)

        # Migration kiểm tra và thêm cột telegram_sent, comment_id nếu bảng ai_analyses đã tồn tại từ trước
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(ai_analyses)").fetchall()]
        if cols:
            if "telegram_sent" not in cols:
                cursor.execute("ALTER TABLE ai_analyses ADD COLUMN telegram_sent INTEGER DEFAULT 0")
                cursor.execute("UPDATE ai_analyses SET telegram_sent = 1 WHERE telegram_sent IS NULL OR telegram_sent = 0")
            if "comment_id" not in cols:
                cursor.execute("ALTER TABLE ai_analyses ADD COLUMN comment_id TEXT")

        # Migration bảng posts bổ sung ai_status, matched_keyword, matched_source, matched_comment_id
        cols_posts = [r[1] for r in cursor.execute("PRAGMA table_info(posts)").fetchall()]
        if cols_posts:
            if "ai_status" not in cols_posts:
                cursor.execute("ALTER TABLE posts ADD COLUMN ai_status INTEGER DEFAULT 0")
            if "matched_keyword" not in cols_posts:
                cursor.execute("ALTER TABLE posts ADD COLUMN matched_keyword TEXT DEFAULT ''")
            if "matched_source" not in cols_posts:
                cursor.execute("ALTER TABLE posts ADD COLUMN matched_source TEXT DEFAULT ''")
            if "matched_comment_id" not in cols_posts:
                cursor.execute("ALTER TABLE posts ADD COLUMN matched_comment_id TEXT DEFAULT ''")

        # Migration bảng facebook_groups bổ sung last_scraped_at
        cols_groups = [r[1] for r in cursor.execute("PRAGMA table_info(facebook_groups)").fetchall()]
        if cols_groups and "last_scraped_at" not in cols_groups:
            cursor.execute("ALTER TABLE facebook_groups ADD COLUMN last_scraped_at TEXT")

        # Indexes để tối ưu hóa truy vấn
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_replies_comment_id ON replies(comment_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_replies_post_id ON replies(post_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_post_id ON media(post_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_creation_time ON posts(creation_time);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_posts_ai_status ON posts(ai_status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_post_id ON ai_analyses(post_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_comment_id ON ai_analyses(comment_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_post_comment ON ai_analyses(post_id, comment_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_should_notify ON ai_analyses(should_notify);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_telegram_sent ON ai_analyses(telegram_sent, should_notify);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_created_at ON ai_analyses(created_at);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_logs_created_at ON logs(created_at);")

        conn.commit()
    seed_default_settings(db_path)
    migrate_group_urls_if_needed(db_path)
    cleanup_old_logs(days=1, db_path=db_path)


def migrate_ai_analyses_telegram_sent_if_needed(db_path: str = None):
    """Tự động bổ sung cột telegram_sent vào bảng ai_analyses nếu chưa tồn tại"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cols = [r[1] for r in cursor.execute("PRAGMA table_info(ai_analyses)").fetchall()]
        if cols and "telegram_sent" not in cols:
            cursor.execute("ALTER TABLE ai_analyses ADD COLUMN telegram_sent INTEGER DEFAULT 0")
            cursor.execute("UPDATE ai_analyses SET telegram_sent = 1 WHERE telegram_sent IS NULL OR telegram_sent = 0")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_analyses_telegram_sent ON ai_analyses(telegram_sent, should_notify);")
            conn.commit()


def migrate_group_urls_if_needed(db_path: str = None):
    """Tự động chuyển đổi settings.group_urls cũ sang bảng facebook_groups nếu bảng groups trống"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        count_groups = cursor.execute("SELECT COUNT(*) FROM facebook_groups").fetchone()[0]
        if count_groups == 0:
            row = cursor.execute("SELECT value FROM settings WHERE key = 'group_urls'").fetchone()
            if row and row["value"]:
                lines = [line.strip() for line in row["value"].split("\n") if line.strip()]
                for line in lines:
                    cursor.execute("""
                        INSERT INTO facebook_groups (name, url, group_id, created_at, updated_at)
                        VALUES (?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
                    """, ("", line, ""))
                conn.commit()


# ==============================================================================
# Facebook Groups CRUD Helpers
# ==============================================================================

def get_all_groups(db_path: str = None) -> list[dict]:
    """Lấy toàn bộ danh sách group trong SQLite"""
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT id, name, url, group_id, last_scraped_at, created_at, updated_at FROM facebook_groups ORDER BY id ASC").fetchall()
        return [dict(r) for r in rows]


def add_group(url: str, name: str = "", group_id: str = "", db_path: str = None) -> int:
    """Thêm một group mới vào SQLite, trả về ID vừa thêm"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO facebook_groups (name, url, group_id, created_at, updated_at)
            VALUES (?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
        """, (name.strip(), url.strip(), group_id.strip()))
        conn.commit()
        return cursor.lastrowid


def update_group(group_db_id: int, name: str = None, url: str = None, group_id: str = None, db_path: str = None) -> bool:
    """Cập nhật thông tin một group trong SQLite"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        updates = []
        params = []
        if name is not None:
            updates.append("name = ?")
            params.append(name.strip())
        if url is not None:
            updates.append("url = ?")
            params.append(url.strip())
        if group_id is not None:
            updates.append("group_id = ?")
            params.append(group_id.strip())
        if not updates:
            return False
        updates.append("updated_at = datetime('now', 'localtime')")
        params.append(group_db_id)
        sql = f"UPDATE facebook_groups SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0


def delete_group(group_db_id: int, db_path: str = None) -> bool:
    """Xóa một group khỏi SQLite theo ID"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM facebook_groups WHERE id = ?", (group_db_id,))
        conn.commit()
        return cursor.rowcount > 0


def save_all_groups(groups: list[dict], db_path: str = None):
    """Lưu/đồng bộ toàn bộ danh sách group vào bảng facebook_groups (giữ lại last_scraped_at)"""
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        old_scraped_map = {}
        rows = cursor.execute("SELECT group_id, url, last_scraped_at FROM facebook_groups WHERE last_scraped_at IS NOT NULL").fetchall()
        for r in rows:
            if r["group_id"]:
                old_scraped_map[f"id:{r['group_id']}"] = r["last_scraped_at"]
            if r["url"]:
                old_scraped_map[f"url:{r['url']}"] = r["last_scraped_at"]

        cursor.execute("DELETE FROM facebook_groups")
        for g in groups:
            name = (g.get("name") or "").strip()
            url = (g.get("url") or "").strip()
            group_id = (g.get("group_id") or "").strip()
            if not url and not name:
                continue
            last_scraped = g.get("last_scraped_at") or old_scraped_map.get(f"id:{group_id}") or old_scraped_map.get(f"url:{url}")
            cursor.execute("""
                INSERT INTO facebook_groups (name, url, group_id, last_scraped_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, datetime('now', 'localtime'), datetime('now', 'localtime'))
            """, (name, url, group_id, last_scraped))
        conn.commit()


def update_group_last_scraped(group_identifier: str, db_path: str = None) -> bool:
    """Cập nhật thời gian cào dữ liệu gần nhất cho nhóm theo group_id hoặc url"""
    if not group_identifier:
        return False
    gid_or_url = str(group_identifier).strip()
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE facebook_groups
            SET last_scraped_at = datetime('now', 'localtime'),
                updated_at = datetime('now', 'localtime')
            WHERE group_id = ? OR url = ? OR url LIKE ?
        """, (gid_or_url, gid_or_url, f"%{gid_or_url}%"))
        conn.commit()
        return cursor.rowcount > 0



# Các hằng số Prompt (DEFAULT_AI_PROMPT, DEFAULT_BUYER_AI_PROMPT, DEFAULT_RENTAL_AI_PROMPT, DEFAULT_JOB_AI_PROMPT)
# được import từ src.config.default_prompts




def seed_default_settings(db_path: str = None):
    """Khởi tạo giá trị cấu hình mặc định nếu chưa có"""
    defaults = {
        "group_urls": "",
        "keywords": "",
        "post_count": "5",
        "min_comments": "0",
        "infinite_loop": "0",
        "loop_interval": "60",
        "telegram_enabled": "0",
        "telegram_token": "",
        "telegram_chat_id": "",
        "notify_on_finish": "0",
        "notify_on_keyword": "0",
        "ai_enabled": "0",
        "ai_base_url": "",
        "ai_api_key": "",
        "ai_model": "gpt-4o-mini",
        "ai_models": "gpt-4o-mini, gpt-4o, gemini-2.0-flash, gemma4-31b",
        "ai_prompt": DEFAULT_AI_PROMPT,
        "ai_timeout": "20",
        "language": "vi"
    }
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for key, val in defaults.items():
            cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, str(val)))
        conn.commit()


def get_setting(key: str, default=None, db_path: str = None) -> str:
    """Lấy giá trị của 1 key cấu hình trong SQLite"""
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str, db_path: str = None):
    """Lưu hoặc cập nhật 1 key cấu hình vào SQLite"""
    with get_connection(db_path) as conn:
        conn.execute("""
            INSERT INTO settings (key, value, updated_at) 
            VALUES (?, ?, datetime('now', 'localtime'))
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now', 'localtime')
        """, (key, str(value) if value is not None else ""))
        conn.commit()


def get_all_settings(db_path: str = None) -> dict:
    """Lấy toàn bộ key-value trong bảng settings"""
    with get_connection(db_path) as conn:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}


def save_settings_batch(settings_dict: dict, db_path: str = None):
    """Lưu hàng loạt key-value vào bảng settings"""
    with get_connection(db_path) as conn:
        for k, v in settings_dict.items():
            conn.execute("""
                INSERT INTO settings (key, value, updated_at) 
                VALUES (?, ?, datetime('now', 'localtime'))
                ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = datetime('now', 'localtime')
            """, (k, str(v) if v is not None else ""))
        conn.commit()


def post_exists(post_id: str, db_path: str = None) -> bool:
    """Kiểm tra bài viết đã tồn tại trong SQLite hay chưa"""
    if not post_id:
        return False
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT 1 FROM posts WHERE post_id = ?", (str(post_id),)).fetchone()
        return bool(row)


def comment_exists(comment_id: str, db_path: str = None) -> bool:
    """Kiểm tra comment đã tồn tại trong SQLite hay chưa"""
    if not comment_id:
        return False
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT 1 FROM comments WHERE comment_id = ?", (str(comment_id),)).fetchone()
        return bool(row)


def reply_exists(reply_id: str, db_path: str = None) -> bool:
    """Kiểm tra reply đã tồn tại trong SQLite hay chưa"""
    if not reply_id:
        return False
    with get_connection(db_path) as conn:
        row = conn.execute("SELECT 1 FROM replies WHERE reply_id = ?", (str(reply_id),)).fetchone()
        return bool(row)


def save_or_update_post(post_type: str, post_id: str, post_data: dict, comments_data: list = None, db_path: str = None) -> dict:
    """
    Lưu bài viết và comment vào SQLite:
    - Nếu post chưa tồn tại: Insert post, nạp media, nạp comment + reply.
    - Nếu post đã tồn tại: Cập nhật comment_count và updated_at cho post, chỉ nạp thêm các comment/reply mới chưa có.
    """
    if not post_id:
        return {"post_created": False, "comments_added": 0, "replies_added": 0, "media_added": 0}

    post_id = str(post_id)
    comments_data = comments_data or []
    stats = {
        "post_created": False,
        "comments_added": 0,
        "replies_added": 0,
        "media_added": 0
    }

    # Trích xuất dữ liệu post
    story_id = post_data.get("id") or post_data.get("story_id") or ""
    message = post_data.get("message") or post_data.get("text") or ""
    comment_count = post_data.get("comment_count")
    if comment_count is None:
        comment_count = len(comments_data)
    else:
        try:
            comment_count = int(comment_count)
        except (ValueError, TypeError):
            comment_count = len(comments_data)

    group_name = post_data.get("group_name") or ""
    page_name = post_data.get("page_name") or ""
    permalink = post_data.get("permalink") or ""
    creation_time = post_data.get("creation_time")

    with get_connection(db_path) as conn:
        cursor = conn.cursor()

        # Kiểm tra post tồn tại
        exists_row = cursor.execute("SELECT 1 FROM posts WHERE post_id = ?", (post_id,)).fetchone()
        
        if not exists_row:
            # 1. Insert post mới
            cursor.execute("""
                INSERT INTO posts (post_id, story_id, post_type, message, comment_count, group_name, page_name, permalink, creation_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, story_id, post_type, message, comment_count, group_name, page_name, permalink, creation_time))
            stats["post_created"] = True

            # 2. Insert media
            # Case A: photos/videos trong group_post
            photos = post_data.get("photos", [])
            for p in photos:
                if isinstance(p, dict):
                    m_id = p.get("id") or ""
                    url = p.get("url") or ""
                    saved_as = p.get("saved_as") or ""
                    w = p.get("width")
                    h = p.get("height")
                    cursor.execute("""
                        INSERT INTO media (post_id, media_type, media_id, url, saved_as, width, height)
                        VALUES (?, 'photo', ?, ?, ?, ?, ?)
                    """, (post_id, m_id, url, saved_as, w, h))
                    stats["media_added"] += 1

            videos = post_data.get("videos", [])
            for v in videos:
                if isinstance(v, dict):
                    m_id = v.get("id") or ""
                    url = v.get("url") or ""
                    thumb = v.get("thumbnail") or ""
                    cursor.execute("""
                        INSERT INTO media (post_id, media_type, media_id, url, thumbnail)
                        VALUES (?, 'video', ?, ?, ?)
                    """, (post_id, m_id, url, thumb))
                    stats["media_added"] += 1

            # Case B: media array trong page_post
            generic_media = post_data.get("media", [])
            for m in generic_media:
                if isinstance(m, dict):
                    m_type = m.get("type", "photo")
                    m_id = m.get("id") or ""
                    url = m.get("url") or ""
                    saved_as = m.get("saved_as") or ""
                    cursor.execute("""
                        INSERT INTO media (post_id, media_type, media_id, url, saved_as)
                        VALUES (?, ?, ?, ?, ?)
                    """, (post_id, m_type, m_id, url, saved_as))
                    stats["media_added"] += 1
        else:
            # Post đã tồn tại -> Cập nhật comment_count, updated_at và cập nhật group_name nếu có
            if group_name:
                cursor.execute("""
                    UPDATE posts 
                    SET comment_count = ?, 
                        group_name = CASE WHEN group_name IS NULL OR TRIM(group_name) = '' THEN ? ELSE group_name END,
                        updated_at = datetime('now', 'localtime')
                    WHERE post_id = ?
                """, (comment_count, group_name, post_id))
            else:
                cursor.execute("""
                    UPDATE posts 
                    SET comment_count = ?, updated_at = datetime('now', 'localtime')
                    WHERE post_id = ?
                """, (comment_count, post_id))

        # 3. Xử lý comments và replies (check exist từng comment/reply theo ID)
        for comment in comments_data:
            if not isinstance(comment, dict):
                continue
            
            c_id = comment.get("comment_id")
            if not c_id:
                continue
            c_id = str(c_id)

            c_text = comment.get("text") or ""
            c_reactions = str(comment.get("reaction_count") or "0")

            c_exists = cursor.execute("SELECT 1 FROM comments WHERE comment_id = ?", (c_id,)).fetchone()
            if not c_exists:
                cursor.execute("""
                    INSERT INTO comments (comment_id, post_id, text, reaction_count)
                    VALUES (?, ?, ?, ?)
                """, (c_id, post_id, c_text, c_reactions))
                stats["comments_added"] += 1
            else:
                # Cập nhật reaction_count nếu có thay đổi
                cursor.execute("""
                    UPDATE comments 
                    SET reaction_count = ?, updated_at = datetime('now', 'localtime')
                    WHERE comment_id = ?
                """, (c_reactions, c_id))

            # Xử lý replies của comment này
            replies = comment.get("replies", [])
            for reply in replies:
                if not isinstance(reply, dict):
                    continue
                
                r_id = reply.get("reply_id")
                if not r_id:
                    continue
                r_id = str(r_id)

                r_text = reply.get("text") or ""
                r_reactions = str(reply.get("reaction_count") or "0")

                r_exists = cursor.execute("SELECT 1 FROM replies WHERE reply_id = ?", (r_id,)).fetchone()
                if not r_exists:
                    cursor.execute("""
                        INSERT INTO replies (reply_id, comment_id, post_id, text, reaction_count)
                        VALUES (?, ?, ?, ?, ?)
                    """, (r_id, c_id, post_id, r_text, r_reactions))
                    stats["replies_added"] += 1
                else:
                    cursor.execute("""
                        UPDATE replies 
                        SET reaction_count = ?, updated_at = datetime('now', 'localtime')
                        WHERE reply_id = ?
                    """, (r_reactions, r_id))

        conn.commit()

    return stats


def get_post_by_id(post_id: str, db_path: str = None) -> dict:
    """Lấy chi tiết một bài viết kèm media, comments và replies từ SQLite"""
    post_id = str(post_id)
    with get_connection(db_path) as conn:
        post_row = conn.execute("SELECT * FROM posts WHERE post_id = ?", (post_id,)).fetchone()
        if not post_row:
            return None

        result = dict(post_row)

        # Lấy media
        media_rows = conn.execute("SELECT * FROM media WHERE post_id = ?", (post_id,)).fetchall()
        result["photos"] = [dict(m) for m in media_rows if m["media_type"] == "photo"]
        result["videos"] = [dict(m) for m in media_rows if m["media_type"] == "video"]

        # Lấy comments và replies
        comments = []
        comment_rows = conn.execute("SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC", (post_id,)).fetchall()
        for c in comment_rows:
            c_dict = dict(c)
            reply_rows = conn.execute("SELECT * FROM replies WHERE comment_id = ? ORDER BY created_at ASC", (c["comment_id"],)).fetchall()
            c_dict["replies"] = [dict(r) for r in reply_rows]
            comments.append(c_dict)

        result["comments"] = comments
        return result


def save_media(post_id: str, media_items: list[dict], db_path: str = None) -> int:
    """Lưu danh sách media (ảnh/video) của bài viết vào bảng media SQLite"""
    if not post_id or not media_items:
        return 0
    post_id = str(post_id)
    added = 0
    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        for m in media_items:
            if not isinstance(m, dict):
                continue
            m_type = m.get("type", "photo")
            m_id = m.get("id") or ""
            url = m.get("url") or ""
            saved_as = m.get("saved_as") or ""
            w = m.get("width")
            h = m.get("height")
            thumb = m.get("thumbnail") or ""
            cursor.execute("""
                INSERT INTO media (post_id, media_type, media_id, url, saved_as, width, height, thumbnail)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, m_type, m_id, url, saved_as, w, h, thumb))
            added += 1
        conn.commit()
    return added


def get_db_stats(db_path: str = None) -> dict:
    """Lấy thống kê tổng số lượng bài viết, bình luận, phản hồi, media trong SQLite"""
    with get_connection(db_path) as conn:
        total_posts = conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        total_comments = conn.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
        total_replies = conn.execute("SELECT COUNT(*) FROM replies").fetchone()[0]
        total_media = conn.execute("SELECT COUNT(*) FROM media").fetchone()[0]
        return {
            "total_posts": total_posts,
            "total_comments": total_comments,
            "total_replies": total_replies,
            "total_media": total_media
        }


def build_posts_filter_clause(search_query: str = None, filters: dict = None) -> tuple[str, list]:
    """Xây dựng mệnh đề WHERE và danh sách parameters cho tìm kiếm và lọc theo cột"""
    clauses = []
    params = []
    if search_query and search_query.strip():
        sq = f"%{search_query.strip()}%"
        clauses.append("(p.message LIKE ? OR p.group_name LIKE ? OR p.page_name LIKE ? OR p.post_id LIKE ?)")
        params.extend([sq, sq, sq, sq])

    if filters:
        # Lọc theo Post ID
        if filters.get("post_id"):
            clauses.append("p.post_id LIKE ?")
            params.append(f"%{filters['post_id'].strip()}%")

        # Lọc theo Nhóm / Trang
        if filters.get("group_name"):
            g_val = f"%{filters['group_name'].strip()}%"
            clauses.append("(p.group_name LIKE ? OR p.page_name LIKE ?)")
            params.extend([g_val, g_val])

        # Lọc theo Nội dung bài viết
        if filters.get("message"):
            clauses.append("p.message LIKE ?")
            params.append(f"%{filters['message'].strip()}%")

        # Lọc theo Số bình luận tối thiểu (dựa trên comment_count hoặc số comments thực tế)
        if filters.get("min_comments") is not None:
            try:
                min_c = int(filters["min_comments"])
                if min_c > 0:
                    clauses.append("(p.comment_count >= ? OR (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) >= ?)")
                    params.extend([min_c, min_c])
            except (ValueError, TypeError):
                pass

        # Lọc theo Thời gian (ngày/tháng/năm hoặc giờ)
        if filters.get("time_str"):
            t_val = f"%{filters['time_str'].strip()}%"
            clauses.append("(p.created_at LIKE ? OR datetime(p.creation_time, 'unixepoch', 'localtime') LIKE ? OR strftime('%d/%m/%Y', p.creation_time, 'unixepoch', 'localtime') LIKE ?)")
            params.extend([t_val, t_val, t_val])

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params


def get_posts_count(search_query: str = None, filters: dict = None, db_path: str = None) -> int:
    """Đếm tổng số bài viết thỏa mãn điều kiện tìm kiếm và bộ lọc để phục vụ phân trang (Paging)"""
    where_sql, params = build_posts_filter_clause(search_query, filters)
    query = f"SELECT COUNT(*) FROM posts p {where_sql}"
    with get_connection(db_path) as conn:
        row = conn.execute(query, params).fetchone()
        return row[0] if row else 0


def get_all_posts_summary(limit: int = 50, offset: int = 0, search_query: str = None, filters: dict = None, db_path: str = None) -> list[dict]:
    """Lấy danh sách tóm tắt các bài viết cho GridView / Lịch sử, có hỗ trợ phân trang và lọc theo từng cột"""
    where_sql, params = build_posts_filter_clause(search_query, filters)
    query = f"""
        SELECT p.post_id, p.story_id, p.post_type, p.message, p.comment_count, p.group_name, p.page_name, p.permalink, p.creation_time, p.created_at, p.updated_at,
               (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) as actual_comments_count
        FROM posts p
        {where_sql}
        ORDER BY CASE WHEN p.creation_time IS NOT NULL THEN p.creation_time ELSE 0 END DESC, p.created_at DESC
        LIMIT ? OFFSET ?
    """
    full_params = params + [limit, offset]
    with get_connection(db_path) as conn:
        rows = conn.execute(query, full_params).fetchall()
        return [dict(r) for r in rows]


# ==============================================================================
# Distinct Group Names Helper (For Autocomplete Dropdown)
# ==============================================================================

def get_distinct_group_names(db_path: str = None) -> list[str]:
    """Lấy toàn bộ tên nhóm/trang không trùng lặp từ facebook_groups và posts"""
    names_set = set()
    with get_connection(db_path) as conn:
        # Từ bảng facebook_groups
        rows_fg = conn.execute("SELECT DISTINCT name FROM facebook_groups WHERE name IS NOT NULL AND TRIM(name) != ''").fetchall()
        for r in rows_fg:
            names_set.add(r["name"].strip())

        # Từ bảng posts (group_name và page_name)
        rows_p = conn.execute("SELECT DISTINCT group_name FROM posts WHERE group_name IS NOT NULL AND TRIM(group_name) != ''").fetchall()
        for r in rows_p:
            names_set.add(r["group_name"].strip())

        rows_page = conn.execute("SELECT DISTINCT page_name FROM posts WHERE page_name IS NOT NULL AND TRIM(page_name) != ''").fetchall()
        for r in rows_page:
            names_set.add(r["page_name"].strip())

    return sorted(list(names_set), key=lambda s: s.lower())


# ==============================================================================
# AI Analyses CRUD Helpers
# ==============================================================================

def save_ai_analysis(
    post_id: str,
    comment_id: str = None,
    group_name: str = "",
    matched_keyword: str = "",
    matched_source: str = "",
    model_used: str = "",
    should_notify: bool = False,
    is_seller: bool = None,
    target_name: str = "",
    price: str = "",
    actor_role: str = "",
    matched_snippet: str = "",
    reason: str = "",
    raw_response: str = "",
    device_name: str = None,
    seller_type: str = None,
    seller_snippet: str = None,
    telegram_sent: int = None,
    db_path: str = None
) -> int:
    """Lưu một bản ghi phân tích AI mới vào bảng ai_analyses (hỗ trợ comment_id, schema đa năng mới lẫn cũ và telegram_sent)"""
    if not post_id:
        return 0
    if is_seller is None:
        is_seller = should_notify
    if telegram_sent is None:
        telegram_sent = 0

    final_target = target_name or device_name or ""
    final_role = actor_role or seller_type or ""
    final_snippet = matched_snippet or seller_snippet or ""
    final_comment_id = str(comment_id).strip() if comment_id and str(comment_id).strip() else None

    with get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO ai_analyses (
                post_id, comment_id, group_name, matched_keyword, matched_source, model_used,
                should_notify, is_seller, device_name, price, seller_type,
                seller_snippet, reason, raw_response, telegram_sent, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))
        """, (
            str(post_id),
            final_comment_id,
            group_name or "",
            matched_keyword or "",
            matched_source or "",
            model_used or "",
            1 if should_notify else 0,
            1 if is_seller else 0,
            final_target,
            price or "",
            final_role,
            final_snippet,
            reason or "",
            raw_response or "",
            int(telegram_sent)
        ))
        conn.commit()
        return cursor.lastrowid


def ai_analysis_exists(post_id: str, comment_id: str = None, db_path: str = None) -> bool:
    """
    Kiểm tra xem bài viết hoặc bình luận/reply đã từng được AI phân tích hay chưa:
    - Nếu comment_id là None hoặc rỗng: kiểm tra post_id có bản ghi ai_analyses với (comment_id IS NULL hoặc comment_id = '').
    - Nếu comment_id có giá trị: kiểm tra cả post_id và comment_id.
    """
    if not post_id:
        return False
    clean_post_id = str(post_id).strip()
    clean_comment_id = str(comment_id).strip() if comment_id and str(comment_id).strip() else None

    with get_connection(db_path) as conn:
        if clean_comment_id:
            row = conn.execute(
                "SELECT 1 FROM ai_analyses WHERE post_id = ? AND comment_id = ? LIMIT 1",
                (clean_post_id, clean_comment_id)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT 1 FROM ai_analyses WHERE post_id = ? AND (comment_id IS NULL OR comment_id = '') LIMIT 1",
                (clean_post_id,)
            ).fetchone()
        return bool(row)


def build_ai_analyses_filter_clause(search_query: str = None, filters: dict = None) -> tuple[str, list]:
    """Xây dựng mệnh đề WHERE và parameters cho tìm kiếm lịch sử phân tích AI"""
    clauses = []
    params = []

    # Tìm kiếm chung
    if search_query and search_query.strip():
        sq = f"%{search_query.strip()}%"
        clauses.append("(a.post_id LIKE ? OR a.comment_id LIKE ? OR a.group_name LIKE ? OR a.matched_keyword LIKE ? OR a.device_name LIKE ? OR a.reason LIKE ? OR a.seller_snippet LIKE ?)")
        params.extend([sq, sq, sq, sq, sq, sq, sq])

    if filters:
        # Lọc should_notify (mặc định 1 trong tab Lịch sử phân tích)
        if filters.get("should_notify") is not None:
            clauses.append("a.should_notify = ?")
            params.append(1 if filters["should_notify"] else 0)

        # Lọc theo Post ID
        if filters.get("post_id"):
            clauses.append("a.post_id LIKE ?")
            params.append(f"%{filters['post_id'].strip()}%")

        # Lọc theo Comment ID
        if filters.get("comment_id"):
            clauses.append("a.comment_id LIKE ?")
            params.append(f"%{filters['comment_id'].strip()}%")

        # Lọc theo Nhóm/Trang
        if filters.get("group_name"):
            clauses.append("a.group_name LIKE ?")
            params.append(f"%{filters['group_name'].strip()}%")

        # Lọc theo Từ khóa
        if filters.get("matched_keyword"):
            clauses.append("a.matched_keyword LIKE ?")
            params.append(f"%{filters['matched_keyword'].strip()}%")

        # Lọc theo Mục tiêu / Thiết bị / Sản phẩm
        filter_target = filters.get("target_name") or filters.get("device_name")
        if filter_target:
            clauses.append("a.device_name LIKE ?")
            params.append(f"%{filter_target.strip()}%")

        # Lọc theo Model
        if filters.get("model_used"):
            clauses.append("a.model_used LIKE ?")
            params.append(f"%{filters['model_used'].strip()}%")

        # Lọc theo Trạng thái Telegram
        if filters.get("telegram_sent") is not None:
            clauses.append("a.telegram_sent = ?")
            params.append(int(filters["telegram_sent"]))

        # Lọc theo Thời gian
        if filters.get("time_str"):
            clauses.append("a.created_at LIKE ?")
            params.append(f"%{filters['time_str'].strip()}%")

    where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where_sql, params


def get_ai_analyses_count(search_query: str = None, filters: dict = None, db_path: str = None) -> int:
    """Đếm tổng số bản ghi phân tích AI phục vụ phân trang"""
    where_sql, params = build_ai_analyses_filter_clause(search_query, filters)
    query = f"SELECT COUNT(*) FROM ai_analyses a {where_sql}"
    with get_connection(db_path) as conn:
        row = conn.execute(query, params).fetchone()
        return row[0] if row else 0


def get_all_ai_analyses(limit: int = 50, offset: int = 0, search_query: str = None, filters: dict = None, db_path: str = None) -> list[dict]:
    """Lấy danh sách các bản ghi phân tích AI phân trang (kèm permalink, message từ posts và telegram_sent)"""
    where_sql, params = build_ai_analyses_filter_clause(search_query, filters)
    query = f"""
        SELECT a.id, a.post_id, a.comment_id, a.group_name, a.matched_keyword, a.matched_source, a.model_used,
               a.should_notify, a.is_seller, a.device_name, a.price, a.seller_type,
               a.seller_snippet, a.reason, a.raw_response, a.telegram_sent, a.created_at,
               p.message as post_message, p.permalink, p.comment_count
        FROM ai_analyses a
        LEFT JOIN posts p ON a.post_id = p.post_id
        {where_sql}
        ORDER BY a.id DESC
        LIMIT ? OFFSET ?
    """
    full_params = params + [limit, offset]
    with get_connection(db_path) as conn:
        rows = conn.execute(query, full_params).fetchall()
        res = []
        for r in rows:
            d = dict(r)
            d["target_name"] = d.get("device_name") or ""
            d["actor_role"] = d.get("seller_type") or ""
            d["matched_snippet"] = d.get("seller_snippet") or ""
            res.append(d)
        return res


def get_ai_analysis_by_post_id(post_id: str, comment_id: str = None, db_path: str = None) -> dict:
    """Lấy bản ghi phân tích AI mới nhất của một bài viết / bình luận cụ thể"""
    if not post_id:
        return None
    clean_post_id = str(post_id).strip()
    clean_comment_id = str(comment_id).strip() if comment_id and str(comment_id).strip() else None

    with get_connection(db_path) as conn:
        if clean_comment_id is not None:
            row = conn.execute("""
                SELECT * FROM ai_analyses WHERE post_id = ? AND comment_id = ? ORDER BY id DESC LIMIT 1
            """, (clean_post_id, clean_comment_id)).fetchone()
        else:
            row = conn.execute("""
                SELECT * FROM ai_analyses WHERE post_id = ? ORDER BY id DESC LIMIT 1
            """, (clean_post_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["target_name"] = d.get("device_name") or ""
        d["actor_role"] = d.get("seller_type") or ""
        d["matched_snippet"] = d.get("seller_snippet") or ""
        return d



def delete_ai_analysis_by_id(analysis_id: int, db_path: str = None) -> bool:
    """Xóa một bản ghi phân tích AI theo ID"""
    if not analysis_id:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM ai_analyses WHERE id = ?", (int(analysis_id),))
        return cursor.rowcount > 0


def delete_ai_analysis_by_post_id(post_id: str, db_path: str = None) -> bool:
    """Xóa tất cả bản ghi phân tích AI của một bài viết cụ thể"""
    if not post_id:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM ai_analyses WHERE post_id = ?", (str(post_id),))
        return cursor.rowcount > 0


def delete_post_by_id(post_id: str, db_path: str = None) -> bool:
    """Xóa một bài viết khỏi SQLite (tự động xóa cascade comments, replies, media, ai_analyses)"""
    if not post_id:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM posts WHERE post_id = ?", (str(post_id),))
        return cursor.rowcount > 0


def delete_posts_by_ids(post_ids: list[str], db_path: str = None) -> int:
    """Xóa danh sách bài viết theo danh sách post_ids (tự động cascade)"""
    if not post_ids:
        return 0
    clean_ids = [str(pid).strip() for pid in post_ids if str(pid).strip()]
    if not clean_ids:
        return 0
    placeholders = ",".join(["?"] * len(clean_ids))
    with get_connection(db_path) as conn:
        cursor = conn.execute(f"DELETE FROM posts WHERE post_id IN ({placeholders})", clean_ids)
        return cursor.rowcount


def delete_all_posts(db_path: str = None) -> int:
    """Xóa trắng toàn bộ bài viết và dữ liệu liên đới trong database"""
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM posts")
        return cursor.rowcount


def delete_ai_analyses_by_ids(analysis_ids: list[int], db_path: str = None) -> int:
    """Xóa danh sách bản ghi phân tích AI theo danh sách ID"""
    if not analysis_ids:
        return 0
    clean_ids = [int(aid) for aid in analysis_ids if aid is not None]
    if not clean_ids:
        return 0
    placeholders = ",".join(["?"] * len(clean_ids))
    with get_connection(db_path) as conn:
        cursor = conn.execute(f"DELETE FROM ai_analyses WHERE id IN ({placeholders})", clean_ids)
        return cursor.rowcount


def delete_all_ai_analyses(db_path: str = None) -> int:
    """Xóa trắng toàn bộ bản ghi phân tích AI trong database"""
    with get_connection(db_path) as conn:
        cursor = conn.execute("DELETE FROM ai_analyses")
        return cursor.rowcount


def get_posts_within_last_24h(db_path: str = None) -> list[dict]:
    """
    Lấy danh sách các bài viết có thời gian đăng trong vòng 24 giờ qua:
    - Nếu có creation_time (Unix timestamp): creation_time >= (hiện tại - 86400)
    - Nếu không có creation_time: created_at >= datetime('now', '-24 hours', 'localtime')
    """
    import time
    cutoff_timestamp = int(time.time()) - (24 * 3600)
    query = """
        SELECT p.post_id, p.story_id, p.post_type, p.message, p.comment_count, p.group_name, p.page_name, p.permalink, p.creation_time, p.created_at, p.updated_at,
               (SELECT COUNT(*) FROM comments c WHERE c.post_id = p.post_id) as actual_comments_count
        FROM posts p
        WHERE (p.creation_time IS NOT NULL AND p.creation_time >= ?)
           OR (p.creation_time IS NULL AND p.created_at >= datetime('now', '-24 hours', 'localtime'))
        ORDER BY CASE WHEN p.creation_time IS NOT NULL THEN p.creation_time ELSE 0 END DESC, p.created_at DESC
    """
    with get_connection(db_path) as conn:
        rows = conn.execute(query, (cutoff_timestamp,)).fetchall()
        return [dict(r) for r in rows]


# ==============================================================================
# Logging Helpers (Logs Table & Auto-cleanup > 1 day)
# ==============================================================================

def add_log(message: str, level: str = "INFO", module: str = "APP", db_path: str = None) -> int:
    """Ghi một bản ghi log vào bảng logs trong SQLite"""
    if not message:
        return 0
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO logs (level, message, module, created_at)
                VALUES (?, ?, ?, datetime('now', 'localtime'))
            """, (str(level).upper(), str(message), str(module)))
            conn.commit()
            return cursor.lastrowid
    except Exception:
        return 0


def get_logs(limit: int = 200, offset: int = 0, level: str = None, module: str = None, db_path: str = None) -> list[dict]:
    """Lấy danh sách log từ bảng logs"""
    try:
        clauses = []
        params = []
        if level:
            clauses.append("level = ?")
            params.append(level.upper())
        if module:
            clauses.append("module = ?")
            params.append(module)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        query = f"SELECT id, level, message, module, created_at FROM logs {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        with get_connection(db_path) as conn:
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]
    except Exception:
        return []


def cleanup_old_logs(days: int = 1, db_path: str = None) -> int:
    """
    Xóa các bản ghi log cũ hơn N ngày (mặc định 1 ngày = 24 giờ).
    Được tự động gọi khi ứng dụng khởi chạy.
    """
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM logs WHERE created_at < datetime('now', '-{int(days)} days', 'localtime')")
            deleted = cursor.rowcount
            conn.commit()
            return deleted
    except Exception:
        return 0


# ==============================================================================
# Telegram Dispatcher Helpers (Pending Queue & Status Update)
# ==============================================================================

def get_pending_telegram_analyses(limit: int = 10, db_path: str = None) -> list[dict]:
    """
    Lấy danh sách các bài viết/phân tích AI đã xác nhận should_notify = 1 nhưng CHƯA gửi Telegram
    (telegram_sent = 0 hoặc NULL) kèm thông tin bài viết để dispatcher gửi thông báo.
    """
    try:
        query = """
            SELECT a.id, a.post_id, a.group_name, a.matched_keyword, a.matched_source,
                   a.model_used, a.should_notify, a.is_seller, a.device_name, a.price,
                   a.seller_type, a.seller_snippet, a.reason, a.raw_response, a.telegram_sent, a.created_at,
                   p.message as post_message, p.permalink, p.group_name as post_group_name, p.page_name as post_page_name
            FROM ai_analyses a
            LEFT JOIN posts p ON a.post_id = p.post_id
            WHERE a.should_notify = 1 AND (a.telegram_sent = 0 OR a.telegram_sent IS NULL)
            ORDER BY a.id ASC
            LIMIT ?
        """
        with get_connection(db_path) as conn:
            rows = conn.execute(query, (limit,)).fetchall()
            res = []
            for r in rows:
                d = dict(r)
                d["target_name"] = d.get("device_name") or ""
                d["actor_role"] = d.get("seller_type") or ""
                d["matched_snippet"] = d.get("seller_snippet") or ""
                res.append(d)
            return res
    except Exception:
        return []


def mark_telegram_analysis_sent(analysis_id: int, status: int = 1, db_path: str = None) -> bool:
    """
    Cập nhật trạng thái gửi Telegram cho bản ghi phân tích AI (1 = Đã gửi, 0 = Chưa gửi, -1 = Lỗi).
    """
    if not analysis_id:
        return False
    try:
        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE ai_analyses SET telegram_sent = ? WHERE id = ?", (int(status), int(analysis_id)))
            conn.commit()
            return cursor.rowcount > 0
    except Exception:
        return False


# ==============================================================================
# Diagnostic Export (.diagnose file without settings table)
# ==============================================================================

def export_diagnostics_sql(output_file_path: str, db_path: str = None) -> tuple[bool, str, int]:
    """
    Xuất toàn bộ cấu trúc và dữ liệu SQLite ra tệp SQL dump với đuôi .diagnose,
    LOẠI TRỪ HOÀN TOÀN bảng 'settings' để bảo mật thông tin tài khoản/API key của người dùng.
    Trả về: (thành_công: bool, thông_điệp: str, tổng_bản_ghi_đã_xuất: int)
    """
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_file_path)), exist_ok=True)
        total_records = 0
        dump_lines = []
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        dump_lines.append("-- ============================================================================")
        dump_lines.append(f"-- Facebook Notification Diagnostic Dump (.diagnose)")
        dump_lines.append(f"-- Generated At: {now_str}")
        dump_lines.append(f"-- Note: 'settings' table is strictly excluded for security & privacy.")
        dump_lines.append("-- ============================================================================\n")
        dump_lines.append("PRAGMA foreign_keys = OFF;\n")

        with get_connection(db_path) as conn:
            cursor = conn.cursor()
            
            # Lấy danh sách tất cả các bảng (loại trừ settings và sqlite_*)
            tables_query = """
                SELECT name, sql FROM sqlite_master 
                WHERE type = 'table' AND name != 'settings' AND name NOT LIKE 'sqlite_%'
                ORDER BY name ASC
            """
            tables = cursor.execute(tables_query).fetchall()

            for t_row in tables:
                t_name = t_row["name"]
                t_sql = t_row["sql"]
                if not t_sql:
                    continue

                dump_lines.append(f"\n-- ----------------------------------------------------------------------------")
                dump_lines.append(f"-- Table structure for `{t_name}`")
                dump_lines.append(f"-- ----------------------------------------------------------------------------")
                dump_lines.append(f"DROP TABLE IF EXISTS `{t_name}`;")
                dump_lines.append(f"{t_sql};\n")

                # Lấy dữ liệu của bảng
                rows = cursor.execute(f"SELECT * FROM `{t_name}`").fetchall()
                if rows:
                    dump_lines.append(f"-- Dumping data for table `{t_name}` ({len(rows)} records)")
                    col_names = [f"`{col}`" for col in rows[0].keys()]
                    cols_str = ", ".join(col_names)

                    for r in rows:
                        val_list = []
                        for v in tuple(r):
                            if v is None:
                                val_list.append("NULL")
                            elif isinstance(v, (int, float)):
                                val_list.append(str(v))
                            else:
                                val_str = str(v).replace("'", "''")
                                val_list.append(f"'{val_str}'")
                        vals_str = ", ".join(val_list)
                        dump_lines.append(f"INSERT INTO `{t_name}` ({cols_str}) VALUES ({vals_str});")
                        total_records += 1
                    dump_lines.append("")

            # Lấy indexes (loại trừ indexes trên bảng settings và sqlite_*)
            indexes_query = """
                SELECT name, sql, tbl_name FROM sqlite_master 
                WHERE type = 'index' AND tbl_name != 'settings' AND sql IS NOT NULL AND name NOT LIKE 'sqlite_%'
                ORDER BY name ASC
            """
            indexes = cursor.execute(indexes_query).fetchall()
            if indexes:
                dump_lines.append(f"\n-- ----------------------------------------------------------------------------")
                dump_lines.append(f"-- Indexes for tables")
                dump_lines.append(f"-- ----------------------------------------------------------------------------")
                for i_row in indexes:
                    i_sql = i_row["sql"]
                    if i_sql:
                        dump_lines.append(f"{i_sql};")

            dump_lines.append("\nPRAGMA foreign_keys = ON;\n")

        with open(output_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(dump_lines))

        file_size_kb = os.path.getsize(output_file_path) / 1024
        msg = f"Đã xuất chẩn đoán thành công: {total_records} bản ghi ({file_size_kb:.1f} KB) tại '{output_file_path}'"
        return True, msg, total_records

    except Exception as e:
        err_msg = f"Lỗi xuất chẩn đoán: {str(e)}"
        return False, err_msg, 0


# ==============================================================================
# AI Queue Helpers for Background Dispatcher
# ==============================================================================

def mark_post_ai_pending(post_id: str, matched_keyword: str = "", matched_source: str = "", matched_comment_id: str = None, db_path: str = None) -> bool:
    """Đưa bài viết vào hàng đợi phân tích AI (ai_status = 1)"""
    if not post_id:
        return False
    clean_comment_id = str(matched_comment_id).strip() if matched_comment_id and str(matched_comment_id).strip() else ""
    with get_connection(db_path) as conn:
        cursor = conn.execute("""
            UPDATE posts 
            SET ai_status = 1, 
                matched_keyword = ?, 
                matched_source = ?,
                matched_comment_id = ?,
                updated_at = datetime('now', 'localtime')
            WHERE post_id = ?
        """, (matched_keyword or "", matched_source or "", clean_comment_id, str(post_id)))
        return cursor.rowcount > 0


def mark_post_ai_status(post_id: str, status: int, db_path: str = None) -> bool:
    """Cập nhật trạng thái phân tích AI của bài viết (0: bình thường, 1: chờ phân tích, 2: đã xong, -1: lỗi, 3: đang chạy)"""
    if not post_id:
        return False
    with get_connection(db_path) as conn:
        cursor = conn.execute("""
            UPDATE posts 
            SET ai_status = ?, 
                updated_at = datetime('now', 'localtime')
            WHERE post_id = ?
        """, (int(status), str(post_id)))
        return cursor.rowcount > 0


def get_pending_ai_posts(limit: int = 5, db_path: str = None) -> list[dict]:
    """Lấy danh sách các bài viết đang chờ phân tích AI (ai_status = 1)"""
    with get_connection(db_path) as conn:
        rows = conn.execute("""
            SELECT post_id, group_name, page_name, message, permalink, comment_count, creation_time, post_type, matched_keyword, matched_source, matched_comment_id
            FROM posts 
            WHERE ai_status = 1
            ORDER BY updated_at ASC
            LIMIT ?
        """, (int(limit),)).fetchall()
        return [dict(r) for r in rows]


def get_post_comments_with_replies(post_id: str, db_path: str = None) -> list[dict]:
    """Lấy toàn bộ bình luận và reply của một bài viết từ SQLite"""
    if not post_id:
        return []
    post_id = str(post_id)
    with get_connection(db_path) as conn:
        comments = []
        comment_rows = conn.execute("SELECT * FROM comments WHERE post_id = ? ORDER BY created_at ASC", (post_id,)).fetchall()
        for c in comment_rows:
            c_dict = dict(c)
            reply_rows = conn.execute("SELECT * FROM replies WHERE comment_id = ? ORDER BY created_at ASC", (c["comment_id"],)).fetchall()
            c_dict["replies"] = [dict(r) for r in reply_rows]
            comments.append(c_dict)
        return comments






