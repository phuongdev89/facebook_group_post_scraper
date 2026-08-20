#!/usr/bin/env bash
# ========================================================
#   BUILD PATCH UPDATE - FACEBOOK NOTIFICATION SCRAPER
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
echo "  BUILD PATCH UPDATE - FACEBOOK NOTIFICATION v${APP_VERSION}"
echo "========================================================"
echo ""

echo "[1/3] Đang đóng gói phiên bản mới nhất với PyInstaller..."
"$PYTHON_BIN" -m PyInstaller --noconfirm facebook_notification.spec

echo ""
echo "[2/3] Đang tạo bộ cài đặt Patch tự động với Inno Setup..."
ISCC_PATH=""
for p in "/mnt/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "/c/Program Files (x86)/Inno Setup 6/ISCC.exe" "C:/Program Files (x86)/Inno Setup 6/ISCC.exe"; do
    if [ -f "$p" ]; then
        ISCC_PATH="$p"
        break
    fi
done

if [ -n "$ISCC_PATH" ]; then
    "$ISCC_PATH" installer/patch.iss
    echo "[OK] Đã tạo file Patch EXE thành công!"
else
    echo "[SKIP] Không tìm thấy Inno Setup tại 'C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe'."
fi

echo ""
echo "[3/3] Đang đóng gói file nén Patch Portable (.zip)..."
"$PYTHON_BIN" scripts/create_patch_zip.py

echo ""
echo "========================================================"
echo "  BUILD PATCH HOÀN TẤT THÀNH CÔNG!"
echo "========================================================"
echo "  Phiên bản: v${APP_VERSION}"
echo ""
echo "  1. File Patch EXE (Khách nhấp đúp để tự động nâng cấp):"
echo "     dist/FacebookNotification_Patch_v${APP_VERSION}.exe"
echo ""
echo "  2. File Patch ZIP (Khách giải nén đè thủ công):"
echo "     dist/FacebookNotification_Patch_v${APP_VERSION}.zip"
echo "========================================================"
echo ""
