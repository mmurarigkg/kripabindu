; Установщик Krpa Bindu 1.0
; Inno Setup 7
; Интерфейс установщика: русский / English

#define MyAppName "Krpa Bindu"
#define MyAppVersion "1.0"
#define MyAppExeName "Krpabindu.exe"
#define MyAppPublisher "Madhava-Murari dasa GKG"

[Setup]
AppId={{8B7A8E8D-5E8A-4A8D-9C8E-2A0A1B7F4D11}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\Krpabindu
DefaultGroupName={#MyAppName}
OutputDir=installer
OutputBaseFilename=Krpabindu_Setup
SetupIconFile=resources\krpabindu.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2
SolidCompression=yes
DisableProgramGroupPage=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Uninstallable=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Основная программа
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

; Устанавливаемые ресурсы приложения
Source: "assets\*"; DestDir: "{app}\assets"; Flags: recursesubdirs createallsubdirs ignoreversion

; База цитат
Source: "data\quotes.json"; DestDir: "{app}\data"; Flags: ignoreversion

; Фотографии
Source: "data\photos\*"; DestDir: "{app}\data\photos"; Flags: recursesubdirs createallsubdirs ignoreversion

; Аудиофайлы
Source: "data\*"; DestDir: "{app}\data\"; Flags: recursesubdirs createallsubdirs ignoreversion

; Текстовые файлы данных (если присутствуют)
Source: "data\*.txt"; DestDir: "{app}\data"; Flags: ignoreversion skipifsourcedoesntexist
Source: "data\*.md"; DestDir: "{app}\data"; Flags: ignoreversion skipifsourcedoesntexist

; Документация
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; Пользовательские data/logs здесь НЕ создаются: приложение пишет их в %LOCALAPPDATA%\KrpaBindu.
Name: "{app}\data\photos"
Name: "{app}\data\audio"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
