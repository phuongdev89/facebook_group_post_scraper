import time
import pytest
from unittest.mock import MagicMock, patch
from src.database.repository import (
    init_db,
    save_or_update_post,
    save_ai_analysis,
    get_post_by_id,
    get_all_ai_analyses,
    delete_post_by_id,
    delete_posts_by_ids,
    delete_all_posts,
    delete_ai_analyses_by_ids,
    delete_all_ai_analyses,
    get_posts_within_last_24h,
    get_connection
)
from src.ui.workers.comment_update_worker import CommentUpdateWorker


@pytest.fixture
def temp_db(tmp_path):
    db_file = str(tmp_path / "test_delete.sqlite")
    init_db(db_file)
    return db_file


def test_delete_single_post(temp_db):
    post_id = "post_100"
    post_data = {"post_id": post_id, "message": "Test Post 100", "group_name": "Group A"}
    comments = [
        {"comment_id": "c_1", "text": "Comment 1", "replies": [{"reply_id": "r_1", "text": "Reply 1"}]}
    ]
    save_or_update_post("group_post", post_id, post_data, comments, db_path=temp_db)
    save_ai_analysis(
        post_id=post_id,
        group_name="Group A",
        matched_keyword="test",
        matched_source="post",
        model_used="gpt-4o",
        should_notify=True,
        db_path=temp_db
    )

    # Verify exists
    assert get_post_by_id(post_id, db_path=temp_db) is not None
    with get_connection(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM comments WHERE post_id = ?", (post_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM replies WHERE post_id = ?", (post_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM ai_analyses WHERE post_id = ?", (post_id,)).fetchone()[0] == 1

    # Delete single post
    ok = delete_post_by_id(post_id, db_path=temp_db)
    assert ok is True
    assert get_post_by_id(post_id, db_path=temp_db) is None

    # Check CASCADE
    with get_connection(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM comments WHERE post_id = ?", (post_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM replies WHERE post_id = ?", (post_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM ai_analyses WHERE post_id = ?", (post_id,)).fetchone()[0] == 0


def test_delete_posts_by_ids(temp_db):
    for i in range(1, 6):
        pid = f"post_{i}"
        save_or_update_post("group_post", pid, {"post_id": pid, "message": f"Msg {i}"}, db_path=temp_db)

    # Delete post_1, post_3, post_5
    deleted = delete_posts_by_ids(["post_1", "post_3", "post_5"], db_path=temp_db)
    assert deleted == 3

    assert get_post_by_id("post_1", db_path=temp_db) is None
    assert get_post_by_id("post_2", db_path=temp_db) is not None
    assert get_post_by_id("post_3", db_path=temp_db) is None
    assert get_post_by_id("post_4", db_path=temp_db) is not None
    assert get_post_by_id("post_5", db_path=temp_db) is None


def test_delete_all_posts(temp_db):
    for i in range(1, 4):
        pid = f"post_{i}"
        save_or_update_post("group_post", pid, {"post_id": pid, "message": f"Msg {i}"}, db_path=temp_db)

    deleted = delete_all_posts(db_path=temp_db)
    assert deleted == 3

    with get_connection(temp_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0


def test_delete_ai_analyses_by_ids_and_all(temp_db):
    save_or_update_post("group_post", "p1", {"post_id": "p1"}, db_path=temp_db)
    save_or_update_post("group_post", "p2", {"post_id": "p2"}, db_path=temp_db)
    save_or_update_post("group_post", "p3", {"post_id": "p3"}, db_path=temp_db)

    a1 = save_ai_analysis(post_id="p1", group_name="G1", matched_keyword="k1", db_path=temp_db)
    a2 = save_ai_analysis(post_id="p2", group_name="G2", matched_keyword="k2", db_path=temp_db)
    a3 = save_ai_analysis(post_id="p3", group_name="G3", matched_keyword="k3", db_path=temp_db)

    # Delete a1 and a2
    deleted = delete_ai_analyses_by_ids([a1, a2], db_path=temp_db)
    assert deleted == 2

    analyses = get_all_ai_analyses(db_path=temp_db)
    assert len(analyses) == 1
    assert analyses[0]["id"] == a3

    # Delete all
    del_all = delete_all_ai_analyses(db_path=temp_db)
    assert del_all == 1
    assert len(get_all_ai_analyses(db_path=temp_db)) == 0


def test_get_posts_within_last_24h(temp_db):
    now = int(time.time())
    
    # 1. Bài mới: 2 tiếng trước
    recent_id = "post_recent"
    save_or_update_post(
        "group_post",
        recent_id,
        {"post_id": recent_id, "message": "Recent post", "creation_time": now - 7200},
        db_path=temp_db
    )

    # 2. Bài cũ: 48 tiếng trước
    old_id = "post_old"
    save_or_update_post(
        "group_post",
        old_id,
        {"post_id": old_id, "message": "Old post", "creation_time": now - 172800},
        db_path=temp_db
    )

    # 3. Bài không có creation_time nhưng vừa insert
    no_time_id = "post_no_time"
    save_or_update_post(
        "group_post",
        no_time_id,
        {"post_id": no_time_id, "message": "No creation_time post"},
        db_path=temp_db
    )

    posts_24h = get_posts_within_last_24h(db_path=temp_db)
    found_ids = [p["post_id"] for p in posts_24h]

    assert recent_id in found_ids
    assert no_time_id in found_ids
    assert old_id not in found_ids


def test_comment_update_worker_keyword_check():
    worker = CommentUpdateWorker(
        post_ids=["p1"],
        keywords=["máy ảnh", "sony"]
    )

    # 1. Match in post text
    post_data = {"post_id": "p1", "message": "Cần bán máy ảnh Sony A7"}
    comments = [{"text": "Bao nhiêu vậy shop"}]
    matched, kw, src, cid = worker.check_keyword_match(post_data, comments, worker.keywords)
    assert matched is True
    assert kw in ["máy ảnh", "sony"]
    assert src == "Bài viết"
    assert cid is None

    # 2. Match in comment text
    post_data2 = {"post_id": "p2", "message": "Xin chào cả nhà"}
    comments2 = [{"comment_id": "c_202", "text": "Mình có máy ảnh cần bán nè"}]
    matched2, kw2, src2, cid2 = worker.check_keyword_match(post_data2, comments2, worker.keywords)
    assert matched2 is True
    assert kw2 == "máy ảnh"
    assert src2 == "Bình luận"
    assert cid2 == "c_202"

    # 3. No match
    post_data3 = {"post_id": "p3", "message": "Hôm nay trời đẹp"}
    comments3 = [{"text": "Chào bạn"}]
    matched3, kw3, src3, cid3 = worker.check_keyword_match(post_data3, comments3, worker.keywords)
    assert matched3 is False
    assert cid3 is None


def test_comment_update_worker_post_status_signal(temp_db):
    save_or_update_post("group_post", "p_signal_1", {"post_id": "p_signal_1", "message": "Test signal"}, db_path=temp_db)
    
    worker = CommentUpdateWorker(
        post_ids=["p_signal_1"],
        keywords=[]
    )

    signals_emitted = []
    worker.post_status_signal.connect(lambda pid, status, count: signals_emitted.append((pid, status, count)))

    with patch("src.ui.workers.comment_update_worker.fetch_comments") as mock_fetch, \
         patch("src.ui.workers.comment_update_worker.get_post_by_id") as mock_get_post, \
         patch("src.ui.workers.comment_update_worker.save_or_update_post"):
        mock_fetch.return_value = ([{"comment_id": "c1", "text": "Hi"}], None)
        mock_get_post.return_value = {"post_id": "p_signal_1", "message": "Test signal"}
        worker.run()

    assert ("p_signal_1", "updating", 0) in signals_emitted
    assert ("p_signal_1", "done", 1) in signals_emitted
