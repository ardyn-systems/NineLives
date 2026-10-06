# Build the Windows HashBench bundle + installer.
#
# Prereqs:  python -m pip install pyinstaller py7zr
#           (optional) Inno Setup 6 for the installer: https://jrsoftware.org/isdl.php
#
# Usage:    powershell -ExecutionPolicy Bypass -File build_windows.ps1
#           add -Full to bundle the entire SecLists collection (large)
#           add -NoFetch to skip (re)downloading hashcat/wordlists

param([switch]$Full, [switch]$NoFetch)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --quiet --upgrade pyinstaller py7zr pywebview pythonnet

if (-not $NoFetch) {
    Write-Host "== Fetching latest hashcat (into vendor\hashcat) =="
    python fetch_hashcat.py
    Write-Host "== Fetching wordlists (into vendor\wordlists) =="
    if ($Full) { python fetch_wordlists.py --full } else { python fetch_wordlists.py }
}

$addData = @("--add-data", "webui;webui")
if (Test-Path "vendor") { $addData += @("--add-data", "vendor;vendor") }

Write-Host "== Building with PyInstaller =="
pyinstaller --noconfirm --windowed --name HashBench `
    --collect-all webview `
    @addData `
    hashbench.py

Write-Host "Built: dist\HashBench\HashBench.exe"

# Build the installer if Inno Setup is available.
$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc -and (Test-Path "C:\Program Files (x86)\Inno Setup 6\ISCC.exe")) {
    $iscc = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
} elseif ($iscc) { $iscc = $iscc.Source }

if ($iscc) {
    Write-Host "== Building installer with Inno Setup =="
    & $iscc installer.iss
    Write-Host "Installer: dist\HashBench-Setup.exe"
} else {
    Write-Host "Inno Setup (iscc) not found - skipping installer."
    Write-Host "Install Inno Setup 6 to produce dist\HashBench-Setup.exe."
}
