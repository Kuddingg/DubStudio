; Bộ cài DubStudio (Inno Setup 6). Build: ISCC.exe packaging\installer.iss
; Cài cho người dùng hiện tại (không cần quyền admin); dữ liệu người dùng nằm ở %LOCALAPPDATA%\DubStudio.

#define AppName "DubStudio"
; Số phiên bản do build.bat truyền vào (/DAppVersion=...) từ core\version.py
#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{6D2B6F0A-6E8B-4C3E-9C2B-2F7C1D9E4A11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=DubStudio
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\build\installer
OutputBaseFilename=DubStudio-Setup-{#AppVersion}
SetupIconFile=dubstudio.ico
UninstallDisplayIcon={app}\DubStudio.exe
Compression=lzma2/normal
SolidCompression=no
DiskSpanning=no
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
; Cập nhật từ trong app: bộ cài tự đóng DubStudio đang chạy để thay file
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Tạo biểu tượng ngoài màn hình (Desktop)"; GroupDescription: "Tùy chọn:"

[Files]
Source: "..\build\dist\DubStudio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\DubStudio.exe"
Name: "{group}\Gỡ cài đặt {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DubStudio.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DubStudio.exe"; Description: "Mở {#AppName}"; Flags: nowait postinstall skipifsilent
; Cập nhật từ trong app (chạy bộ cài với /SILENT) → cài xong tự mở lại app
Filename: "{app}\DubStudio.exe"; Flags: nowait; Check: WizardSilent
