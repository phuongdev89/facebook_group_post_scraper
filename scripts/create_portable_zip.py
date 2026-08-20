#!/usr/bin/env python3
"""
Create Portable ZIP package for Facebook Notification App
Nén thư mục standalone thành file zip tiện phân phối cho người dùng.
"""

import os
import sys
import shutil
import zipfile

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
APP_DIR = os.path.join(DIST_DIR, "FacebookNotification")

VERSION_FILE = os.path.join(PROJECT_ROOT, ".version")
APP_VERSION = "1.0.1"
if os.path.exists(VERSION_FILE):
    try:
        with open(VERSION_FILE, "r", encoding="utf-8") as vf:
            APP_VERSION = vf.read().strip() or "1.0.1"
    except Exception:
        pass

ZIP_OUTPUT = os.path.join(DIST_DIR, f"FacebookNotification-v{APP_VERSION}-windows-x64-portable.zip")



def create_portable_zip():
    if not os.path.exists(APP_DIR):
        print(f"❌ [Zip] Không tìm thấy thư mục {APP_DIR}. Hãy chạy scripts/build_standalone.py trước.")
        sys.exit(1)

    print(f"📦 Đang nén thư mục '{APP_DIR}' thành '{ZIP_OUTPUT}'...")
    if os.path.exists(ZIP_OUTPUT):
        os.remove(ZIP_OUTPUT)

    with zipfile.ZipFile(ZIP_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(APP_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, APP_DIR)
                zipf.write(file_path, os.path.join("FacebookNotification", rel_path))

    file_size_mb = os.path.getsize(ZIP_OUTPUT) / (1024 * 1024)
    print("=" * 60)
    print("✅ [Zip] Tạo gói Portable ZIP thành công!")
    print(f"📍 File: {ZIP_OUTPUT}")
    print(f"📊 Dung lượng: {file_size_mb:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    create_portable_zip()
