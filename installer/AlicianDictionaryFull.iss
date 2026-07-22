#define MyAppName "Alician Dictionary Full"
#define MyAppPublisher "Meartraep"
#define MyAppExeName "AlicianDictionaryFull.exe"
#define MyAppURL "https://github.com/Meartraep/Alician_dictionary"
#define ModelRevision "183bb99aa7af74355fb58d16edf8c13ae7c5433e"

#ifndef MyAppVersion
  #define MyAppVersion "26.7.22"
#endif

#ifdef OnlineInstaller
  #define SetupFlavor "Online"
  #define SetupDisplayFlavor "在线"
#else
  #define SetupFlavor "Offline"
  #define SetupDisplayFlavor "离线"
#endif

[Setup]
AppId={{A0C30F79-E83C-4AC8-BA32-642195A888AA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}（{#SetupDisplayFlavor}安装包）
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={localappdata}\Programs\AlicianDictionary
DefaultGroupName=Alician Dictionary
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\release\Full
OutputBaseFilename=AlicianDictionaryFull{#SetupFlavor}Setup
SetupIconFile=..\alice_app.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
DirExistsWarning=no
UsePreviousAppDir=yes
UsePreviousLanguage=yes
UsePreviousTasks=yes
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} {#SetupDisplayFlavor} installer
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
LicenseFile=..\LICENSE

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Default.isl"

[LangOptions]
LanguageName=简体中文
LanguageID=$0804
LanguageCodePage=936
DialogFontName=Microsoft YaHei UI

[Messages]
SetupAppTitle=安装程序
SetupWindowTitle=安装 - %1
UninstallAppTitle=卸载程序
UninstallAppFullTitle=卸载 %1
InformationTitle=信息
ConfirmTitle=确认
ErrorTitle=错误
SetupLdrStartupMessage=即将安装 %1。是否继续？
ExitSetupTitle=退出安装程序
ExitSetupMessage=安装尚未完成。如果现在退出，程序将不会被安装。%n%n以后可以再次运行安装程序完成安装。%n%n确定退出吗？
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安装(&I)
ButtonOK=确定
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonNo=否(&N)
ButtonFinish=完成(&F)
ButtonBrowse=浏览(&B)...
ButtonWizardBrowse=浏览(&R)...
ButtonNewFolder=新建文件夹(&M)
ClickNext=点击“下一步”继续，或点击“取消”退出安装程序。
BrowseDialogTitle=浏览文件夹
BrowseDialogLabel=请在下面选择文件夹，然后点击“确定”。
NewFolderName=新建文件夹
WelcomeLabel1=欢迎使用 [name] 安装向导
WelcomeLabel2=此向导将在您的计算机上安装 [name/ver]。%n%n建议继续前关闭其他应用程序。
WizardLicense=许可协议
LicenseLabel=继续前请阅读以下重要信息。
LicenseLabel3=请阅读以下许可协议。必须接受协议才能继续安装。
LicenseAccepted=我接受此协议(&A)
LicenseNotAccepted=我不接受此协议(&D)
WizardSelectDir=选择安装位置
SelectDirDesc=[name] 应安装到哪里？
SelectDirLabel3=安装程序将把 [name] 安装到以下文件夹。
SelectDirBrowseLabel=点击“下一步”继续。如需选择其他文件夹，请点击“浏览”。
DiskSpaceGBLabel=至少需要 [gb] GB 可用磁盘空间。
DiskSpaceMBLabel=至少需要 [mb] MB 可用磁盘空间。
WizardSelectTasks=选择附加任务
SelectTasksDesc=需要执行哪些附加任务？
SelectTasksLabel2=请选择安装 [name] 时要执行的附加任务，然后点击“下一步”。
WizardReady=准备安装
ReadyLabel1=安装程序已准备好在您的计算机上安装 [name]。
ReadyLabel2a=点击“安装”开始，或点击“上一步”检查或修改设置。
ReadyLabel2b=点击“安装”开始。
ReadyMemoDir=安装位置：
ReadyMemoGroup=开始菜单文件夹：
ReadyMemoTasks=附加任务：
DownloadingLabel2=正在下载文件...
ButtonStopDownload=停止下载(&S)
StopDownload=确定停止下载吗？
ErrorDownloadAborted=下载已中止
ErrorDownloadFailed=下载失败：%1 %2
WizardPreparing=正在准备安装
PreparingDesc=安装程序正在准备将 [name] 安装到您的计算机。
WizardInstalling=正在安装
InstallingLabel=请稍候，安装程序正在安装 [name]。
FinishedHeadingLabel=[name] 安装向导完成
FinishedLabelNoIcons=[name] 已成功安装到您的计算机。
FinishedLabel=[name] 已成功安装到您的计算机。可通过已创建的快捷方式启动程序。
ClickFinish=点击“完成”退出安装程序。
RunEntryExec=运行 %1
SetupAborted=安装未完成。%n%n请修正问题后重新运行安装程序。
StatusClosingApplications=正在关闭应用程序...
StatusCreateDirs=正在创建目录...
StatusExtractFiles=正在解压文件...
StatusDownloadFiles=正在下载文件...
StatusCreateIcons=正在创建快捷方式...
StatusCreateRegistryEntries=正在写入注册表...
StatusSavingUninstall=正在保存卸载信息...
StatusRunProgram=正在完成安装...
ConfirmUninstall=确定要完整删除 %1 及其所有程序组件吗？%n%n独立保存的模型文件和用户数据将予以保留。
UninstallStatusLabel=请稍候，正在从计算机中删除 %1。
UninstalledAll=%1 已成功从计算机中删除。独立模型文件和用户数据仍保留在原位置。
WizardUninstalling=卸载状态
StatusUninstalling=正在卸载 %1...

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："; Flags: unchecked

[Files]
Source: "..\release\Full\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "model_manifest.json"; DestDir: "{code:GetModelDir}"; DestName: ".alic_model_manifest.json"; Flags: ignoreversion uninsneveruninstall
Source: "MODEL_SOURCE.txt"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall
Source: "LICENSE.apache-2.0.txt"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall

#ifdef OnlineInstaller
Source: "https://huggingface.co/shibing624/text2vec-base-chinese/resolve/{#ModelRevision}/config.json?download=true"; DestName: "config.json"; DestDir: "{code:GetModelDir}"; Hash: "fdf4d96b74a9e2dc8ae752d74bcfbbf8b3a754b3d97412477f8768ef65a7db36"; ExternalSize: 856; Flags: external download ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "https://huggingface.co/shibing624/text2vec-base-chinese/resolve/{#ModelRevision}/model.safetensors?download=true"; DestName: "model.safetensors"; DestDir: "{code:GetModelDir}"; Hash: "0c855515479137398ce4ea985628548d4e8ed8c5764656dac966d6a24f39e721"; ExternalSize: 409098104; Flags: external download ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "https://huggingface.co/shibing624/text2vec-base-chinese/resolve/{#ModelRevision}/special_tokens_map.json?download=true"; DestName: "special_tokens_map.json"; DestDir: "{code:GetModelDir}"; Hash: "303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3"; ExternalSize: 112; Flags: external download ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "https://huggingface.co/shibing624/text2vec-base-chinese/resolve/{#ModelRevision}/tokenizer_config.json?download=true"; DestName: "tokenizer_config.json"; DestDir: "{code:GetModelDir}"; Hash: "3da14b28cdfd6bcb24aef5e16a37c868bc6e8428b4180833d5e0ef9cc19931df"; ExternalSize: 319; Flags: external download ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "https://huggingface.co/shibing624/text2vec-base-chinese/resolve/{#ModelRevision}/vocab.txt?download=true"; DestName: "vocab.txt"; DestDir: "{code:GetModelDir}"; Hash: "45bbac6b341c319adc98a532532882e91a9cefc0329aa57bac9ae761c27b291c"; ExternalSize: 109540; Flags: external download ignoreversion uninsneveruninstall; Check: ShouldInstallModel
#else
Source: "..\release_build\installer_model\config.json"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "..\release_build\installer_model\model.safetensors"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "..\release_build\installer_model\special_tokens_map.json"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "..\release_build\installer_model\tokenizer_config.json"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall; Check: ShouldInstallModel
Source: "..\release_build\installer_model\vocab.txt"; DestDir: "{code:GetModelDir}"; Flags: ignoreversion uninsneveruninstall; Check: ShouldInstallModel
#endif

[Icons]
Name: "{group}\Alician Dictionary Full"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Alician Dictionary Full"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Meartraep\AlicianDictionary"; ValueType: string; ValueName: "ModelPath"; ValueData: "{code:GetModelDir}"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Meartraep\AlicianDictionary"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 Alician Dictionary Full"; Flags: nowait postinstall skipifsilent

[Code]
var
  ModelDirPage: TInputDirWizardPage;
  ModelInstallRequired: Boolean;

function GetModelDir(Param: String): String;
begin
  if Assigned(ModelDirPage) then
    Result := RemoveBackslashUnlessRoot(ModelDirPage.Values[0])
  else
    Result := ExpandConstant('{localappdata}\AlicianDictionary\Models\text2vec-base-chinese');
end;

function HasExpectedModelFile(
  const FileName: String; ExpectedSize: Integer; const ExpectedSHA256: String
): Boolean;
var
  ActualSize: Integer;
begin
  Result := False;
  if not FileSize(FileName, ActualSize) then
    Exit;
  if ActualSize <> ExpectedSize then
    Exit;
  Result := CompareText(GetSHA256OfFile(FileName), ExpectedSHA256) = 0;
end;

function IsInstalledModelValid: Boolean;
var
  ModelDir: String;
begin
  ModelDir := GetModelDir('');
  Result :=
    HasExpectedModelFile(
      AddBackslash(ModelDir) + 'config.json', 856,
      'fdf4d96b74a9e2dc8ae752d74bcfbbf8b3a754b3d97412477f8768ef65a7db36') and
    HasExpectedModelFile(
      AddBackslash(ModelDir) + 'model.safetensors', 409098104,
      '0c855515479137398ce4ea985628548d4e8ed8c5764656dac966d6a24f39e721') and
    HasExpectedModelFile(
      AddBackslash(ModelDir) + 'special_tokens_map.json', 112,
      '303df45a03609e4ead04bc3dc1536d0ab19b5358db685b6f3da123d05ec200e3') and
    HasExpectedModelFile(
      AddBackslash(ModelDir) + 'tokenizer_config.json', 319,
      '3da14b28cdfd6bcb24aef5e16a37c868bc6e8428b4180833d5e0ef9cc19931df') and
    HasExpectedModelFile(
      AddBackslash(ModelDir) + 'vocab.txt', 109540,
      '45bbac6b341c319adc98a532532882e91a9cefc0329aa57bac9ae761c27b291c');
end;

function ShouldInstallModel: Boolean;
begin
  Result := ModelInstallRequired;
end;

procedure InitializeWizard;
var
  PreviousModelPath: String;
  CommandLineModelPath: String;
begin
  ModelDirPage := CreateInputDirPage(
    wpSelectDir,
    '选择语义模型存储位置',
    '模型与程序分开保存，后续程序更新不会重复下载模型。',
    '请选择专用于 text2vec 模型的文件夹（约需 410 MB）。可输入本机任意有写入权限的路径。' + #13#10 +
    '如果该目录已有完整模型，安装器将直接复用，不会重新下载或覆盖。',
    False,
    SetupMessage(msgNewFolderName)
  );
  ModelDirPage.Add('模型文件夹：');
  CommandLineModelPath := ExpandConstant('{param:MODELDIR|}');
  if CommandLineModelPath <> '' then
    PreviousModelPath := CommandLineModelPath
  else if not RegQueryStringValue(
    HKCU, 'Software\Meartraep\AlicianDictionary', 'ModelPath', PreviousModelPath
  ) then
    PreviousModelPath := ExpandConstant('{localappdata}\AlicianDictionary\Models\text2vec-base-chinese');
  ModelDirPage.Values[0] := PreviousModelPath;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  ModelDir: String;
  ProbeFile: String;
begin
  Result := True;
  if CurPageID <> ModelDirPage.ID then
    Exit;

  ModelDir := GetModelDir('');
  if ModelDir = '' then
  begin
    MsgBox('请选择模型存储位置。', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  if not ForceDirectories(ModelDir) then
  begin
    MsgBox('无法创建模型目录，请选择一个有写入权限的位置。', mbError, MB_OK);
    Result := False;
    Exit;
  end;

  ProbeFile := AddBackslash(ModelDir) + '.alician-write-test.tmp';
  if not SaveStringToFile(ProbeFile, 'test', False) then
  begin
    MsgBox('无法写入模型目录，请选择另一个位置。', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  DeleteFile(ProbeFile);

  ModelInstallRequired := not IsInstalledModelValid;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  ModelInstallRequired := not IsInstalledModelValid;
  if ModelInstallRequired then
    Log('The selected model directory needs installation or repair: ' + GetModelDir(''))
  else
    Log('A complete model already exists; model download/copy will be skipped: ' + GetModelDir(''));
  Result := '';
end;
