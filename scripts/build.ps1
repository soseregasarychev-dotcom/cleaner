# Сборка Уборщика в exe и установка в %LOCALAPPDATA%\Programs\Uborshchik.
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1            # собрать и установить
#   powershell -ExecutionPolicy Bypass -File scripts\build.ps1 -NoInstall # только собрать
param([switch]$NoInstall)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$py = Join-Path $root '.venv\Scripts\python.exe'

& $py scripts\make_icon.py
& $py -m PyInstaller --noconfirm --clean --windowed --onedir `
    --name 'Uborshchik' `
    --icon 'assets\icon.ico' `
    --exclude-module PySide6.QtWebEngineCore --exclude-module PySide6.Qt3DCore `
    --exclude-module PySide6.QtQuick --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtMultimedia --exclude-module PySide6.QtPdf `
    --exclude-module tkinter `
    scripts\entry.py
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed' }
# Русское имя у exe — переименовываем после сборки
Rename-Item 'dist\Uborshchik\Uborshchik.exe' 'Уборщик.exe' -Force
Write-Host "Собрано: dist\Uborshchik\Уборщик.exe"

if ($NoInstall) { return }

$target = Join-Path $env:LOCALAPPDATA 'Programs\Uborshchik'
# Остановить запущенную копию, чтобы заменить файлы
Get-Process -Name 'Уборщик' -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500
if (Test-Path $target) { Remove-Item $target -Recurse -Force }
Copy-Item 'dist\Uborshchik' $target -Recurse
$exe = Join-Path $target 'Уборщик.exe'

# Ярлык в меню «Пуск»
$lnk = Join-Path ([Environment]::GetFolderPath('Programs')) 'Уборщик.lnk'
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $exe
$s.WorkingDirectory = $target
$s.IconLocation = "$exe,0"
$s.Description = 'Уборщик — порядок на рабочем столе'
$s.Save()
Write-Host "Установлено: $exe"
Write-Host "Ярлык: $lnk"
