#ifndef AppVersion
  #error AppVersion must be passed by Build-Installer.ps1
#endif
#ifndef PayloadDir
  #error PayloadDir must point to the verified portable package
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif
#ifndef AppIdValue
  #define AppIdValue "{1C35DA89-E657-4DD0-AEAA-EE63E6745D23}"
#endif
#ifndef DisplayName
  #define DisplayName "GhostData"
#endif

[Setup]
AppId={{#AppIdValue}
AppName={#DisplayName}
AppVersion={#AppVersion}
AppVerName={#DisplayName} Phantom - Beta 1 ({#AppVersion})
AppPublisher=LoyalLambChops
AppPublisherURL=https://loyallambchops.github.io/ghostdata-site/
AppSupportURL=mailto:LoyalLambChops@gmail.com
DefaultDirName={localappdata}\Programs\{#DisplayName}
DefaultGroupName={#DisplayName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0.22000
OutputDir={#OutputDir}
OutputBaseFilename=GhostData-Setup-{#AppVersion}-x64
SetupIconFile=..\app\GhostData.App\Assets\GhostData.ico
UninstallDisplayIcon={app}\app\GhostData.App.exe
UninstallFilesDir={app}\maintenance
WizardStyle=modern
Compression=lzma2
SolidCompression=yes
AppMutex=Local\GhostData.App
SetupMutex=Local\GhostData.Setup
CloseApplications=no
RestartApplications=no
UsePreviousTasks=yes
InfoBeforeFile=INSTALL_INFO.txt

[Tasks]
Name: "desktopicon"; Description: "Create a &Desktop shortcut"; GroupDescription: "Shortcuts:"; Flags: unchecked

[Files]
Source: "{#PayloadDir}\*"; DestDir: "{app}\app"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#DisplayName}"; Filename: "{app}\app\GhostData.App.exe"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\GhostData.App.exe"
Name: "{autodesktop}\{#DisplayName}"; Filename: "{app}\app\GhostData.App.exe"; WorkingDir: "{app}\app"; IconFilename: "{app}\app\GhostData.App.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\app\GhostData.App.exe"; WorkingDir: "{app}\app"; Description: "Launch GhostData"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: files; Name: "{app}\ghostdata-install.json"
; Only recursively remove a payload that passed inventory/hash verification.
; Unknown files placed here by the user are preserved.
Type: filesandordirs; Name: "{app}\app"; Check: CanRemovePayload

[Code]
var
  MovedPrevious, InstallCompleted, RemovePayload: Boolean;

function VerifyPayload(const Root: String): Boolean;
var ExitCode: Integer;
begin
  Result := FileExists(Root + '\ghostdata-release.json') and
    Exec(Root + '\python\python.exe', '-B "' + Root + '\ghostdata.py" --verify-release "' + Root + '"',
      Root, SW_HIDE, ewWaitUntilTerminated, ExitCode) and (ExitCode = 0);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var Root, Backup: String;
begin
  Result := '';
  Root := ExpandConstant('{app}');
  Backup := Root + '\.previous-package';
  if FileExists(Root + '\GhostData.App.exe') then begin
    Result := 'This folder contains a portable copy. Choose a separate installation folder; your existing match history will still be used.';
    exit;
  end;
  if DirExists(Backup) then begin
    Result := 'An earlier installation backup requires recovery: ' + Backup;
    exit;
  end;
  if DirExists(Root + '\app') then begin
    if not FileExists(Root + '\ghostdata-install.json') or not VerifyPayload(Root + '\app') then begin
      Result := 'This folder is not a verified GhostData installation, or its app files were modified. Choose an empty folder. No match history will be removed.';
      exit;
    end;
    MovedPrevious := RenameFile(Root + '\app', Backup);
    if not MovedPrevious then
      Result := 'Could not prepare the existing app for upgrade. Close GhostData and retry.';
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var Marker: String;
begin
  if CurStep = ssPostInstall then begin
    if not VerifyPayload(ExpandConstant('{app}\app')) then
      RaiseException('Installed app verification failed.');
    Marker := '{"product":"GhostData","schema_version":1,"payload":"app","app_id":"{#AppIdValue}"}';
    if not SaveStringToFile(ExpandConstant('{app}\ghostdata-install.json'), Marker, False) then
      RaiseException('Could not write installation identity.');
  end;
  if CurStep = ssDone then begin
    InstallCompleted := True;
    if MovedPrevious and not DelTree(ExpandConstant('{app}\.previous-package'), True, True, True) then
      Log('The previous verified package could not be removed.');
  end;
end;

procedure DeinitializeSetup();
begin
  if MovedPrevious and not InstallCompleted then begin
    DelTree(ExpandConstant('{app}\app'), True, True, True);
    if not RenameFile(ExpandConstant('{app}\.previous-package'), ExpandConstant('{app}\app')) then
      MsgBox('The previous app is preserved in .previous-package but could not be restored automatically.', mbError, MB_OK);
  end;
end;

function InitializeUninstall(): Boolean;
begin
  RemovePayload := VerifyPayload(ExpandConstant('{app}\app'));
  Result := True;
end;

function CanRemovePayload(): Boolean;
begin
  Result := RemovePayload;
end;
