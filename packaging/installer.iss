; Inno Setup script for ThaiVoice
; Compile: ISCC.exe packaging\installer.iss
; Or run: packaging\build_installer.bat (after scripts\build.bat produced dist\ThaiVoice.exe)
; All source paths in this file are relative to packaging/ (the .iss location).

#define AppName        "ThaiVoice"
#define AppVersion     "0.1.0"
#define AppPublisher   "nrathpluk"
#define AppURL         "https://github.com/nrathpluk/VoiceInk"
#define AppExeName     "ThaiVoice.exe"

[Setup]
AppId={{4F2A1B6E-9E31-4F4B-9F4D-1A5E0C2A8E11}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases
DefaultDirName={userappdata}\..\Local\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=ThaiVoice-Setup-{#AppVersion}
SetupIconFile=icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#AppExeName}
CloseApplications=force
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
; Thai language file isn't shipped with stock Inno; English-only for now.

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startmenuicon"; Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "..\dist\{#AppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\LICENSE"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove the per-user log + config on uninstall.
; %LOCALAPPDATA%\ThaiVoice and %APPDATA%\ThaiVoice
Type: filesandordirs; Name: "{userappdata}\..\Local\{#AppName}"
Type: filesandordirs; Name: "{userappdata}\{#AppName}"
