# Собрать установщик для передачи другим: dist\Уборщик-Setup-<версия>.exe
#   powershell -ExecutionPolicy Bypass -File scripts\installer.ps1
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'

$iscc = @(
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $iscc) { throw 'Нет Inno Setup: winget install JRSoftware.InnoSetup' }

& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'build.ps1') -NoInstall
if ($LASTEXITCODE -ne 0) { throw 'Сборка exe не удалась' }
& $py scripts\make_installer_art.py

$version = (& $py -c "import uborshchik; print(uborshchik.__version__)").Trim()
& $iscc /Q "/DAppVersion=$version" installer\uborshchik.iss
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup не собрал установщик' }
$out = Join-Path $root "dist\Уборщик-Setup-$version.exe"
Write-Host ("Готово: {0} ({1:N0} МБ)" -f $out, ((Get-Item $out).Length / 1MB))
