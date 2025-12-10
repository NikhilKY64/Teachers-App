; Inno Setup Installer Script for Teachers App (Teacher Timetable App)

[Setup]
AppName=Teachers App
AppVersion=1.5.1
AppPublisher=Nikhil Yadav XI-E (2025-26)
AppPublisherURL=https://github.com/NikhilKY64/Teachers-App/tree/App-v1.5.1
DefaultDirName=C:\Teachers App
DefaultGroupName=Teachers App
SetupIconFile=Icon-Setup.ico
OutputDir=Output
OutputBaseFilename=TeacherAppSetup
Compression=lzma
SolidCompression=yes

; --- Version info of installer EXE ---
VersionInfoVersion=1.5.1
VersionInfoProductVersion=1.5.1
VersionInfoDescription=Teachers App Setup
VersionInfoProductName=Teachers App
VersionInfoCompany=Nikhil Yadav XI-E (2025-26)
VersionInfoOriginalFileName=TeachersAppSetup.exe
; -------------------------------------

[Files]
; 1) Install database.db and NEVER remove it automatically on uninstall
;    (we will ask user during uninstall and delete it manually if they choose so)
Source: "dist\Teachers App\database.db"; DestDir: "{app}"; Flags: ignoreversion uninsneveruninstall

; 2) Install all other app files except database.db
Source: "dist\Teachers App\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs; Excludes: "database.db"

; 3) Sample Excel files (optional task)
Source: "Samples\sample_timetable.xlsx"; DestDir: "{commondesktop}\Teachers App Samples"; Flags: ignoreversion; Tasks: samples
Source: "Samples\Sample_Teacher_details.xlsx"; DestDir: "{commondesktop}\Teachers App Samples"; Flags: ignoreversion; Tasks: samples

[Icons]
Name: "{group}\Teachers App"; Filename: "{app}\Teachers App.exe"
Name: "{commondesktop}\Teachers App"; Filename: "{app}\Teachers App.exe"; Tasks: desktopicon
Name: "{group}\Open Sample Excel Files"; Filename: "{commondesktop}\Teachers App Samples"; Tasks: samples

[Tasks]
Name: "desktopicon"; Description: "Create Desktop Shortcut"; GroupDescription: "Additional options:"
Name: "samples"; Description: "Install Sample Excel Files on Desktop"; GroupDescription: "Additional options:"

[Run]
Filename: "{app}\Teachers App.exe"; Description: "Launch Teachers App"; Flags: nowait postinstall skipifsilent

[Code]

var
  UseExistingDbPage: TInputOptionWizardPage;
  ExistingDbPage: TInputFileWizardPage;
  ExistingDbPath: string;
  DeleteDatabaseOnUninstall: Boolean;

{======================== INSTALL WIZARD ========================}

procedure InitializeWizard;
begin
  { Ask if the user has an existing database file }
  UseExistingDbPage :=
    CreateInputOptionPage(
      wpSelectTasks,
      'Existing Data',
      'Use an existing database?',
      'If you already have a previous database file or a backup created by Teachers App,'#13#10 +
      'you can use it with this installation.',
      True,
      False
    );

  UseExistingDbPage.Add('Yes, I have an existing database file and want to use it');
  UseExistingDbPage.Add('No, start with a new empty database');
  UseExistingDbPage.SelectedValueIndex := 0;  { default: Yes }

  { Page to select the existing database file (only if user chose Yes) }
  ExistingDbPage :=
    CreateInputFilePage(
      UseExistingDbPage.ID,
      'Select your existing database file',
      'Choose your data file',
      'Select your existing "database.db" file or a backup file like:'#13#10 +
      '"database_bkp_YYYY-MM-DD_HH-MM.db".'#13#10 +
      'The installer will restore it as "database.db".'#13#10#13#10 +
      'Tip: Backup file are also supported; this will be restored automatically.'
    );

  { This Add signature: Add(Prompt, Filter, DefaultExt) }
  ExistingDbPage.Add(
    'Database or backup file (.db):',
    'Database Files (*.db)|*.db|All Files (*.*)|*.*',
    '.db'
  );
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  { Skip the file selection page if user did NOT choose "Yes" }
  if (PageID = ExistingDbPage.ID) and (UseExistingDbPage.SelectedValueIndex <> 0) then
    Result := True;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  FileName: string;
begin
  Result := True;

  if CurPageID = ExistingDbPage.ID then
  begin
    ExistingDbPath := ExistingDbPage.Values[0];

    if ExistingDbPath = '' then
    begin
      MsgBox(
        'Please select your existing database or backup file, or click Back and choose "No".',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;

    FileName := ExtractFileName(ExistingDbPath);

    { Allowed:
       - database.db
       - database_bkp_*.db  (e.g. database_bkp_2025-12-09_17-30.db)
    }
    if (CompareText(FileName, 'database.db') <> 0) and
       not ((Pos('database_bkp_', LowerCase(FileName)) = 1) and
            (CompareText(ExtractFileExt(FileName), '.db') = 0)) then
    begin
      MsgBox(
        'Invalid file selected.'#13#10 +
        'Allowed files:'#13#10 +
        '  ✔ database.db'#13#10 +
        '  ✔ database_bkp_YYYY-MM-DD_HH-MM.db',
        mbError, MB_OK);
      Result := False;
      Exit;
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssPostInstall) then
  begin
    { If user chose "Yes" and selected a file, restore it as database.db }
    if (UseExistingDbPage.SelectedValueIndex = 0) and
       (ExistingDbPath <> '') then
    begin
      if not FileCopy(ExistingDbPath, ExpandConstant('{app}\database.db'), False) then
        MsgBox('Failed to restore your selected database file.', mbError, MB_OK);
    end;
  end;
end;

{======================== UNINSTALL LOGIC ========================}

function InitializeUninstall(): Boolean;
var
  Res: Integer;
begin
  Result := True;
  DeleteDatabaseOnUninstall := False;

  if FileExists(ExpandConstant('{app}\database.db')) then
  begin
    Res := MsgBox(
      'Your saved timetable data (database.db) was found.'#13#10#13#10 +
      'Do you want to DELETE this file during uninstall?'#13#10 +
      'Choose "No" to keep your saved timetable.',
      mbConfirmation, MB_YESNOCANCEL);

    if Res = IDYES then
      DeleteDatabaseOnUninstall := True
    else if Res = IDCANCEL then
      Result := False;  { cancel uninstall }
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if (CurUninstallStep = usUninstall) and DeleteDatabaseOnUninstall then
    if FileExists(ExpandConstant('{app}\database.db')) then
      DeleteFile(ExpandConstant('{app}\database.db'));
end;
