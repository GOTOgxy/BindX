@echo off
setlocal

cd /d "%~dp0"

set "SOURCE=%CD%\BindX.bat"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\BindX.lnk"
set "OLD_TARGET=%STARTUP_DIR%\BindX.bat"

if not exist "%SOURCE%" (
  echo BindX.bat not found:
  echo %SOURCE%
  goto :end
)

if exist "%OLD_TARGET%" del /f /q "%OLD_TARGET%" >nul 2>nul

set "VBS=%TEMP%\bindx_startup_%RANDOM%.vbs"
echo Set ws = CreateObject("WScript.Shell") > "%VBS%"
echo Set sc = ws.CreateShortcut("%TARGET%") >> "%VBS%"
echo sc.TargetPath = "%SOURCE%" >> "%VBS%"
echo sc.WorkingDirectory = "%CD%" >> "%VBS%"
echo sc.Description = "BindX" >> "%VBS%"
echo sc.Save >> "%VBS%"
cscript //nologo "%VBS%" >nul
del /f /q "%VBS%" >nul 2>nul

if exist "%TARGET%" (
  echo Startup install complete.
  echo %TARGET%
) else (
  echo Install failed.
)

:end
echo.
pause
endlocal
