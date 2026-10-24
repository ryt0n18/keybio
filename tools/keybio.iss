; Asistente de instalación de KeyBio para Windows (Inno Setup 6).
; Lo genera la integración continua o se crea a mano después de "tools\build.bat":
;   ISCC.exe /DAppVersion=2.1.1 tools\keybio.iss
; Instala el programa ya empaquetado (no hace falta Python) y muestra la licencia, que build.py
; deja en build\licenses. Los perfiles se guardan en
; %APPDATA%\KeyBio; al desinstalar se pregunta si se quieren borrar.

#define AppName "KeyBio"
#ifndef AppVersion
  #define AppVersion "2.1.1"
#endif

[Setup]
AppId={{23A5C63C-1D14-4618-B5E8-D7290C6B9F1E}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Álvaro Ruiz (ryt0n18)
AppCopyright=© 2026 Álvaro Ruiz (ryt0n18). Todos los derechos reservados.
LicenseFile=..\build\licenses\KeyBio-LICENCIA.txt
AppComments=Biometría de la dinámica de tecleo
VersionInfoVersion={#AppVersion}
VersionInfoDescription=Instalador de {#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=..\dist
OutputBaseFilename=KeyBio-{#AppVersion}-setup
SetupIconFile=..\build\icon\keybio.ico
UninstallDisplayIcon={app}\KeyBio.exe
UninstallDisplayName={#AppName} {#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "catalan"; MessagesFile: "compiler:Languages\Catalan.isl"
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "portuguese"; MessagesFile: "compiler:Languages\Portuguese.isl"
Name: "german"; MessagesFile: "compiler:Languages\German.isl"
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[CustomMessages]
spanish.DeleteData=¿Quieres borrar también los perfiles biométricos, el historial y los ajustes de KeyBio?%n%nCarpeta: %1%n%nSi eliges «No», se conservan por si vuelves a instalar el programa.
english.DeleteData=Do you also want to delete the KeyBio biometric profiles, history and settings?%n%nFolder: %1%n%nChoose "No" to keep them in case you reinstall the program.
catalan.DeleteData=Vols esborrar també els perfils biomètrics, l'historial i la configuració de KeyBio?%n%nCarpeta: %1%n%nSi tries «No», es conserven per si tornes a instal·lar el programa.
french.DeleteData=Voulez-vous aussi supprimer les profils biométriques, l'historique et les réglages de KeyBio ?%n%nDossier : %1%n%nSi vous choisissez « Non », ils seront conservés au cas où vous réinstalleriez le programme.
portuguese.DeleteData=Queres apagar também os perfis biométricos, o histórico e as definições do KeyBio?%n%nPasta: %1%n%nSe escolheres «Não», são conservados para o caso de voltares a instalar o programa.
german.DeleteData=Möchtest du auch die biometrischen Profile, den Verlauf und die Einstellungen von KeyBio löschen?%n%nOrdner: %1%n%nWenn du „Nein“ wählst, bleiben sie erhalten, falls du das Programm erneut installierst.
italian.DeleteData=Vuoi eliminare anche i profili biometrici, la cronologia e le impostazioni di KeyBio?%n%nCartella: %1%n%nSe scegli «No», vengono conservati nel caso tu reinstalli il programma.
spanish.AppDescription=Biometría de la dinámica de tecleo
english.AppDescription=Keystroke dynamics biometrics
catalan.AppDescription=Biometria de la dinàmica de tecleig
french.AppDescription=Biométrie de la dynamique de frappe
portuguese.AppDescription=Biometria da dinâmica de digitação
german.AppDescription=Biometrie der Tippdynamik
italian.AppDescription=Biometria della dinamica di digitazione

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\KeyBio\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\KeyBio.exe"; Comment: "{cm:AppDescription}"; AppUserModelID: "KeyBio.KeystrokeBiometrics"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\KeyBio.exe"; Comment: "{cm:AppDescription}"; AppUserModelID: "KeyBio.KeystrokeBiometrics"; Tasks: desktopicon

[Run]
Filename: "{app}\KeyBio.exe"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if (CurUninstallStep = usPostUninstall) and not UninstallSilent then
  begin
    DataDir := ExpandConstant('{userappdata}\KeyBio');
    if DirExists(DataDir) then
      if MsgBox(FmtMessage(CustomMessage('DeleteData'), [DataDir]), mbConfirmation,
                MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
