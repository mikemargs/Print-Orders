#define MyAppName "Print Order Manager Multi-Store"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Print Operations"
#define MyAppExeName "PrintOrderManager-MultiStore.exe"

[Setup]
AppId={{B50F4B04-846B-42D9-9D0E-93EC9879EF6B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Print Order Manager Multi-Store
DefaultGroupName={#MyAppName}
OutputDir=output
OutputBaseFilename=PrintOrderManager-MultiStore-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\client\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

