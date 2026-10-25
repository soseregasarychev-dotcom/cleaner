; Установщик Уборщика (Inno Setup 6). Собирается скриптом scripts\installer.ps1.
; Ставится без прав администратора в %LOCALAPPDATA%\Programs\Uborshchik.

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#define AppName "Уборщик"
#define AppExe "Уборщик.exe"
#define Root ".."

[Setup]
AppId={{6E1B3C2A-8F4D-4B7A-9C51-0D2E7A4F9B13}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Сергей Сарычев
DefaultDirName={localappdata}\Programs\Uborshchik
DisableDirPage=yes
DisableProgramGroupPage=yes
DisableReadyPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#Root}\dist
OutputBaseFilename=Уборщик-Setup-{#AppVersion}
SetupIconFile={#Root}\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
WizardImageFile={#Root}\assets\wizard_big_0.bmp,{#Root}\assets\wizard_big_1.bmp,{#Root}\assets\wizard_big_2.bmp
WizardSmallImageFile={#Root}\assets\wizard_small_0.bmp,{#Root}\assets\wizard_small_1.bmp,{#Root}\assets\wizard_small_2.bmp
Compression=lzma2/ultra64
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Messages]
russian.WelcomeLabel1=Прораб Уборщик заступает на объект
russian.WelcomeLabel2=Уборщик наводит порядок на рабочем столе: уносит файлы в архив с датой, чистит Загрузки, временные файлы, корзину и мусор AutoCAD/Revit.%n%nПервая уборка — только после вашего согласия, по смете. Облака (Яндекс Диск, OneDrive, Google Диск) не трогаю никогда.%n%nНажмите «Далее», чтобы начать монтаж.
russian.FinishedHeadingLabel=Объект сдан!
russian.FinishedLabelNoIcons=Уборщик установлен и живёт в трее (у часов). Начните с раздела «Охранные зоны» — обведите на столе место, которое трогать нельзя.

[Tasks]
Name: "desktopicon"; Description: "Ярлык на рабочем столе"; Flags: unchecked

[Files]
Source: "{#Root}\dist\Uborshchik\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{userprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "Порядок на рабочем столе"
Name: "{userdesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "Запустить Уборщик"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Настройки и журнал. Архив на рабочем столе — это файлы пользователя, его не трогаем.
Type: filesandordirs; Name: "{userappdata}\Uborshchik"

[Code]
procedure StopApp();
var
  Code: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im "{#AppExe}"', '', SW_HIDE,
    ewWaitUntilTerminated, Code);
  Sleep(400);
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  StopApp();
  Result := '';
end;

function InitializeUninstall(): Boolean;
begin
  StopApp();
  Result := True;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    // Убрать из автозапуска (программа прописывает себя сама)
    RegDeleteValue(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Run', 'Uborshchik');
end;
