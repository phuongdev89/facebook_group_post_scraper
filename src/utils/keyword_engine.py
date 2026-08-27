"""
Keyword Engine - Bộ máy phân tích và đánh giá biểu thức logic từ khóa (Boolean Expression Engine)
Hỗ trợ:
- Toán tử logic: AND, OR, NOT (hoặc and, or, not, &&, ||, !)
- Cụm từ chính xác: "bán máy", 'combo xé lẻ'
- Dấu ngoặc lồng nhau: ( ... )
- 2 chế độ: "Tự nhập biểu thức (Raw)" và "Dựng điều kiện trực quan (Visual Rule Builder)"
- Chuyển đổi qua lại 2 chiều giữa Biểu thức chuỗi <-> Cấu trúc nhóm trực quan
"""

import re
from typing import Tuple, List, Optional, Union, Dict, Any


class Token:
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    TERM = "TERM"

    def __init__(self, type_: str, value: str, pos: int = 0):
        self.type = type_
        self.value = value
        self.pos = pos

    def __repr__(self):
        return f"Token({self.type}, {repr(self.value)})"


def tokenize(expr: str) -> List[Token]:
    """Tách biểu thức thành danh sách các Tokens"""
    tokens = []
    i = 0
    n = len(expr)

    while i < n:
        c = expr[i]

        # Bỏ qua khoảng trắng
        if c.isspace():
            i += 1
            continue

        # Dấu ngoặc
        if c == '(':
            tokens.append(Token(Token.LPAREN, '(', i))
            i += 1
            continue
        if c == ')':
            tokens.append(Token(Token.RPAREN, ')', i))
            i += 1
            continue

        # Cụm từ trong ngoặc kép hoặc ngoặc đơn: "..." hoặc '...'
        if c in ('"', "'", '“', '”', '‘', '’'):
            quote_char = c
            close_quotes = ('"', '”') if c in ('"', '“', '”') else ("'", '’')
            start_pos = i
            i += 1
            phrase_chars = []
            while i < n and expr[i] not in close_quotes:
                phrase_chars.append(expr[i])
                i += 1
            if i < n and expr[i] in close_quotes:
                i += 1  # Bỏ qua dấu đóng ngoặc
            phrase = "".join(phrase_chars).strip()
            if phrase:
                tokens.append(Token(Token.TERM, phrase, start_pos))
            continue

        # Kiểm tra toán tử ký hiệu đặc biệt: &&, ||, !
        if expr[i:i+2] == '&&':
            tokens.append(Token(Token.AND, 'AND', i))
            i += 2
            continue
        if expr[i:i+2] == '||':
            tokens.append(Token(Token.OR, 'OR', i))
            i += 2
            continue
        if c == '!' and (i + 1 < n and not expr[i+1].isspace() and expr[i+1] not in ('=', '&', '|')):
            tokens.append(Token(Token.NOT, 'NOT', i))
            i += 1
            continue

        # Đọc từ (Word / Term hoặc AND/OR/NOT)
        start_pos = i
        term_chars = []
        while i < n and not expr[i].isspace() and expr[i] not in ('(', ')', '"', "'", '“', '”', '‘', '’'):
            term_chars.append(expr[i])
            i += 1
        
        term = "".join(term_chars).strip()
        term_upper = term.upper()

        if term_upper in ("AND", "&&"):
            tokens.append(Token(Token.AND, "AND", start_pos))
        elif term_upper in ("OR", "||"):
            tokens.append(Token(Token.OR, "OR", start_pos))
        elif term_upper in ("NOT", "!"):
            tokens.append(Token(Token.NOT, "NOT", start_pos))
        else:
            if term:
                tokens.append(Token(Token.TERM, term, start_pos))

    # Tự động chèn toán tử AND nếu 2 TERM hoặc RPAREN-TERM đứng cạnh nhau mà thiếu toán tử
    normalized_tokens = []
    for idx, tok in enumerate(tokens):
        if idx > 0:
            prev = tokens[idx - 1]
            if (prev.type in (Token.TERM, Token.RPAREN) and
                tok.type in (Token.TERM, Token.LPAREN, Token.NOT)):
                normalized_tokens.append(Token(Token.AND, "AND", tok.pos))
        normalized_tokens.append(tok)

    return normalized_tokens


# ================= AST NODES =================

class ASTNode:
    def evaluate(self, text_lower: str, matched_terms: list) -> bool:
        raise NotImplementedError

    def to_string(self) -> str:
        raise NotImplementedError


class TermNode(ASTNode):
    def __init__(self, term: str):
        self.term = term
        self.term_lower = term.lower().strip()

    def evaluate(self, text_lower: str, matched_terms: list) -> bool:
        if not self.term_lower:
            return True
        if self.term_lower in text_lower:
            if self.term not in matched_terms:
                matched_terms.append(self.term)
            return True
        return False

    def to_string(self) -> str:
        if " " in self.term:
            return f'"{self.term}"'
        return self.term

    def __repr__(self):
        return f"Term({repr(self.term)})"


class NotNode(ASTNode):
    def __init__(self, child: ASTNode):
        self.child = child

    def evaluate(self, text_lower: str, matched_terms: list) -> bool:
        dummy_list = []
        return not self.child.evaluate(text_lower, dummy_list)

    def to_string(self) -> str:
        if isinstance(self.child, TermNode):
            return f"NOT {self.child.to_string()}"
        return f"NOT ({self.child.to_string()})"

    def __repr__(self):
        return f"NOT({self.child})"


class AndNode(ASTNode):
    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right

    def evaluate(self, text_lower: str, matched_terms: list) -> bool:
        left_val = self.left.evaluate(text_lower, matched_terms)
        if not left_val:
            return False
        return self.right.evaluate(text_lower, matched_terms)

    def to_string(self) -> str:
        return f"{self.left.to_string()} AND {self.right.to_string()}"

    def __repr__(self):
        return f"({self.left} AND {self.right})"


class OrNode(ASTNode):
    def __init__(self, left: ASTNode, right: ASTNode):
        self.left = left
        self.right = right

    def evaluate(self, text_lower: str, matched_terms: list) -> bool:
        left_val = self.left.evaluate(text_lower, matched_terms)
        right_val = self.right.evaluate(text_lower, matched_terms)
        return left_val or right_val

    def to_string(self) -> str:
        return f"{self.left.to_string()} OR {self.right.to_string()}"

    def __repr__(self):
        return f"({self.left} OR {self.right})"


# ================= PARSER (Recursive Descent) =================

class Parser:
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0

    def current(self) -> Optional[Token]:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return None

    def consume(self, expected_type: str = None) -> Token:
        tok = self.current()
        if tok is None:
            raise ValueError("Cú pháp kết thúc bất ngờ (Thiếu từ khóa hoặc dấu ngoặc đóng).")
        if expected_type and tok.type != expected_type:
            raise ValueError(f"Kỳ vọng {expected_type} nhưng gặp '{tok.value}' tại vị trí {tok.pos}.")
        self.pos += 1
        return tok

    def parse(self) -> Optional[ASTNode]:
        if not self.tokens:
            return None
        node = self.parse_or()
        if self.current() is not None:
            extra = self.current()
            raise ValueError(f"Cú pháp dư thừa gần '{extra.value}' tại vị trí {extra.pos}.")
        return node

    def parse_or(self) -> ASTNode:
        node = self.parse_and()
        while self.current() and self.current().type == Token.OR:
            self.consume(Token.OR)
            right = self.parse_and()
            node = OrNode(node, right)
        return node

    def parse_and(self) -> ASTNode:
        node = self.parse_not()
        while self.current() and self.current().type == Token.AND:
            self.consume(Token.AND)
            right = self.parse_not()
            node = AndNode(node, right)
        return node

    def parse_not(self) -> ASTNode:
        if self.current() and self.current().type == Token.NOT:
            self.consume(Token.NOT)
            child = self.parse_not()
            return NotNode(child)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        tok = self.current()
        if tok is None:
            raise ValueError("Thiếu từ khóa hoặc biểu thức con sau toán tử.")

        if tok.type == Token.LPAREN:
            self.consume(Token.LPAREN)
            node = self.parse_or()
            self.consume(Token.RPAREN)
            return node
        elif tok.type == Token.TERM:
            self.consume(Token.TERM)
            return TermNode(tok.value)
        else:
            raise ValueError(f"Toán tử '{tok.value}' đặt sai vị trí tại vị trí {tok.pos}.")


# ================= TWO-WAY CONVERSION (AST <-> VISUAL GROUPS) =================

def _has_and_node(node: ASTNode) -> bool:
    """Kiểm tra cây AST có chứa nhánh AND hay không"""
    if isinstance(node, AndNode):
        return True
    if isinstance(node, OrNode):
        return _has_and_node(node.left) or _has_and_node(node.right)
    if isinstance(node, NotNode):
        return _has_and_node(node.child)
    return False


def _has_or_node(node: ASTNode) -> bool:
    """Kiểm tra cây AST có chứa nhánh OR hay không"""
    if isinstance(node, OrNode):
        return True
    if isinstance(node, AndNode):
        return _has_or_node(node.left) or _has_or_node(node.right)
    if isinstance(node, NotNode):
        return _has_or_node(node.child)
    return False


def _is_flat_group(node: ASTNode) -> bool:
    """
    Kiểm tra một ASTNode có phải là một khối nhóm đơn thuần (chỉ toàn OR hoặc chỉ toàn AND/NOT) hay không.
    Nếu là flat group, node này tương ứng với 1 GroupCard duy nhất trong Visual Builder.
    """
    if isinstance(node, TermNode):
        return True
    if isinstance(node, NotNode):
        return _is_flat_group(node.child)
    if isinstance(node, OrNode):
        return not _has_and_node(node)
    if isinstance(node, AndNode):
        return not _has_or_node(node)
    return False


def _collect_top_groups(node: ASTNode, default_op: str = "OR") -> List[Tuple[str, ASTNode]]:
    """Tách các nhóm cấp cao nhất kèm toán tử nối (group_op, node)"""
    if _is_flat_group(node):
        return [(default_op, node)]

    if isinstance(node, OrNode):
        left_branches = _collect_top_groups(node.left, default_op)
        right_branches = _collect_top_groups(node.right, "OR")
        return left_branches + right_branches
    elif isinstance(node, AndNode):
        left_branches = _collect_top_groups(node.left, default_op)
        right_branches = _collect_top_groups(node.right, "AND")
        return left_branches + right_branches
    elif isinstance(node, NotNode):
        return [("NOT", node.child)]
    return [(default_op, node)]


def _decompose_group_to_rows(node: ASTNode, default_op: str = "AND") -> List[Dict[str, str]]:
    """
    Tách triệt để một ASTNode nhóm thành danh sách các dòng điều kiện trực quan.
    Đảm bảo mỗi dòng CHỈ chứa từ khóa thuần túy trong 'text', còn toán tử (AND, OR, NOT) nằm ở 'op'.
    Tuyệt đối không để chữ AND, OR, NOT lẫn vào ô text!
    """
    if isinstance(node, TermNode):
        term = node.term.strip()
        if (term.startswith('"') and term.endswith('"')) or (term.startswith("'") and term.endswith("'")):
            term = term[1:-1].strip()
        return [{"op": default_op, "text": term}]
    elif isinstance(node, NotNode):
        if isinstance(node.child, TermNode):
            term = node.child.term.strip()
            if (term.startswith('"') and term.endswith('"')) or (term.startswith("'") and term.endswith("'")):
                term = term[1:-1].strip()
            return [{"op": "NOT", "text": term}]
        else:
            child_rows = _decompose_group_to_rows(node.child, "NOT")
            return child_rows
    elif isinstance(node, AndNode):
        left_rows = _decompose_group_to_rows(node.left, default_op)
        right_rows = _decompose_group_to_rows(node.right, "AND")
        return left_rows + right_rows
    elif isinstance(node, OrNode):
        left_rows = _decompose_group_to_rows(node.left, default_op if default_op == "OR" else "OR")
        right_rows = _decompose_group_to_rows(node.right, "OR")
        return left_rows + right_rows
    else:
        return [{"op": default_op, "text": str(getattr(node, "term", node))}]


def expression_to_visual_groups(expr: str) -> List[Dict[str, Any]]:
    """
    Chuyển đổi chuỗi biểu thức logic thành danh sách nhóm điều kiện trực quan.
    Tất cả các toán tử AND, OR, NOT được đưa vào dropdown 'op' / 'group_op',
    ô 'text' chỉ chứa từ khóa đơn lẻ.
    """
    expr = str(expr or "").strip()
    if not expr:
        return [{"id": 1, "group_op": "OR", "items": [{"op": "AND", "text": ""}]}]

    try:
        tokens = tokenize(expr)
        if not tokens:
            return [{"id": 1, "group_op": "OR", "items": [{"op": "AND", "text": ""}]}]
        parser = Parser(tokens)
        ast = parser.parse()
        if ast is None:
            return [{"id": 1, "group_op": "OR", "items": [{"op": "AND", "text": ""}]}]

        top_groups = _collect_top_groups(ast)
        visual_groups = []

        for idx, (grp_op, branch) in enumerate(top_groups):
            items = _decompose_group_to_rows(branch)
            if not items:
                items = [{"op": "AND", "text": ""}]
            visual_groups.append({
                "id": idx + 1,
                "group_op": grp_op,
                "items": items
            })

        return visual_groups if visual_groups else [{"id": 1, "group_op": "OR", "items": [{"op": "AND", "text": ""}]}]

    except Exception:
        # Fallback nếu chuỗi không parse chuẩn
        return [{"id": 1, "group_op": "OR", "items": [{"op": "AND", "text": expr}]}]


def _format_item_text(text: str) -> str:
    """Format một từ khóa đơn lẻ thành dạng chuỗi chuẩn trong biểu thức"""
    t = str(text or "").strip()
    if not t:
        return ""
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        t = t[1:-1].strip()
    return f'"{t}"'


def visual_groups_to_expression(groups: List[Dict[str, Any]]) -> str:
    """
    Chuyển đổi danh sách nhóm trực quan thành chuỗi biểu thức logic chuẩn.
    Hỗ trợ toán tử group_op giữa các nhóm (OR, AND, NOT).
    """
    group_parts = []

    for idx, grp in enumerate(groups):
        items = grp.get("items", [])
        if not items:
            continue

        item_parts = []
        for it_idx, it in enumerate(items):
            op = str(it.get("op", "AND")).upper().strip()
            raw_text = str(it.get("text", "")).strip()
            if not raw_text:
                continue

            formatted_val = _format_item_text(raw_text)
            if not formatted_val:
                continue

            if it_idx == 0:
                if op == "NOT":
                    item_parts.append(f"NOT {formatted_val}")
                else:
                    item_parts.append(formatted_val)
            else:
                if op == "NOT":
                    item_parts.append(f"AND NOT {formatted_val}")
                elif op == "OR":
                    item_parts.append(f"OR {formatted_val}")
                else:  # AND
                    item_parts.append(f"AND {formatted_val}")

        if not item_parts:
            continue

        group_str = " ".join(item_parts)
        if len(item_parts) > 1:
            group_str = f"({group_str})"

        group_op = str(grp.get("group_op", "OR")).upper().strip()
        if idx == 0:
            if group_op == "NOT":
                group_parts.append(f"NOT {group_str}")
            else:
                group_parts.append(group_str)
        else:
            if group_op in ("NOT", "AND NOT"):
                group_parts.append(f"AND NOT {group_str}")
            elif group_op == "AND":
                group_parts.append(f"AND {group_str}")
            else:  # OR
                group_parts.append(f"OR {group_str}")

    if not group_parts:
        return ""

    return " ".join(group_parts)


# ================= PUBLIC API =================

def validate_expression(expr: str) -> Tuple[bool, str]:
    """Kiểm tra tính hợp lệ của biểu thức logic từ khóa. Trả về (is_valid, message)"""
    if not expr or not expr.strip():
        return True, "Biểu thức trống (Chấp nhận tất cả bài viết/bình luận)."

    try:
        tokens = tokenize(expr)
        if not tokens:
            return True, "Biểu thức trống."
        parser = Parser(tokens)
        ast = parser.parse()
        return True, "✅ Cú pháp biểu thức logic hợp lệ."
    except Exception as e:
        return False, f"⚠️ Lỗi cú pháp: {str(e)}"


def parse_expression(expr_or_list: Union[str, list]) -> Optional[ASTNode]:
    """Chuyển đổi chuỗi hoặc danh sách từ khóa thành AST Tree"""
    if isinstance(expr_or_list, list):
        clean_tags = [str(t).strip() for t in expr_or_list if str(t).strip()]
        if not clean_tags:
            return None
        expr = " OR ".join(f'"{t}"' for t in clean_tags)
    else:
        expr = str(expr_or_list or "").strip()

    if not expr:
        return None

    try:
        tokens = tokenize(expr)
        if not tokens:
            return None
        parser = Parser(tokens)
        return parser.parse()
    except Exception:
        return TermNode(expr)


def evaluate_keyword_match(
    text: str,
    expression_or_keywords: Union[str, list, ASTNode]
) -> Tuple[bool, str, List[str]]:
    """
    Kiểm tra một đoạn văn bản (text) có thỏa mãn biểu thức từ khóa không.
    """
    if not expression_or_keywords:
        return True, "Không có bộ lọc từ khóa", []

    if isinstance(expression_or_keywords, ASTNode):
        ast = expression_or_keywords
    else:
        ast = parse_expression(expression_or_keywords)

    if ast is None:
        return True, "Không có bộ lọc từ khóa", []

    text_lower = (text or "").lower()
    matched_terms = []
    is_matched = ast.evaluate(text_lower, matched_terms)

    if is_matched:
        terms_str = ", ".join([f"'{t}'" for t in matched_terms]) if matched_terms else "Khớp điều kiện"
        return True, f"Khớp từ khóa: {terms_str}", matched_terms
    else:
        return False, "Không khớp điều kiện", []


def check_post_and_comments_match(
    post_data: dict,
    comments_data: list,
    expression_or_keywords: Union[str, list]
) -> Tuple[bool, str, str, Optional[str]]:
    """
    Kiểm tra tổng hợp cả bài viết, các bình luận và phản hồi.
    """
    if not expression_or_keywords:
        return True, "", "", None

    ast = parse_expression(expression_or_keywords)
    if ast is None:
        return True, "", "", None

    # 1. Kiểm tra bài viết
    post_text = (post_data.get("message") or post_data.get("text") or "")
    matched, _, hit_terms = evaluate_keyword_match(post_text, ast)
    if matched:
        hit_label = ", ".join(hit_terms) if hit_terms else "Bài viết"
        return True, hit_label, "Bài viết", None

    # 2. Kiểm tra bình luận
    if comments_data:
        for c in comments_data:
            c_text = (c.get("text") or "")
            matched, _, hit_terms = evaluate_keyword_match(c_text, ast)
            if matched:
                c_id = str(c.get("comment_id") or c.get("id") or "")
                hit_label = ", ".join(hit_terms) if hit_terms else "Bình luận"
                return True, hit_label, "Bình luận", c_id if c_id else None

            # 3. Kiểm tra phản hồi (Replies)
            for r in (c.get("replies") or []):
                r_text = (r.get("text") or "")
                matched, _, hit_terms = evaluate_keyword_match(r_text, ast)
                if matched:
                    r_id = str(r.get("reply_id") or r.get("id") or c.get("comment_id") or "")
                    hit_label = ", ".join(hit_terms) if hit_terms else "Phản hồi"
                    return True, hit_label, "Phản hồi bình luận", r_id if r_id else None

    return False, "", "", None


# ================= HUMAN-READABLE EXPLAINER =================

def _is_all_terms(nodes: List[ASTNode]) -> bool:
    return all(isinstance(n, TermNode) for n in nodes)


def _collect_flat_or(node: ASTNode) -> List[ASTNode]:
    if isinstance(node, OrNode):
        return _collect_flat_or(node.left) + _collect_flat_or(node.right)
    return [node]


def _collect_flat_and(node: ASTNode) -> List[ASTNode]:
    if isinstance(node, AndNode):
        return _collect_flat_and(node.left) + _collect_flat_and(node.right)
    return [node]


def explain_node(node: ASTNode) -> str:
    if node is None:
        return "không giới hạn từ khóa"

    if isinstance(node, TermNode):
        return f'từ khóa "{node.term}"'

    if isinstance(node, NotNode):
        if isinstance(node.child, TermNode):
            return f'không chứa từ khóa "{node.child.term}"'
        elif isinstance(node.child, OrNode):
            or_terms = _collect_flat_or(node.child)
            if _is_all_terms(or_terms):
                terms_str = " hoặc ".join([f'"{t.term}"' for t in or_terms])
                return f'không chứa bất kỳ từ khóa nào trong ({terms_str})'
        return f'không chứa ({explain_node(node.child)})'

    if isinstance(node, OrNode):
        branches = _collect_flat_or(node)
        if _is_all_terms(branches):
            terms_str = " hoặc ".join([f'"{t.term}"' for t in branches])
            return f'1 trong các từ khóa {terms_str}'
        return " HOẶC ".join([explain_node(b) for b in branches])

    if isinstance(node, AndNode):
        branches = _collect_flat_and(node)
        
        # Tất cả đều là TermNode đơn lẻ
        if _is_all_terms(branches):
            count = len(branches)
            terms_str = " và ".join([f'"{t.term}"' for t in branches])
            return f'chứa cả {count} từ {terms_str}'
        
        term_nodes = [b for b in branches if isinstance(b, TermNode)]
        other_nodes = [b for b in branches if not isinstance(b, TermNode)]
        
        parts = []
        if term_nodes:
            if len(term_nodes) == 1:
                parts.append(f'có chứa từ khóa "{term_nodes[0].term}"')
            else:
                t_str = " và ".join([f'"{t.term}"' for t in term_nodes])
                parts.append(f'có chứa cả {len(term_nodes)} từ {t_str}')
        
        for on in other_nodes:
            if isinstance(on, OrNode):
                or_terms = _collect_flat_or(on)
                if _is_all_terms(or_terms):
                    terms_str = " hoặc ".join([f'"{t.term}"' for t in or_terms])
                    parts.append(f'kèm thêm 1 trong các từ khóa {terms_str}')
                else:
                    parts.append(f'kèm thêm ({explain_node(on)})')
            elif isinstance(on, NotNode):
                parts.append(f'và {explain_node(on)}')
            else:
                parts.append(f'và ({explain_node(on)})')
                
        return " ".join(parts)

    return node.to_string()


def explain_expression(expr: str) -> str:
    """
    Chuyển đổi biểu thức logic thành câu giải thích tự nhiên bằng tiếng Việt.
    Ví dụ: ("a1" and ("bán" or "pass" or "thanh lý")) or ("combo" and "xé lẻ")
    -> Lọc bài viết có chứa từ khóa "a1" kèm thêm 1 trong các từ khóa "bán" hoặc "pass" hoặc "thanh lý" HOẶC bài viết có chứa cả 2 từ "combo" và "xé lẻ"
    """
    expr = str(expr or "").strip()
    if not expr:
        return "Không lọc từ khóa (lấy tất cả bài viết và bình luận)."

    try:
        tokens = tokenize(expr)
        if not tokens:
            return "Không lọc từ khóa (lấy tất cả bài viết và bình luận)."
        parser = Parser(tokens)
        ast = parser.parse()
        if ast is None:
            return "Không lọc từ khóa (lấy tất cả bài viết và bình luận)."

        if isinstance(ast, OrNode):
            or_branches = _collect_flat_or(ast)
            explained_branches = []
            for b in or_branches:
                b_exp = explain_node(b)
                if not b_exp.startswith("có chứa") and not b_exp.startswith("bài viết") and not b_exp.startswith("chứa"):
                    b_exp = f"bài viết có chứa {b_exp}"
                elif not b_exp.startswith("bài viết"):
                    b_exp = f"bài viết {b_exp}"
                explained_branches.append(b_exp)
            return "Lọc " + " HOẶC ".join(explained_branches)
        else:
            exp = explain_node(ast)
            if not exp.startswith("có chứa") and not exp.startswith("bài viết") and not exp.startswith("chứa"):
                exp = f"bài viết có chứa {exp}"
            elif not exp.startswith("bài viết"):
                exp = f"bài viết {exp}"
            return f"Lọc {exp}"
    except Exception:
        return f"Lọc bài viết theo biểu thức: {expr}"

