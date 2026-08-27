import os
import sys
import tempfile
import webbrowser
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QPushButton, QTextEdit, QProgressBar, QMessageBox, QFrame)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from src.core.updater import download_update_file
from src.utils.helpers import get_app_icon


class DownloadWorker(QThread):
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, download_url: str, dest_path: str):
        super().__init__()
        self.download_url = download_url
        self.dest_path = dest_path

    def run(self):
        ok, res = download_update_file(
            download_url=self.download_url,
            dest_path=self.dest_path,
            progress_callback=self.progress_signal.emit
        )
        self.finished_signal.emit(ok, res)


class UpdateDialog(QDialog):
    """
    Hộp thoại hiển thị thông tin cập nhật OTA (Over-The-Air Update):
    - Hiển thị phiên bản hiện tại và phiên bản mới nhất trên GitHub
    - Hiển thị changelog / ghi chú phát hành
    - Nút tải trực tiếp gói cập nhật kèm thanh tiến trình
    - Nút mở trang GitHub Release trên trình duyệt
    """
    def __init__(self, update_info: dict, parent=None):
        super().__init__(parent)
        self.update_info = update_info or {}
        self.download_worker = None
        self.init_ui()

    def init_ui(self):
        icon = get_app_icon()
        if not icon.isNull():
            self.setWindowIcon(icon)

        latest_ver = self.update_info.get("latest_version", "Mới")
        cur_ver = self.update_info.get("current_version", "")
        pub_date = self.update_info.get("published_at", "")
        changelog = self.update_info.get("changelog", "")
        rel_name = self.update_info.get("release_name") or f"Phiên bản v{latest_ver}"
        
        self.setWindowTitle(f"🔄 Cập nhật phần mềm — v{latest_ver}")
        self.setFixedSize(580, 520)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # Header Title
        header_label = QLabel("🚀 Đã có phiên bản cập nhật mới!")
        header_font = QFont("Arial", 14, QFont.Weight.Bold)
        header_label.setFont(header_font)
        header_label.setStyleSheet("color: #1E40AF; margin-top: 4px;")
        layout.addWidget(header_label)

        # Info Box
        info_frame = QFrame()
        info_frame.setStyleSheet("""
            QFrame {
                background-color: #F0FDF4;
                border: 1px solid #BBF7D0;
                border-radius: 6px;
                padding: 10px;
            }
        """)
        info_layout = QVBoxLayout(info_frame)
        info_layout.setSpacing(6)

        v_row = QHBoxLayout()
        v_label = QLabel(f"<b>Phiên bản mới:</b> <span style='color: #15803D; font-size: 14px; font-weight: bold;'>v{latest_ver}</span> (Hiện tại: <code>v{cur_ver}</code>)")
        v_row.addWidget(v_label)
        if pub_date:
            d_label = QLabel(f"<span style='color: #6B7280; font-size: 11px;'>Phát hành: {pub_date}</span>")
            d_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v_row.addWidget(d_label)
        info_layout.addLayout(v_row)

        if rel_name and rel_name != f"Phiên bản v{latest_ver}":
            name_lbl = QLabel(f"<b>Tiêu đề:</b> {rel_name}")
            name_lbl.setStyleSheet("color: #374151; font-size: 12px;")
            info_layout.addWidget(name_lbl)

        layout.addWidget(info_frame)

        # Changelog Label & Box
        layout.addWidget(QLabel("<b>Nội dung cập nhật / Ghi chú phát hành (Changelog):</b>"))

        self.changelog_text = QTextEdit()
        self.changelog_text.setReadOnly(True)
        self.changelog_text.setPlainText(changelog if changelog else "Không có ghi chú chi tiết cho bản cập nhật này.")
        self.changelog_text.setStyleSheet("""
            QTextEdit {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                font-family: Consolas, 'Segoe UI', monospace;
                font-size: 12px;
                padding: 8px;
                line-height: 1.4;
            }
        """)
        layout.addWidget(self.changelog_text)

        # Progress Bar (hidden by default)
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                text-align: center;
                height: 20px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #10B981;
            }
        """)
        layout.addWidget(self.progress_bar)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet("font-size: 11px; color: #4B5563;")
        self.status_label.setVisible(False)
        layout.addWidget(self.status_label)

        # Action Buttons
        btn_layout = QHBoxLayout()

        self.btn_open_web = QPushButton("🌐 Mở trang GitHub Release")
        self.btn_open_web.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #374151;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 14px;
                border: 1px solid #D1D5DB;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #E5E7EB; }
        """)
        self.btn_open_web.clicked.connect(self.open_github_release_page)
        btn_layout.addWidget(self.btn_open_web)

        btn_layout.addStretch()

        self.btn_download = QPushButton("🚀 Tải bản cập nhật")
        self.btn_download.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-size: 12px;
                font-weight: bold;
                padding: 8px 18px;
                border-radius: 5px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #9CA3AF; }
        """)
        self.btn_download.clicked.connect(self.start_download)
        btn_layout.addWidget(self.btn_download)

        self.btn_close = QPushButton("Để sau")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #6B7280;
                font-size: 12px;
                padding: 8px 14px;
            }
            QPushButton:hover { color: #111827; }
        """)
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

    def open_github_release_page(self):
        url = self.update_info.get("release_url") or "https://github.com/phuongdev89/facebook_group_post_scraper/releases"
        webbrowser.open(url)

    def start_download(self):
        dl_url = self.update_info.get("download_url")
        if not dl_url or dl_url.startswith("http") is False:
            self.open_github_release_page()
            return

        latest_ver = self.update_info.get("latest_version", "latest")
        
        # Lấy tên file gốc từ URL hoặc giữ nguyên đuôi .exe
        raw_name = dl_url.split("?")[0].split("/")[-1]
        if raw_name and raw_name.lower().endswith(".exe"):
            filename = raw_name
        else:
            filename = f"FacebookNotification_Patch_v{latest_ver}.exe"

        dest_path = os.path.join(tempfile.gettempdir(), filename)

        self.btn_download.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"⏳ Đang tải bản cập nhật: {filename}...")
        self.status_label.setVisible(True)

        self.download_worker = DownloadWorker(dl_url, dest_path)
        self.download_worker.progress_signal.connect(self.on_download_progress)
        self.download_worker.finished_signal.connect(self.on_download_finished)
        self.download_worker.start()

    def on_download_progress(self, percent: int):
        self.progress_bar.setValue(percent)
        self.status_label.setText(f"📥 Đang tải: {percent}%...")

    def on_download_finished(self, success: bool, result_path_or_err: str):
        self.btn_download.setEnabled(True)
        if success:
            self.status_label.setText(f"✅ Tải thành công: {result_path_or_err}")
            filename = os.path.basename(result_path_or_err)

            reply = QMessageBox.question(
                self,
                "Cài đặt bản cập nhật",
                f"🎉 <b>Đã tải bản cập nhật thành công!</b><br><br>"
                f"• Tệp cài đặt: <code>{filename}</code><br><br>"
                f"<b>Bạn có muốn cài đặt ngay bây giờ không?</b><br>"
                f"<i>(Ứng dụng sẽ tự động đóng để khởi chạy bộ cài đặt)</i>",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if reply == QMessageBox.StandardButton.Yes:
                try:
                    import subprocess
                    if sys.platform == 'win32':
                        os.startfile(result_path_or_err)
                    else:
                        subprocess.Popen([result_path_or_err], shell=True)

                    # Đóng ứng dụng ngay lập tức
                    from PyQt6.QtWidgets import QApplication
                    app = QApplication.instance()
                    if app:
                        app.quit()
                    else:
                        sys.exit(0)
                except Exception as e:
                    QMessageBox.critical(self, "Lỗi khởi chạy", f"Không thể tự động chạy tệp cài đặt:\n{e}")

            self.accept()
        else:
            self.status_label.setText(f"❌ Tải thất bại: {result_path_or_err}")
            QMessageBox.warning(
                self,
                "Lỗi tải cập nhật",
                f"Không thể tải trực tiếp file cập nhật:\n{result_path_or_err}\n\nBạn có thể mở trang GitHub Release để tải thủ công."
            )
