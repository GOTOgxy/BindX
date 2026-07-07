@echo off
setlocal

set "TARGET=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BindX.lnk"
set "OLD_TARGET=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BindX.bat"
set "REMOVED=0"

if exist "%TARGET%" (
  del /f /q "%TARGET%"
  if exist "%TARGET%" (
    echo Remove failed.
  ) else (
    echo Startup entry removed.
    set "REMOVED=1"
  )
)

if exist "%OLD_TARGET%" (
  del /f /q "%OLD_TARGET%"
  if exist "%OLD_TARGET%" (
    echo Remove old startup entry failed.
  ) else (
    echo Old startup entry removed.
    set "REMOVED=1"
  )
)

if "%REMOVED%"=="0" echo Startup entry was not found.

echo.
pause
endlocal
