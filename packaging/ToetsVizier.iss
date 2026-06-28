#define MyAppId "{{E55D8EE5-4370-4C66-B0AF-1489A3B6169E}}"
#define MyAppName "ToetsVizier"
#define MyAppPublisher "Tom Sommers"

#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#ifndef SourceDir
  #error SourceDir ontbreekt
#endif
#ifndef OutputDir
  #error OutputDir ontbreekt
#endif
#ifndef OutputBaseFilename
  #define OutputBaseFilename "ToetsVizier-windows-installer"
#endif
#ifndef SetupIconFile
  #define SetupIconFile ""
#endif

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\ToetsVizier
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ChangesAssociations=no
CloseApplications=yes
CloseApplicationsFilter=ToetsVizier.exe
RestartApplications=no
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
UninstallDisplayIcon={app}\ToetsVizier.exe
SetupIconFile={#SetupIconFile}

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "Bureaubladsnelkoppeling maken"; GroupDescription: "Extra snelkoppelingen:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\ToetsVizier"; Filename: "{app}\ToetsVizier.exe"; IconFilename: "{app}\ToetsVizier.ico"
Name: "{autodesktop}\ToetsVizier"; Filename: "{app}\ToetsVizier.exe"; IconFilename: "{app}\ToetsVizier.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\ToetsVizier.exe"; Description: "ToetsVizier starten"; Flags: nowait postinstall skipifsilent
