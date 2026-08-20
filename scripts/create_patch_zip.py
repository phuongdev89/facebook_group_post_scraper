#!/usr/bin/env python3
"""
Create Lightweight Patch ZIP package for Facebook Notification App
Chỉ đóng gói file .exe, thư mục _internal/src và guides (không kèm DLL nặng)
"""

import os
import sys
import zipfile

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

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

ZIP_OUTPUT = os.path.join(DIST_DIR, f"FacebookNotification_Patch_v{APP_VERSION}.zip")


def create_patch_zip():
    exe_file = os.path.join(APP_DIR, "FacebookNotification.exe")
    src_dir = os.path.join(APP_DIR, "_internal", "src")
    guides_dir = os.path.join(PROJECT_ROOT, "guides")

    if not os.path.exists(exe_file) or not os.path.exists(src_dir):
        print(f"❌ [Patch Zip] Không tìm thấy file build tại {APP_DIR}.")
        sys.exit(1)

    print(f"📦 Đang tạo gói Patch ZIP siêu nhẹ '{ZIP_OUTPUT}'...")
    if os.path.exists(ZIP_OUTPUT):
        os.remove(ZIP_OUTPUT)

    with zipfile.ZipFile(ZIP_OUTPUT, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # 1. Add exe
        zipf.write(exe_file, "FacebookNotification.exe")

        # 2. Add _internal/src
        for root, dirs, files in os.walk(src_dir):
            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, APP_DIR)
                zipf.write(file_path, rel_path)

        # 3. Add guides
        if os.path.exists(guides_dir):
            for root, dirs, files in os.walk(guides_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    rel_path = os.path.relpath(file_path, PROJECT_ROOT)
                    zipf.write(file_path, rel_path)

    file_size_mb = os.path.getsize(ZIP_OUTPUT) / (1024 * 1024)
    print("=" * 60)
    print("✅ [Patch Zip] Tạo gói Patch Portable ZIP thành công!")
    print(f"📍 File: {ZIP_OUTPUT}")
    print(f"📊 Dung lượng: {file_size_mb:.2f} MB")
    print("=" * 60)


if __name__ == "__main__":
    create_patch_zip()
