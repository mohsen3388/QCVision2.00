#define MyAppName "VisionQC"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "VisionQC"
#define MyAppExeName "VisionQC.exe"

[Setup]
AppId={{A5314E1B-7D8B-467A-8D40-6173CBBC1F20}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\VisionQC
DefaultGroupName=VisionQC
AllowNoIcons=yes
OutputDir=..\installer
OutputBaseFilename=VisionQC_Setup_1.1.0_Offline
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
PrivilegesRequired=admin
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
VersionInfoVersion=1.1.0.0
VersionInfoProductName=VisionQC
VersionInfoDescription=Industrial Visual Quality Intelligence - Offline Full Installer
VersionInfoCompany=VisionQC
MinVersion=10.0.17763

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\VisionQC\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\prerequisites\VC_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\VisionQC"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\VisionQC User Guide"; Filename: "{app}\README.md"
Name: "{autodesktop}\VisionQC"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{tmp}\VC_redist.x64.exe"; Parameters: "/install /quiet /norestart"; StatusMsg: "Installing Microsoft Visual C++ runtime..."; Flags: waituntilterminated; Check: VCRuntimeInstallNeeded
Filename: "{app}\{#MyAppExeName}"; Description: "Launch VisionQC"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
function VCRuntimeInstallNeeded: Boolean;
var
  Installed: Cardinal;
begin
  Result := True;
  if RegQueryDWordValue(HKLM64, 'SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64', 'Installed', Installed) then
    Result := Installed <> 1;
end;

function InitializeSetup(): Boolean;
begin
  if not IsWin64 then begin
    MsgBox('VisionQC requires 64-bit Windows 10 or Windows 11.', mbCriticalError, MB_OK);
    Result := False;
    exit;
  end;
  Result := True;
end;

function InitializeUninstall(): Boolean;
begin
  MsgBox('VisionQC production data is stored separately in the user LocalAppData folder and will not be removed by this uninstaller.', mbInformation, MB_OK);
  Result := True;
end;
