; Inno Setup script for NineLives - builds dist\NineLives-Setup.exe
; Bundles the PyInstaller output (which already includes hashcat + wordlists).
; Compile:  iscc installer.iss   (after build_windows.ps1 produced dist\NineLives)

#define AppName "NineLives"
#define AppVersion "0.2.8"
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

[Files]
; Ship the entire PyInstaller onedir output (app + vendor\hashcat + vendor\wordlists).
Source: "dist\NineLives\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
