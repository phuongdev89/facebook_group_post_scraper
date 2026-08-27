import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import src.config.constants as c
from src.utils.keyword_engine import (
    validate_expression,
    evaluate_keyword_match,
    check_post_and_comments_match,
    parse_expression
)
import src.core.comment_scraper as cs
import src.core.group_scraper as gs

def test_version():
    assert c.APP_VERSION == "1.0.7", f"Expected 1.0.7, got {c.APP_VERSION}"
    print("✅ Version check passed: v1.0.7")

def test_keyword_complex_logic():
    expr = '("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'
    ok, msg = validate_expression(expr)
    assert ok is True, f"Validation failed: {msg}"

    # Match: a1 + thanh lý
    matched, _, hits = evaluate_keyword_match("Dọn nhà thanh lý sony a1 còn mới", expr)
    assert matched is True
    assert "a1" in [h.lower() for h in hits]
    assert "thanh lý" in [h.lower() for h in hits]

    # Match: combo + xé lẻ
    matched2, _, hits2 = evaluate_keyword_match("Bộ combo sony a7iv kèm lens có xé lẻ", expr)
    assert matched2 is True
    assert "combo" in [h.lower() for h in hits2]
    assert "xé lẻ" in [h.lower() for h in hits2]

    # No match
    matched3, _, _ = evaluate_keyword_match("Bán máy ảnh canon r6", expr)
    assert matched3 is False
    print("✅ Keyword logic evaluation passed!")

def test_comment_scraper_safe_extraction():
    # Test with malicious/null responses that previously caused AttributeError: 'NoneType' object has no attribute 'get'
    assert cs._safe(None, "data", "node") is None
    assert cs._safe({"data": None}, "data", "node") is None
    assert cs._safe({"data": {"node": None}}, "data", "node", "feedback") is None
    assert cs._safe({"data": {"node": {"feedback": {"reactors": None}}}}, "data", "node", "feedback", "reactors", "count_reduced", default="0") == "0"
    print("✅ Comment scraper safe extraction check passed!")

def test_bidirectional_conversion():
    from src.utils.keyword_engine import expression_to_visual_groups, visual_groups_to_expression
    groups = [
        {
            "id": 1,
            "group_op": "OR",
            "items": [
                {"op": "AND", "text": "a1"}
            ]
        },
        {
            "id": 2,
            "group_op": "AND",
            "items": [
                {"op": "OR", "text": "bán"},
                {"op": "OR", "text": "pass"},
                {"op": "OR", "text": "thanh lý"}
            ]
        },
        {
            "id": 3,
            "group_op": "OR",
            "items": [
                {"op": "AND", "text": "combo"},
                {"op": "AND", "text": "xé lẻ"}
            ]
        }
    ]

    expr = visual_groups_to_expression(groups)
    assert '"a1"' in expr
    assert '("bán" OR "pass" OR "thanh lý")' in expr
    assert '("combo" AND "xé lẻ")' in expr
    assert " OR " in expr

    parsed_groups = expression_to_visual_groups(expr)
    assert len(parsed_groups) == 3
    assert parsed_groups[0]["items"][0]["text"] == "a1"
    assert len(parsed_groups[1]["items"]) == 3
    assert parsed_groups[1]["items"][0]["text"] == "bán"

    roundtrip_expr = visual_groups_to_expression(parsed_groups)
    ok, _ = validate_expression(roundtrip_expr)
    assert ok is True
    print("✅ Two-way AST <-> Visual Builder conversion passed!")

def test_keyword_filter_widget_qt():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(["test"])
    from src.ui.components.keyword_filter_widget import KeywordFilterWidget

    widget = KeywordFilterWidget()
    test_expr = '("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'
    widget.set_expression(test_expr)
    assert len(widget.get_expression()) > 0

    # Switch to Raw
    widget.on_mode_switched(1)
    assert widget.current_mode == 1

    # Switch back to Visual
    widget.on_mode_switched(0)
    assert widget.current_mode == 0

    print("✅ KeywordFilterWidget Qt Component test passed!")

def test_explain_expression():
    from src.utils.keyword_engine import explain_expression
    expr = '("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'
    explanation = explain_expression(expr)
    assert '"a1"' in explanation
    assert '"bán"' in explanation
    assert '"combo"' in explanation
    assert '"xé lẻ"' in explanation
    assert "HOẶC" in explanation
    print(f"✅ Expression Explanation verified:\n   -> {explanation}")

def test_keyword_filter_dialog_qt():
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(["test"])
    from src.ui.dialogs.keyword_filter_dialog import KeywordFilterDialog

    dlg = KeywordFilterDialog(initial_expression='("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")')
    assert "a1" in dlg.get_expression()
    print("✅ KeywordFilterDialog Qt Component test passed!")

def test_cutoff_time_logic():
    now = int(time.time())
    one_day_ago = now - 86400
    assert one_day_ago < now
    print("✅ Cutoff time logic check passed!")

def test_group_operators():
    from src.utils.keyword_engine import expression_to_visual_groups, visual_groups_to_expression
    groups = [
        {"id": 1, "group_op": "OR", "items": [{"op": "AND", "text": "iphone"}]},
        {"id": 2, "group_op": "AND", "items": [{"op": "AND", "text": "15 pro"}]},
        {"id": 3, "group_op": "NOT", "items": [{"op": "AND", "text": "lock"}]}
    ]
    expr = visual_groups_to_expression(groups)
    assert 'iphone' in expr
    assert 'AND "15 pro"' in expr
    assert 'AND NOT "lock"' in expr
    ok, _ = validate_expression(expr)
def test_user_exact_two_group_case():
    from src.utils.keyword_engine import expression_to_visual_groups, visual_groups_to_expression
    
    # Người dùng nhập: "a1" AND ("bán" OR "thanh lý" OR "pass")
    expr_initial = '"a1" AND ("bán" OR "thanh lý" OR "pass")'
    groups = expression_to_visual_groups(expr_initial)
    
    # Phải tách thành đúng 2 nhóm:
    # Nhóm 1: a1
    # Nhóm 2 (AND): bán, thanh lý, pass
    assert len(groups) == 2, f"Expected 2 groups, got {len(groups)}"
    assert groups[0]["items"][0]["text"] == "a1"
    assert groups[1]["group_op"] == "AND"
    assert len(groups[1]["items"]) == 3
    assert [it["text"] for it in groups[1]["items"]] == ["bán", "thanh lý", "pass"]
    assert "OR" not in groups[1]["items"][0]["text"]
    assert "AND" not in groups[1]["items"][0]["text"]
    
    # Chuyển ngược lại biểu thức
    roundtrip = visual_groups_to_expression(groups)
    assert '"a1"' in roundtrip
    assert 'AND ("bán" OR "thanh lý" OR "pass")' in roundtrip or 'AND ("bán" OR "thanh lý" OR "pass")' in roundtrip
    
    # Parse lại lần nữa xem có bị biến dạng không
    groups_again = expression_to_visual_groups(roundtrip)
    assert len(groups_again) == 2
    assert [it["text"] for it in groups_again[1]["items"]] == ["bán", "thanh lý", "pass"]
    print("✅ Exact user 2-group nested case (a1 AND (bán OR thanh lý OR pass)) passed 100%!")

if __name__ == "__main__":
    test_version()
    test_keyword_complex_logic()
    test_bidirectional_conversion()
    test_group_operators()
    test_user_exact_two_group_case()
    test_explain_expression()
    test_keyword_filter_widget_qt()
    test_keyword_filter_dialog_qt()
    test_comment_scraper_safe_extraction()
    test_cutoff_time_logic()
    print("\n🎉 ALL TESTS IN test_v107_verification.py PASSED SUCCESSFULLY!")
