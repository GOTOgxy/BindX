@echo off
rem BindX launcher.
rem Resolves pythonw robustly: PATH first, then known install locations.
rem (A long-running explorer.exe can hold a stale PATH after environment changes.)
cd /d "%~dp0"

set "PYW="
where pythonw >nul 2>nul && set "PYW=pythonw"

if not defined PYW if exist "C:\Users\gxy\miniforge3\pythonw.exe" set "PYW=C:\Users\gxy\miniforge3\pythonw.exe"
if not defined PYW if exist "C:\Users\gxy\miniconda3\pythonw.exe" set "PYW=C:\Users\gxy\miniconda3\pythonw.exe"

if not defined PYW (
    echo [BindX] pythonw.exe not found in PATH or known locations.
    echo If you recently changed your Python environment, log out and back in.
    pause
    exit /b 1
)

start "" "%PYW%" app.py
