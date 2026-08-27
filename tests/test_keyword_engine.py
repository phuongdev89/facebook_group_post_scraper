import pytest
from src.utils.keyword_engine import (
    tokenize,
    validate_expression,
    parse_expression,
    evaluate_keyword_match,
    check_post_and_comments_match
)

def test_syntax_validation():
    ok, msg = validate_expression('("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")')
    assert ok is True

    ok, msg = validate_expression('(iphone OR samsung) AND NOT lock')
    assert ok is True

    # Thiếu dấu ngoặc đóng
    ok, msg = validate_expression('("a1" AND ("bán" OR "pass")')
    assert ok is False


def test_user_requested_example():
    expr = '("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'
    
    # 1. Match case 1: a1 + bán
    text1 = "Mình cần bán chiếc máy Sony A1 đẹp 99%"
    matched, summary, hit_terms = evaluate_keyword_match(text1, expr)
    assert matched is True
    assert "a1" in [t.lower() for t in hit_terms]
    assert "bán" in [t.lower() for t in hit_terms]

    # 2. Match case 2: a1 + pass
    text2 = "Pass lại sony a1 giá yêu thương"
    matched, summary, hit_terms = evaluate_keyword_match(text2, expr)
    assert matched is True

    # 3. Match case 3: combo + xé lẻ
    text3 = "Bán cả combo có xé lẻ cho anh em cần"
    matched, summary, hit_terms = evaluate_keyword_match(text3, expr)
    assert matched is True
    assert "combo" in [t.lower() for t in hit_terms]
    assert "xé lẻ" in [t.lower() for t in hit_terms]

    # 4. No match: a1 without bán/pass/thanh lý, no combo xé lẻ
    text4 = "Sony a1 chụp ảnh có đẹp không mọi người?"
    matched, summary, hit_terms = evaluate_keyword_match(text4, expr)
    assert matched is False

    # 5. No match: chỉ có combo không có xé lẻ
    text5 = "Bán combo máy ảnh len không bán lẻ"
    matched, summary, hit_terms = evaluate_keyword_match(text5, expr)
    assert matched is False


def test_not_operator():
    expr = 'iphone AND NOT (lock OR "dính icloud")'
    
    text1 = "Bán iphone 15 pro max quốc tế chuẩn"
    matched, _, _ = evaluate_keyword_match(text1, expr)
    assert matched is True

    text2 = "Bán iphone 15 pro max bản lock nhật"
    matched, _, _ = evaluate_keyword_match(text2, expr)
    assert matched is False


def test_post_and_comments_match():
    expr = '("a1" and ("bán" or "pass")) or ("lens" and "24-70")'
    post = {"message": "Hỏi kinh nghiệm dùng lens sony"}
    comments = [
        {"comment_id": "101", "text": "Em đang có lens 24-70 GM2 cần pass"},
        {"comment_id": "102", "text": "Dùng ngon lắm bác ơi"}
    ]

    matched, hit, source, c_id = check_post_and_comments_match(post, comments, expr)
    assert matched is True
    assert source == "Bình luận"
    assert c_id == "101"


def test_bidirectional_conversion():
    from src.utils.keyword_engine import expression_to_visual_groups, visual_groups_to_expression
    
    # 1. Test visual groups to expression
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

    # 2. Test expression to visual groups
    parsed_groups = expression_to_visual_groups(expr)
    assert len(parsed_groups) == 3
    assert parsed_groups[0]["items"][0]["text"] == "a1"
    assert len(parsed_groups[1]["items"]) == 3
    assert parsed_groups[1]["items"][0]["text"] == "bán"

    # 3. Test round-trip expression
    roundtrip_expr = visual_groups_to_expression(parsed_groups)
    ok, _ = validate_expression(roundtrip_expr)
    assert ok is True


def test_explain_expression():
    from src.utils.keyword_engine import explain_expression

    expr = '("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")'
    explanation = explain_expression(expr)
    assert '"a1"' in explanation
    assert '"bán"' in explanation
    assert '"combo"' in explanation
    assert '"xé lẻ"' in explanation
    assert "HOẶC" in explanation

    empty_exp = explain_expression("")
    assert "Không lọc" in empty_exp


def test_group_operators():
    from src.utils.keyword_engine import expression_to_visual_groups, visual_groups_to_expression

    # Nhóm 1 AND Nhóm 2 AND NOT Nhóm 3
    groups = [
        {
            "id": 1,
            "group_op": "OR",
            "items": [{"op": "AND", "text": "iphone"}]
        },
        {
            "id": 2,
            "group_op": "AND",
            "items": [{"op": "AND", "text": "15 pro"}]
        },
        {
            "id": 3,
            "group_op": "NOT",
            "items": [{"op": "AND", "text": "lock"}]
        }
    ]

    expr = visual_groups_to_expression(groups)
    assert 'iphone' in expr
    assert 'AND "15 pro"' in expr
    assert 'AND NOT "lock"' in expr

    ok, msg = validate_expression(expr)
    assert ok is True

    parsed = expression_to_visual_groups(expr)
    assert len(parsed) >= 2
