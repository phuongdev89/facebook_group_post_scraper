@echo off
chcp 65001 > nul

rem Đọc phiên bản từ tệp .version
set "APP_VERSION=1.0.1"
if exist .version (
    set /p APP_VERSION=<.version
)

echo ========================================================
echo   BUILD PATCH UPDATE - FACEBOOK NOTIFICATION SCRAPER v%APP_VERSION%
echo ========================================================
echo.

echo [1/3] Đang đóng gói phiên bản mới nhất với PyInstaller...
python -m PyInstaller --noconfirm facebook_notification.spec

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] PyInstaller build thất bại!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/3] Đang tạo bộ cài đặt Patch tự động với Inno Setup...
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=%APP_VERSION% installer\patch.iss
    if %ERRORLEVEL% NEQ 0 (
        echo [WARNING] Inno Setup compilation gặp lỗi!
    ) else (
        echo [OK] Đã tạo file Patch EXE thành công!
    )
) else (
    echo [SKIP] Không tìm thấy Inno Setup tại 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'.
)

echo.
echo [3/3] Đang đóng gói file nén Patch Portable (.zip)...
python scripts\create_patch_zip.py

echo.
echo ========================================================
echo   BUILD PATCH HOÀN TẤT THÀNH CÔNG!
echo ========================================================
echo   Phiên bản: v%APP_VERSION%
echo.
echo   1. File Patch EXE (Khách nhấp đúp để tự động nâng cấp):
echo      dist\FacebookNotification_Patch_v%APP_VERSION%.exe
echo.
echo   2. File Patch ZIP (Khách giải nén đè thủ công):
echo      dist\FacebookNotification_Patch_v%APP_VERSION%.zip
echo ========================================================
echo.
pause
