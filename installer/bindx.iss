; BindX installer script (Inno Setup 6).
;
; Produces bindx-setup.exe: a user-level installer that also serves as the
; silent-update payload for installed deployments
; (/VERYSILENT /SUPPRESSMSGBOXES /NORESTART).
;
; CI build:   iscc /DMyAppVersion=<ver> installer\bindx.iss   (bindx.exe must sit next to this script)
; Local build: iscc installer\bindx.iss

#ifndef MyAppVersion
  #define MyAppVersion "2.1.0"
#endif
#define MyAppName "BindX"
#define MyAppPublisher "GOTOgxy"
#define MyAppURL "https://github.com/GOTOgxy/BindX"
#define MyAppExeName "bindx.exe"

[Setup]
AppId=BindX
AppName={#MyAppName}
AppVersion={#MyAppVersion}
VersionInfoVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
; User-level install: no admin rights, no UAC prompt, silent updates stay unprivileged.
DefaultDirName={localappdata}\Programs\BindX
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=bindx-setup
SetupIconFile=..\src-tauri\icons\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
; BindX is stopped explicitly in [Code]; let the Restart Manager stay out of it.
CloseApplications=false
RestartApplications=false

[Languages]
Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "开机时自动启动 {#MyAppName}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "bindx.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Opt-in autostart. uninsdeletevalue cleans it on uninstall; silent upgrades never
; touch it because the task defaults to unchecked and Inno only writes when checked.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Code]
// Stop a running BindX so its executable can be replaced.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  RC: LongInt;
begin
  Exec('taskkill', '/IM {#MyAppExeName} /F', '', SW_HIDE, ewWaitUntilTerminated, RC);
  Result := '';
end;

// Silent upgrade: relaunch the app once the new files are in place,
// so the user ends up exactly where they were before updating.
procedure CurStepChanged(CurStep: TSetupStep);
var
  RC: LongInt;
begin
  if (CurStep = ssPostInstall) and WizardSilent then
    Exec(ExpandConstant('{app}\{#MyAppExeName}'), '', ExpandConstant('{app}'), SW_SHOWNORMAL, ewNoWait, RC);
end;

// Interactive uninstall: offer to remove the user config (%APPDATA%\BindX).
// Silent uninstalls never delete user data.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  ConfigDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then begin
    ConfigDir := ExpandConstant('{userappdata}\{#MyAppName}');
    if DirExists(ConfigDir) then
      if MsgBox('是否同时删除 BindX 的配置文件与数据？' + #13#10 + ConfigDir, mbConfirmation, MB_YESNO) = IDYES then
        DelTree(ConfigDir, True, True, True);
  end;
end;
