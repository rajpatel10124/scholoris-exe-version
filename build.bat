@echo off
echo ===================================================
echo   SCHOLARIS - OFFLINE DESKTOP APP BUILDER
echo ===================================================
echo.

echo [1/3] Installing required Python libraries...
python -m pip install -r requirements.txt
python -m pip install pywebview pyinstaller
echo.

echo [2/3] Building the Desktop Application (exe)...
python -m PyInstaller --name "Scholaris" --noconsole --add-data "templates;templates" --add-data "static;static" --add-data "offline_models;offline_models" desktop.py
echo.

echo ===================================================
echo [3/3] BUILD COMPLETE! 
echo ===================================================
echo Your offline application is ready in the "dist\Scholaris" folder!
echo Inside you will find "Scholaris.exe". Just double-click it to run.
echo.
pause
