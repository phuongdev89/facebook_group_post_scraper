#!/usr/bin/env python3
"""
Build Script - Facebook Notification & Scraper Standalone Executable
Đóng gói toàn bộ ứng dụng thành bộ chạy độc lập (Standalone) không cần cài đặt Python.
"""

import os
import sys
import subprocess
import shutil

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPEC_FILE = os.path.join(PROJECT_ROOT, "facebook_notification.spec")
DIST_DIR = os.path.join(PROJECT_ROOT, "dist")
OUTPUT_APP_DIR = os.path.join(DIST_DIR, "FacebookNotification")


def check_and_install_pyinstaller():
    """Kiểm tra và cài đặt pyinstaller nếu chưa có"""
    try:
        import PyInstaller
        print(f"[Build] PyInstaller version: {PyInstaller.__version__}")
        return True
    except ImportError:
        print("[Build] PyInstaller not found. Installing pyinstaller...")
        ret = subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], cwd=PROJECT_ROOT)
        return ret.returncode == 0


def build():
    """Thực hiện đóng gói ứng dụng qua PyInstaller"""
    print("=" * 60)
    print("🚀 Bắt đầu đóng gói Facebook Notification Standalone App...")
    print(f"Project root: {PROJECT_ROOT}")
    print(f"Spec file: {SPEC_FILE}")
    print("=" * 60)

    if not check_and_install_pyinstaller():
        print("[Build] ERROR: Failed to install or find PyInstaller.")
        sys.exit(1)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        SPEC_FILE
    ]

    print(f"[Build] Executing: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("\n❌ [Build] PyInstaller build FAILED!")
        sys.exit(result.returncode)

    exe_path = os.path.join(OUTPUT_APP_DIR, "FacebookNotification.exe")
    if os.path.exists(exe_path):
        # Ensure .version exists in both root and _internal
        version_file = os.path.join(PROJECT_ROOT, ".version")
        internal_dir = os.path.join(OUTPUT_APP_DIR, "_internal")

        if os.path.exists(version_file):
            shutil.copy2(version_file, os.path.join(OUTPUT_APP_DIR, ".version"))
            if os.path.exists(internal_dir):
                shutil.copy2(version_file, os.path.join(internal_dir, ".version"))

        print("\n" + "=" * 60)
        print("✅ [Build] ĐÓNG GÓI THÀNH CÔNG!")
        print(f"📍 Thư mục ứng dụng: {OUTPUT_APP_DIR}")
        print(f"📍 File thực thi: {exe_path}")
        print("💡 Người dùng có thể copy thư mục này sang bất kỳ máy tính Windows nào và chạy trực tiếp mà không cần cài đặt Python.")
        print("=" * 60)
    else:
        print(f"\n⚠️ [Build] Build completed but executable not found at: {exe_path}")


if __name__ == "__main__":
    build()
