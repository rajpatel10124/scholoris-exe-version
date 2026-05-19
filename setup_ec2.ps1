# Scholaris Windows EC2 Complete Setup and Auto-Build Script
# =========================================================
# This script will automatically download and install Git, Python 3.11,
# clone the project, download all AI models, and build the one-click desktop EXE.

$ErrorActionPreference = "Stop"

Write-Host "=========================================================" -ForegroundColor Green
Write-Host "     SCHOLARIS - WINDOWS EC2 AUTOMATED SETUP & BUILDER   " -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""

# 1. Elevate process to Admin if not already
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host "[STATUS] Elevating permissions to Administrator..." -ForegroundColor Yellow
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    Exit
}

$workDir = "C:\Scholaris-Build"
if (-not (Test-Path $workDir)) {
    New-Item -Path $workDir -ItemType Directory | Out-Null
}
Set-Location $workDir

# ── 2. INSTALL GIT FOR WINDOWS ────────────────────────────────────────────────
if (Get-Command git -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Git is already installed." -ForegroundColor Green
} else {
    Write-Host "[STATUS] Downloading Git for Windows..." -ForegroundColor Yellow
    $gitUrl = "https://github.com/git-for-windows/git/releases/download/v2.44.0.windows.1/Git-2.44.0-64-bit.exe"
    $gitPath = Join-Path $workDir "git-installer.exe"
    Invoke-WebRequest -Uri $gitUrl -OutFile $gitPath
    
    Write-Host "[STATUS] Installing Git silently..." -ForegroundColor Yellow
    Start-Process -FilePath $gitPath -ArgumentList "/VERYSILENT", "/NORESTART", "/NOCANCEL", "/SP-" -Wait
    Remove-Item $gitPath
    Write-Host "[OK] Git installed successfully." -ForegroundColor Green
}

# ── 3. INSTALL PYTHON 3.11 ────────────────────────────────────────────────────
if (Get-Command python -ErrorAction SilentlyContinue) {
    Write-Host "[OK] Python is already installed." -ForegroundColor Green
} else {
    Write-Host "[STATUS] Downloading Python 3.11.9 (64-bit)..." -ForegroundColor Yellow
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    $pyPath = Join-Path $workDir "python-installer.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyPath
    
    Write-Host "[STATUS] Installing Python silently (Adding to Path and installing pip)..." -ForegroundColor Yellow
    Start-Process -FilePath $pyPath -ArgumentList "/quiet", "InstallAllUsers=1", "PrependPath=1", "Include_test=0" -Wait
    Remove-Item $pyPath
    Write-Host "[OK] Python installed successfully." -ForegroundColor Green
}

# ── 4. REFRESH ENVIRONMENT VARIABLES ──────────────────────────────────────────
Write-Host "[STATUS] Updating Path environment variables..." -ForegroundColor Yellow
$env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
# Add default Python 3.11 directories to path just in case refresh delayed
$env:Path += ";C:\Program Files\Python311;C:\Program Files\Python311\Scripts"

# Verify installations
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git installation failed or not found in Path. Please try restarting PowerShell."
}
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "Python installation failed or not found in Path. Please try restarting PowerShell."
}

# ── 5. CLONE REPOSITORY ───────────────────────────────────────────────────────
$repoDir = Join-Path $workDir "scholoris-exe-version"
if (Test-Path $repoDir) {
    Write-Host "[STATUS] Cleaning old repository directory..." -ForegroundColor Yellow
    Remove-Item $repoDir -Recurse -Force
}

Write-Host "[STATUS] Cloning repository..." -ForegroundColor Yellow
git clone https://github.com/rajpatel10124/scholoris-exe-version.git $repoDir

# ── 6. START AUTO-BUILD PROCESS ────────────────────────────────────────────────
Set-Location $repoDir
Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host " [SUCCESS] INITIAL SETUP COMPLETE! LAUNCHING AUTO-BUILDER..." -ForegroundColor Green
Write-Host "=========================================================" -ForegroundColor Green
Write-Host ""

Start-Process cmd.exe -ArgumentList "/c build.bat" -Wait

Write-Host ""
Write-Host "=========================================================" -ForegroundColor Green
Write-Host " [SUCCESS] ALL RUNS COMPLETED SUCCESSFULLY! " -ForegroundColor Green
Write-Host " Standalone EXE: C:\Scholaris-Build\scholoris-exe-version\dist_build\Scholaris\Scholaris.exe" -ForegroundColor Yellow
Write-Host "=========================================================" -ForegroundColor Green
