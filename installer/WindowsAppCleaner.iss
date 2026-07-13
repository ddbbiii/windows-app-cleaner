#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif
#ifndef PublishDir
  #define PublishDir "..\artifacts\publish"
#endif

[Setup]
AppId={{7B181148-BC06-43FB-B318-C957CA5DE209}
AppName=Windows 应用清理器
AppVersion={#AppVersion}
AppPublisher=ddbbiii
DefaultDirName={localappdata}\Programs\WindowsAppCleaner
DefaultGroupName=Windows 应用清理器
PrivilegesRequired=lowest
OutputDir=..\artifacts
OutputBaseFilename=WindowsAppCleaner-{#AppVersion}-Setup-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\WindowsAppCleaner.exe
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#PublishDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Windows 应用清理器"; Filename: "{app}\WindowsAppCleaner.exe"
Name: "{userdesktop}\Windows 应用清理器"; Filename: "{app}\WindowsAppCleaner.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加选项:"; Flags: unchecked

[Run]
Filename: "{app}\WindowsAppCleaner.exe"; Description: "启动 Windows 应用清理器"; Flags: nowait postinstall skipifsilent
