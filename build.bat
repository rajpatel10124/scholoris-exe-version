@echo off
title Scholaris - Offline Desktop App Builder
color 0E
cls

echo =================================================================
echo        *  SCHOLARIS - OFFLINE DESKTOP APP BUILDER  *
echo =================================================================
echo.
echo This script will package Scholaris into a high-performance,
echo standalone offline desktop application for Windows.
echo.

:: 1. Verify Python Installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Python is not installed or not in your system PATH!
    echo Please download and install Python 3.10+ 64-bit from:
    echo https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

:: 2. Create clean Windows Virtual Environment
echo [1/6] Setting up a clean Windows virtual environment (venv_win)...
if not exist "venv_win" (
    python -m venv venv_win
    echo [OK] Created 'venv_win' virtual environment.
) else (
    echo [OK] Existing virtual environment 'venv_win' detected.
)
echo.

:: 3. Activate environment and install dependencies
echo [2/6] Activating virtual environment and installing dependencies...
call venv_win\Scripts\activate.bat
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to activate virtual environment!
    pause
    exit /b %errorlevel%
)

echo [OK] Activated virtual environment.
echo Upgrading pip...
python -m pip install --upgrade pip
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to upgrade pip!
    pause
    exit /b %errorlevel%
)

echo Filtering requirements.txt for Windows compatibility...
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-Content requirements.txt | Where-Object { $_ -notmatch 'psycopg2' -and $_ -notmatch 'mysql-connector' -and $_ -notmatch 'gunicorn' } | Set-Content requirements_win.txt"
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to filter requirements.txt!
    pause
    exit /b %errorlevel%
)

echo Installing dependencies from requirements_win.txt...
python -m pip install -r requirements_win.txt
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install dependencies from requirements_win.txt!
    echo Please verify that this PC is connected to the internet to download required packages.
    pause
    exit /b %errorlevel%
)

echo Installing packaging tools (pyinstaller, pywebview)...
python -m pip install pyinstaller pywebview
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to install PyInstaller or PyWebview!
    pause
    exit /b %errorlevel%
)
echo [OK] Dependency installation completed successfully.
echo.

:: 4. Check for offline models (Now inside the active virtual environment)
echo [3/6] Checking offline models folder...
if not exist "offline_models" (
    echo [WARNING] 'offline_models' folder was not found!
    echo Running the download script to retrieve AI models and NLTK data...
    python download_models.py
) else (
    echo [OK] 'offline_models' directory found.
)
echo.

:: 5. Package application using PyInstaller
echo [4/6] Packaging the application into a standalone executable...
echo Closing any running instances of the app to prevent file-locking errors...
taskkill /F /IM "Scholaris.exe" >nul 2>&1
echo Cleaning up previous build directories to prevent caching issues...
rd /s /q build_new >nul 2>&1
rd /s /q dist_build >nul 2>&1
echo.
echo Building may take 1-3 minutes. Please wait...
python -m PyInstaller --name "Scholaris" --noconsole --clean --noconfirm --distpath "dist_build" --workpath "build_new" --collect-all "sklearn" --collect-all "sentence_transformers" --collect-all "nltk" --hidden-import="flask_socketio" --hidden-import="engineio.async_drivers.threading" --hidden-import="faiss" --hidden-import="pdfplumber" --hidden-import="vector_service" --hidden-import="webview" --hidden-import="rapidfuzz" --add-data "templates;templates" --add-data "static;static" desktop.py
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] PyInstaller build failed! Please check the output logs above.
    pause
    exit /b %errorlevel%
)
echo [OK] PyInstaller packaging completed.
echo.

:: 6. Copy offline models directly to the output folder
echo [5/6] Copying 'offline_models' to the portable application folder...
echo (This avoids bloated exe sizes and ensures sub-second app startup!)
xcopy /E /I /Y "offline_models" "dist_build\Scholaris\offline_models"
if %errorlevel% neq 0 (
    color 0C
    echo [ERROR] Failed to copy 'offline_models' to output directory!
    pause
    exit /b %errorlevel%
)

:: 6b. Copy critical VC++ Runtime DLLs for 100% portability on clean PCs
echo Copying system C++ runtime DLLs for native offline side-loading...
copy "C:\Windows\System32\vcruntime140.dll" "dist_build\Scholaris\" /Y >nul 2>&1
copy "C:\Windows\System32\vcruntime140_1.dll" "dist_build\Scholaris\" /Y >nul 2>&1
copy "C:\Windows\System32\msvcp140.dll" "dist_build\Scholaris\" /Y >nul 2>&1
copy "C:\Windows\System32\concrt140.dll" "dist_build\Scholaris\" /Y >nul 2>&1

:: 7. Copy the shortcut helper to the output folder
copy "Create_Desktop_Shortcut.bat" "dist_build\Scholaris\Create_Desktop_Shortcut.bat" /Y >nul
echo [OK] Portability structure and side-loaded DLLs verified.
echo.

:: 8. Automatically create the Desktop Shortcut for the developer
echo [6/6] Creating a high-fidelity desktop icon for Scholaris...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$WshShell = New-Object -ComObject WScript.Shell; $Shortcut = $WshShell.CreateShortcut('%USERPROFILE%\Desktop\Scholaris.lnk'); $Shortcut.TargetPath = '%CD%\dist_build\Scholaris\Scholaris.exe'; $Shortcut.WorkingDirectory = '%CD%\dist_build\Scholaris'; $Shortcut.Description = 'Scholaris Plagiarism Detection System'; $Shortcut.Save()"
if %errorlevel% neq 0 (
    echo [WARNING] Could not create desktop shortcut automatically. You can do it manually!
) else (
    echo [OK] Desktop icon created successfully!
)
echo.

color 0A
echo =================================================================
echo [SUCCESS] BUILD SUCCESSFUL! SCHOLARIS DESKTOP IS READY!
echo =================================================================
echo.
echo PORTABLE DIRECTORY: %CD%\dist_build\Scholaris
echo.
echo Inside this directory:
echo   - Scholaris.exe             : Double-click to launch the app instantly.
echo   - offline_models\           : Contains your preloaded AI models.
echo   - Create_Desktop_Shortcut.bat: Double-click to create a desktop shortcut 
echo                                 on any other Windows computer!
echo.
echo One-Click Desktop Icon has been placed on your Desktop.
echo.
echo You can zip and share the entire 'dist_build\Scholaris' directory with any
echo Windows user. They just need to extract and click 'Create_Desktop_Shortcut.bat'!
echo =================================================================
echo.
pause
