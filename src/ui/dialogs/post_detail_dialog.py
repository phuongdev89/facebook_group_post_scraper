import webbrowser
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QTextEdit, QScrollArea, QFrame,
                             QWidget, QGroupBox, QGridLayout, QSizePolicy)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap, QCursor
from src.database.repository import get_post_by_id, get_ai_analysis_by_post_id


class _ThumbLabel(QLabel):
    """Ảnh thumbnail nhỏ — click mở URL bằng trình duyệt hệ thống."""
    def __init__(self, url: str, tooltip: str = "", parent=None):
        super().__init__(parent)
        self._url = url
        self.setFixedSize(100, 80)
        self.setScaledContents(True)
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setStyleSheet(
            "border: 1px solid #D1D5DB; border-radius: 4px; background: #F3F4F6;"
        )
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setText("⏳")
        if tooltip:
            self.setToolTip(tooltip)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._url:
            webbrowser.open(self._url)

    def set_pixmap_from_bytes(self, data: bytes):
        pix = QPixmap()
        if pix.loadFromData(data):
            self.setPixmap(pix.scaled(
                self.width(), self.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            ))
            self.setText("")
        else:
            self.setText("🖼")


class _ImageLoader(QThread):
    done = pyqtSignal(object, bytes)   # (label, data)

    def __init__(self, label, url, parent=None):
        super().__init__(parent)
        self._label = label
        self._url = url

    def run(self):
        try:
            import urllib.request
            with urllib.request.urlopen(self._url, timeout=8) as r:
                data = r.read()
            self.done.emit(self._label, data)
        except Exception:
            self.done.emit(self._label, b"")


class PostDetailDialog(QDialog):
    def __init__(self, post_id: str, parent=None):
        super().__init__(parent)
        self.post_id = str(post_id)
        self._loaders = []   # giữ tham chiếu để thread không bị GC
        self.setWindowTitle(f"Chi tiết bài viết & Đánh giá AI - Post ID: {self.post_id}")
        self.resize(880, 760)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        
        post_data = get_post_by_id(self.post_id)
        ai_data = get_ai_analysis_by_post_id(self.post_id)
        
        if not post_data:
            layout.addWidget(QLabel(f"❌ Không tìm thấy dữ liệu cho bài viết ID: {self.post_id}"))
            close_btn = QPushButton("Đóng")
            close_btn.clicked.connect(self.accept)
            layout.addWidget(close_btn)
            return

        # 1. AI Analysis Card
        if ai_data:
            ai_card = QGroupBox("🤖 Kết quả Đánh giá AI")
            ai_card.setStyleSheet("""
                QGroupBox {
                    font-weight: bold;
                    color: #5B21B6;
                    border: 1px solid #DDD6FE;
                    border-radius: 6px;
                    margin-top: 6px;
                    padding-top: 10px;
                    background-color: #F5F3FF;
                }
                QGroupBox::title {
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 4px;
                }
            """)
            ai_layout = QVBoxLayout(ai_card)
            
            grid = QGridLayout()
            grid.setSpacing(6)
            
            target = ai_data.get("target_name") or ai_data.get("device_name") or "Không đề cập"
            price = ai_data.get("price") or ai_data.get("price_or_budget") or "Thỏa thuận"
            actor_role = ai_data.get("actor_role") or ai_data.get("seller_type") or "N/A"
            model_used = ai_data.get("model_used") or "N/A"
            reason = ai_data.get("reason") or "N/A"
            snippet = ai_data.get("matched_snippet") or ai_data.get("seller_snippet") or ""
            
            grid.addWidget(QLabel("<b>Mục tiêu / Đối tượng:</b>"), 0, 0)
            grid.addWidget(QLabel(f"<code>{target}</code>"), 0, 1)
            
            grid.addWidget(QLabel("<b>Giá / Lương / Ngân sách:</b>"), 0, 2)
            grid.addWidget(QLabel(f"<b style='color:#B91C1C;'>{price}</b>"), 0, 3)
            
            grid.addWidget(QLabel("<b>Vai trò phát hiện:</b>"), 1, 0)
            grid.addWidget(QLabel(f"<b>{actor_role}</b>"), 1, 1)
            
            grid.addWidget(QLabel("<b>Model AI:</b>"), 1, 2)
            grid.addWidget(QLabel(f"<code>{model_used}</code>"), 1, 3)
            
            comment_id = ai_data.get("comment_id")
            if comment_id:
                grid.addWidget(QLabel("<b>Comment / Reply ID:</b>"), 2, 0)
                grid.addWidget(QLabel(f"<code>{comment_id}</code>"), 2, 1)
                grid.addWidget(QLabel("<b>Nguồn khớp:</b>"), 2, 2)
                grid.addWidget(QLabel(f"<code>{ai_data.get('matched_source') or 'Bình luận'}</code>"), 2, 3)
            
            ai_layout.addLayout(grid)

            
            if snippet:
                ai_layout.addWidget(QLabel(f"💬 <b>Trích đoạn:</b> <i>{snippet}</i>"))
            if reason:
                ai_layout.addWidget(QLabel(f"💡 <b>Đánh giá:</b> <i>{reason}</i>"))
                
            layout.addWidget(ai_card)

        # 2. Post Header Info
        header_group = QGroupBox("📄 Thông tin bài viết")
        h_layout = QGridLayout(header_group)
        
        group_name = post_data.get("group_name") or post_data.get("page_name") or "Facebook"
        author_name = post_data.get("user_name") or "Ẩn danh"
        created_time = post_data.get("created_time_formatted") or post_data.get("created_time") or "N/A"
        permalink = post_data.get("permalink") or f"https://www.facebook.com/{self.post_id}"
        
        h_layout.addWidget(QLabel("<b>Nhóm / Trang:</b>"), 0, 0)
        h_layout.addWidget(QLabel(group_name), 0, 1)
        
        h_layout.addWidget(QLabel("<b>Người đăng:</b>"), 0, 2)
        h_layout.addWidget(QLabel(author_name), 0, 3)
        
        h_layout.addWidget(QLabel("<b>Thời gian:</b>"), 1, 0)
        h_layout.addWidget(QLabel(str(created_time)), 1, 1)
        
        open_fb_btn = QPushButton("🔗 Mở trên Facebook")
        open_fb_btn.setStyleSheet("padding: 3px 8px; font-weight: bold; background-color: #2563EB; color: white; border-radius: 4px;")
        open_fb_btn.clicked.connect(lambda: webbrowser.open(permalink))
        h_layout.addWidget(open_fb_btn, 1, 3)
        
        layout.addWidget(header_group)

        # 3. Post Message
        layout.addWidget(QLabel("<b>📝 Nội dung bài viết:</b>"))
        msg_text = QTextEdit()
        msg_text.setReadOnly(True)
        msg_text.setPlainText(post_data.get("message") or "(Không có nội dung văn bản)")
        msg_text.setMaximumHeight(130)
        layout.addWidget(msg_text)

        # 4. Media Section (photos + videos)
        photos = post_data.get("photos") or []
        videos = post_data.get("videos") or []
        if photos or videos:
            media_group = QGroupBox(f"🖼 Ảnh & Video ({len(photos)} ảnh, {len(videos)} video) — Bấm để mở")
            media_group.setStyleSheet("""
                QGroupBox {
                    font-weight: bold; font-size: 12px;
                    border: 1px solid #E5E7EB; border-radius: 6px;
                    margin-top: 6px; padding-top: 8px;
                }
                QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            """)
            media_flow = QHBoxLayout(media_group)
            media_flow.setContentsMargins(8, 8, 8, 8)
            media_flow.setSpacing(8)
            media_flow.setAlignment(Qt.AlignmentFlag.AlignLeft)

            for i, photo in enumerate(photos):
                url = photo.get("url") or ""
                if not url:
                    continue
                lbl = _ThumbLabel(url, tooltip=f"Ảnh {i+1} — Bấm để mở")
                lbl.setText("🖼")
                media_flow.addWidget(lbl)
                loader = _ImageLoader(lbl, url, self)
                loader.done.connect(lambda label, data: label.set_pixmap_from_bytes(data) if data else label.setText("🖼"))
                self._loaders.append(loader)
                loader.start()

            for i, video in enumerate(videos):
                # video thumbnail hoặc fallback placeholder
                thumb_url = video.get("thumbnail") or ""
                open_url = video.get("url") or video.get("playable_url") or ""
                lbl = _ThumbLabel(open_url or thumb_url, tooltip=f"Video {i+1} — Bấm để mở")
                lbl.setText("🎬")
                lbl.setStyleSheet(lbl.styleSheet() + " color: #1D4ED8; font-size: 28px;")
                if thumb_url:
                    loader = _ImageLoader(lbl, thumb_url, self)
                    loader.done.connect(lambda label, data: label.set_pixmap_from_bytes(data) if data else None)
                    self._loaders.append(loader)
                    loader.start()
                media_flow.addWidget(lbl)

            media_flow.addStretch()
            layout.addWidget(media_group)

        # 5. Comments Section
        comments = post_data.get("comments") or []
        layout.addWidget(QLabel(f"<b>💬 Bình luận ({len(comments)} bình luận gốc):</b>"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: white; border: 1px solid #E5E7EB; border-radius: 4px;")
        
        comment_container = QWidget()
        c_layout = QVBoxLayout(comment_container)
        c_layout.setContentsMargins(6, 6, 6, 6)
        c_layout.setSpacing(6)
        
        if not comments:
            c_layout.addWidget(QLabel("<i>(Chưa có bình luận nào được lưu)</i>"))
        else:
            for c in comments:
                c_card = QFrame()
                c_card.setStyleSheet("background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 6px; padding: 6px;")
                card_layout = QVBoxLayout(c_card)
                card_layout.setContentsMargins(4, 4, 4, 4)
                card_layout.setSpacing(2)
                
                c_author = c.get("author_name") or "Người dùng"
                c_text = c.get("text") or ""
                card_layout.addWidget(QLabel(f"<b>👤 {c_author}:</b>"))
                card_layout.addWidget(QLabel(c_text))
                
                replies = c.get("replies") or []
                for r in replies:
                    r_card = QFrame()
                    r_card.setStyleSheet("background-color: #F3F4F6; border-left: 2px solid #6366F1; margin-left: 14px; padding: 4px;")
                    r_layout = QVBoxLayout(r_card)
                    r_layout.setContentsMargins(4, 2, 4, 2)
                    r_author = r.get("author_name") or "Người dùng"
                    r_text = r.get("text") or ""
                    r_layout.addWidget(QLabel(f"↳ <b>{r_author}:</b> {r_text}"))
                    card_layout.addWidget(r_card)
                    
                c_layout.addWidget(c_card)
                
        c_layout.addStretch()
        scroll.setWidget(comment_container)
        layout.addWidget(scroll)

        close_btn = QPushButton("Đóng")
        close_btn.setStyleSheet("padding: 8px; font-weight: bold; border-radius: 4px;")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
