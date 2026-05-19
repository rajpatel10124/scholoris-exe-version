@echo off
title Scholaris Shortcut Creator
color 0B
cls
echo ===================================================
echo   SCHOLARIS - CREATE DESKTOP SHORTCUT
echo ===================================================
echo.
echo Creating a shortcut to Scholaris on your Desktop...
echo.

:: Create temporary VBScript to resolve the dynamic Desktop folder (handles OneDrive & domain redirects)
echo Set WshShell = CreateObject("WScript.Shell") > "%temp%\create_shortcut.vbs"
echo strDesktop = WshShell.SpecialFolders("Desktop") >> "%temp%\create_shortcut.vbs"
echo Set oMyShortcut = WshShell.CreateShortcut(strDesktop ^& "\Scholaris.lnk") >> "%temp%\create_shortcut.vbs"
echo oMyShortcut.TargetPath = "%~dp0Scholaris.exe" >> "%temp%\create_shortcut.vbs"
echo oMyShortcut.WorkingDirectory = "%~dp0" >> "%temp%\create_shortcut.vbs"
echo oMyShortcut.Description = "Scholaris Plagiarism Detection System" >> "%temp%\create_shortcut.vbs"
echo oMyShortcut.Save >> "%temp%\create_shortcut.vbs"

:: Run the script natively using Windows Script Host
cscript //nologo "%temp%\create_shortcut.vbs"
del "%temp%\create_shortcut.vbs"

echo.
echo ===================================================
echo [SUCCESS] Shortcut 'Scholaris' created on your Desktop.
echo You can now run the app with one click from your Desktop!
echo ===================================================
echo.
pause
