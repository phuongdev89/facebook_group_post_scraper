; Facebook Notification & Scraper Patch / Update Script (Lightweight Patch)
; Chỉ ghi đè mã nguồn ứng dụng (src), file exe và tài liệu hướng dẫn (guides)
; Không ghi đè các file DLL thư viện nặng của Qt/Python => Dung lượng siêu nhẹ

#define MyAppName "Facebook Notification & Scraper"

#ifndef MyAppVersion
  #if FileExists(AddBackslash(SourcePath) + "..\.version")
    #define FileHandle FileOpen(AddBackslash(SourcePath) + "..\.version")
    #define MyAppVersion Trim(FileRead(FileHandle))
    #expr FileClose(FileHandle)
  #else
    #define MyAppVersion "1.0.1"
  #endif
#endif

#define MyAppPublisher "PhuongDev"
#define MyAppURL "https://gitlab.com/phuongdev89/facebook_post_comment_scraper"
#define MyAppExeName "FacebookNotification.exe"

[Setup]
; AppId phải khớp chính xác với AppId của bộ cài đặt chính (setup.iss)
AppId={{8E47D63A-9F22-4D39-9B9B-89A82D6E3F41}
AppName={#MyAppName} (Patch Update)
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Tự động tìm thư mục đã cài đặt trước đó từ Registry
DefaultDirName={autopf}\FacebookNotification
DefaultGroupName={#MyAppName}
UsePreviousAppDir=yes
CreateUninstallRegKey=no
UpdateUninstallLogAppName=no

OutputDir=..\dist
OutputBaseFilename=FacebookNotification_Patch_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequiredOverridesAllowed=dialog commandline
PrivilegesRequired=lowest
DisableProgramGroupPage=yes
DisableDirPage=auto

; Tự động yêu cầu đóng ứng dụng nếu đang chạy ngầm trước khi cập nhật
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Ghi đè file exe khởi chạy
Source: "..\dist\FacebookNotification\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Ghi đè file version
Source: "..\.version"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\.version"; DestDir: "{app}\_internal"; Flags: ignoreversion
; Ghi đè toàn bộ mã nguồn và bytecode của ứng dụng (src)
Source: "..\dist\FacebookNotification\_internal\src\*"; DestDir: "{app}\_internal\src"; Flags: ignoreversion recursesubdirs createallsubdirs
; Ghi đè tài liệu hướng dẫn sử dụng mới nhất
Source: "..\guides\*"; DestDir: "{app}\guides"; Flags: ignoreversion recursesubdirs createallsubdirs

[Run]
; Khởi động lại ứng dụng sau khi patch xong (tùy chọn)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
