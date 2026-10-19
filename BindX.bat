@echo off
rem BindX Native Desktop Launcher
cd /d "%~dp0"

if exist "bindx.exe" (
    start "" "bindx.exe"
    exit /b 0
)

if exist "%USERPROFILE%\.bindx-target\release\bindx.exe" (
    start "" "%USERPROFILE%\.bindx-target\release\bindx.exe"
    exit /b 0
)

echo [BindX] 尚未找到已编译的 bindx.exe 可执行文件。
pause
exit /b 1
