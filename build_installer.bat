@echo off
chcp 65001 > nul

rem Đọc phiên bản từ tệp .version
set "APP_VERSION=1.0.1"
if exist .version (
    set /p APP_VERSION=<.version
)

echo ========================================================
echo   BUILD INSTALLER - FACEBOOK NOTIFICATION SCRAPER v%APP_VERSION%
echo ========================================================
echo.

echo [1/2] Đang đóng gói ứng dụng với PyInstaller...
python -m PyInstaller --noconfirm facebook_notification.spec

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PyInstaller build failed!
    pause
    exit /b %ERRORLEVEL%
)

echo.
echo [2/2] Đang tạo bộ cài đặt Installer với Inno Setup...
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DMyAppVersion=%APP_VERSION% installer\setup.iss
    if %ERRORLEVEL% NEQ 0 (
        echo [ERROR] Inno Setup compilation failed!
        pause
        exit /b %ERRORLEVEL%
    )
) else (
    echo [ERROR] Không tìm thấy Inno Setup tại 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'!
    pause
    exit /b 1
)

echo.
echo ========================================================
echo   BUILD THÀNH CÔNG!
echo   File cài đặt: dist\FacebookNotification_Setup_v%APP_VERSION%.exe
echo ========================================================
pause
