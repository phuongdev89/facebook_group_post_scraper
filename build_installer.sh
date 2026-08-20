#!/usr/bin/env bash
# ========================================================
#   BUILD FULL INSTALLER - FACEBOOK NOTIFICATION SCRAPER
# ========================================================

set -e

# Tìm Windows Python binary
PYTHON_BIN="python.exe"
if ! command -v "$PYTHON_BIN" &> /dev/null; then
    if command -v py &> /dev/null; then
        PYTHON_BIN="py"
    elif command -v python &> /dev/null; then
        PYTHON_BIN="python"
    elif [ -f "/mnt/c/Users/Windows/AppData/Local/Programs/Python/Python313/python.exe" ]; then
        PYTHON_BIN="/mnt/c/Users/Windows/AppData/Local/Programs/Python/Python313/python.exe"
    else
        PYTHON_BIN="C:/Users/Windows/AppData/Local/Programs/Python/Python313/python.exe"
    fi
fi

# Đọc phiên bản từ tệp .version
APP_VERSION="1.0.1"
if [ -f ".version" ]; then
    APP_VERSION=$(tr -d '\r\n' < .version)
fi

echo "========================================================"
echo "  BUILD INSTALLER - FACEBOOK NOTIFICATION v${APP_VERSION}"
echo "========================================================"
echo ""

echo "[1/2] Đang đóng gói ứng dụng với PyInstaller..."
"$PYTHON_BIN" -m PyInstaller --noconfirm facebook_notification.spec

echo ""
echo "[2/2] Đang tạo bộ cài đặt Installer với Inno Setup..."
ISCC_PATH=""
for p in "/mnt/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "C:/Program Files (x86)/Inno Setup 6/ISCC.exe"; do
    if [ -f "$p" ]; then
        ISCC_PATH="$p"
        break
    fi
done

if [ -n "$ISCC_PATH" ]; then
    "$ISCC_PATH" installer/setup.iss
    echo "[OK] Đã tạo file Installer EXE thành công!"
else
    echo "[ERROR] Không tìm thấy Inno Setup tại 'C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe'!"
    exit 1
fi

echo ""
echo "========================================================"
echo "  BUILD INSTALLER HOÀN TẤT THÀNH CÔNG!"
echo "  File cài đặt: dist/FacebookNotification_Setup_v${APP_VERSION}.exe"
echo "========================================================"
echo ""
