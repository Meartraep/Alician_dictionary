param(
    [string]$AppVersion = "26.7.22",
    [switch]$SkipProgramBuild
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseFull = Join-Path $projectRoot "release\Full"
$releaseLite = Join-Path $projectRoot "release\Lite"
$modelStage = Join-Path $projectRoot "release_build\installer_model"
$manifestPath = Join-Path $projectRoot "installer\model_manifest.json"
$installerScript = Join-Path $projectRoot "installer\AlicianDictionaryFull.iss"

function Get-IsccPath {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $candidates = @(
        (Join-Path ${env:LOCALAPPDATA} "Programs\Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:LOCALAPPDATA} "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles} "Inno Setup 7\ISCC.exe"),
        (Join-Path ${env:ProgramFiles} "Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe")
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) { return $candidate }
    }
    throw "Inno Setup 6.5+ was not found. Install JRSoftware.InnoSetup with winget first."
}

function Test-ModelFile {
    param([string]$Path, [long]$ExpectedSize, [string]$ExpectedHash)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "Missing model file: $Path"
    }
    $item = Get-Item -LiteralPath $Path
    if ($item.Length -ne $ExpectedSize) {
        throw "Unexpected size for $Path (actual $($item.Length), expected $ExpectedSize)"
    }
    $actualHash = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $ExpectedHash.ToLowerInvariant()) {
        throw "SHA-256 mismatch for $Path"
    }
}

Push-Location $projectRoot
try {
    New-Item -ItemType Directory -Force -Path $releaseFull, $releaseLite, $modelStage | Out-Null

    if (-not $SkipProgramBuild) {
        python -m PyInstaller --noconfirm --clean --workpath release_build\full --distpath release\Full AlicianDictionary.spec
        if ($LASTEXITCODE -ne 0) { throw "Full PyInstaller build failed." }
        python -m PyInstaller --noconfirm --clean --workpath release_build\lite --distpath release\Lite AlicianDictionaryLite.spec
        if ($LASTEXITCODE -ne 0) { throw "Lite PyInstaller build failed." }
    }

    $modelRoot = python -c "from model_manager import find_cached_model_snapshot; p=find_cached_model_snapshot(); print(p or '')"
    if ($LASTEXITCODE -ne 0 -or -not $modelRoot) {
        throw "The pinned text2vec model snapshot is not available in the local Hugging Face cache."
    }
    $modelRoot = $modelRoot.Trim()
    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    foreach ($property in $manifest.files.PSObject.Properties) {
        $name = $property.Name
        $metadata = $property.Value
        $source = Join-Path $modelRoot $name
        Test-ModelFile -Path $source -ExpectedSize ([long]$metadata.size) -ExpectedHash ([string]$metadata.sha256)
        Copy-Item -LiteralPath $source -Destination (Join-Path $modelStage $name) -Force
    }

    $iscc = Get-IsccPath
    & $iscc "/DMyAppVersion=$AppVersion" "/DOnlineInstaller=1" $installerScript
    if ($LASTEXITCODE -ne 0) { throw "Online installer compilation failed." }
    & $iscc "/DMyAppVersion=$AppVersion" $installerScript
    if ($LASTEXITCODE -ne 0) { throw "Offline installer compilation failed." }

    $artifacts = @(
        (Join-Path $releaseFull "AlicianDictionaryFull.exe"),
        (Join-Path $releaseLite "AlicianDictionaryLite.exe"),
        (Join-Path $releaseFull "AlicianDictionaryFullOnlineSetup.exe"),
        (Join-Path $releaseFull "AlicianDictionaryFullOfflineSetup.exe")
    )
    $artifacts | ForEach-Object {
        $item = Get-Item -LiteralPath $_
        $hash = (Get-FileHash -LiteralPath $_ -Algorithm SHA256).Hash
        [PSCustomObject]@{
            Path = $item.FullName
            LastWriteTime = $item.LastWriteTime
            Size = $item.Length
            SHA256 = $hash
        }
    } | Format-List
}
finally {
    Pop-Location
}
