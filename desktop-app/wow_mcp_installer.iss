#define MyAppName "WoW MCP Companion"
#define MyAppVersion "0.2.0"
#define MyAppPublisher "wow-mcp"
#define MyAppExeName "WowMCP.exe"

[Setup]
AppId={{0A653A9E-7E1A-4B0F-A7CA-38B3A1D3F6B8}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\WowMCP
DefaultGroupName=WoW MCP Companion
DisableProgramGroupPage=yes
LicenseFile=
OutputDir=dist
OutputBaseFilename=WowMCP-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked

[Files]
Source: "dist\WowMCP.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "requirements.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\addon\WowMCP_State\*"; DestDir: "{app}\addon\WowMCP_State"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\addon\WowMCP_Cmd\*"; DestDir: "{app}\addon\WowMCP_Cmd"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release\wow-mcp-friends-bundle\install-addon-windows.ps1"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\WoW MCP Companion"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\WoW MCP Companion"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch WoW MCP Companion"; Flags: nowait postinstall skipifsilent
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\install-addon-windows.ps1"""; Description: "Install WoW addon now"; Flags: postinstall unchecked runhidden
