; Inno Setup script for NineLives - builds dist\NineLives-Setup.exe
; Bundles the PyInstaller output (which already includes hashcat + wordlists).
; Compile:  iscc installer.iss   (after build_windows.ps1 produced dist\NineLives)

#define AppName "NineLives"
#define AppVersion "0.2.9"
#define AppPublisher "Ardyn Systems"
#define AppExe "NineLives.exe"

[Setup]
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=dist
OutputBaseFilename=NineLives-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=brand\ninelives.ico
UninstallDisplayIcon={app}\{#AppExe}
ArchitecturesInstallIn64BitMode=x64compatible
; hashcat + wordlists make this large; allow plenty of headroom.
DiskSpanning=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional icons:"

[InstallDelete]
; On upgrade, clear the previously bundled vendor payload BEFORE copying the new
; one. Inno Setup never deletes files the new version omits, so without this a
; big list dropped by an older build (e.g. the ~133 MB rockyou.txt that newer
; builds no longer bundle) and stale hashcat files would linger forever. The
; user's downloaded wordlists and hashcat updates live under %LOCALAPPDATA%\
; NineLives, NOT here, so they are untouched.
Type: filesandordirs; Name: "{app}\_internal\vendor\wordlists"
Type: filesandordirs; Name: "{app}\_internal\vendor\hashcat"

[Files]
; Ship the entire PyInstaller onedir output (app + vendor\hashcat + vendor\wordlists).
Source: "dist\NineLives\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
