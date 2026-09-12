; Huawei Document Generator Windows installer (Inno Setup 6)
; Built by scripts/package_installer.py — do not edit generated values by hand.

#define AppName "文档生成工作台"
#define AppPublisher "Huawei"
#ifndef AppVersion
  #define AppVersion "2.2.0"
#endif
#ifndef SourceDir
  #define SourceDir "dist\\document-workbench-windows-x64-" + AppVersion
#endif
#ifndef OutputDir
  #define OutputDir "dist"
#endif

[Setup]
AppId={{7E8D9A3B-1F4C-4E2A-9B6D-5C8A1F3E2D7B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\HuaweiDocumentGenerator\{#AppVersion}
DefaultGroupName={#AppName}
OutputDir={#OutputDir}
OutputBaseFilename=HuaweiDocumentGenerator-Setup-{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
ShowLanguageDialog=yes
UninstallDisplayIcon={app}\DocumentWorkbench.exe
UninstallDisplayName={#AppName} {#AppVersion}
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; SigntoolOptions is intentionally not set until intranet code-signing cert is available.

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\DocumentWorkbench.exe"; WorkingDir: "{app}"; IconFilename: "{app}\DocumentWorkbench.exe"
Name: "{group}\卸载 {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\DocumentWorkbench.exe"; WorkingDir: "{app}"; IconFilename: "{app}\DocumentWorkbench.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DocumentWorkbench.exe"; Description: "立即运行 {#AppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"
; settings.json / jobs / credentials in %LOCALAPPDATA%\HuaweiDocumentGenerator are preserved across upgrades/uninstalls.
