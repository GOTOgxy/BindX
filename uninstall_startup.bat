@echo off
setlocal

set "TARGET=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\BindX.bat"

if exist "%TARGET%" (
  del /f /q "%TARGET%"
  if exist "%TARGET%" (
    echo Remove failed.
  ) else (
    echo Startup entry removed.
  )
) else (
  echo Startup entry was not found.
)

echo.
pause
endlocal
