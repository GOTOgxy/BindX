@echo off
setlocal

cd /d "%~dp0"

set "SOURCE=%CD%\BindX.bat"
set "STARTUP_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET=%STARTUP_DIR%\BindX.bat"

if not exist "%SOURCE%" (
  echo BindX.bat not found:
  echo %SOURCE%
  goto :end
)

copy /y "%SOURCE%" "%TARGET%" >nul
if errorlevel 1 (
  echo Install failed.
  goto :end
)

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
