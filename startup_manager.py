# -*- coding: utf-8 -*-

import sys
from pathlib import Path
import winreg


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "BindX"
ROOT = Path(__file__).resolve().parent
APP_SCRIPT = ROOT / "app.py"
LEGACY_STARTUP_DIR = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
LEGACY_TARGETS = (
    LEGACY_STARTUP_DIR / "BindX.lnk",
    LEGACY_STARTUP_DIR / "BindX.bat",
)


def _startup_pythonw() -> Path:
    executable = Path(sys.executable).resolve()
    sibling_pythonw = executable.with_name("pythonw.exe")
    if executable.name.lower() == "pythonw.exe":
        return executable
    if sibling_pythonw.exists():
        return sibling_pythonw
    return executable


def build_command() -> str:
    interpreter = _startup_pythonw()
    return f'"{interpreter}" "{APP_SCRIPT}" --autostart'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, VALUE_NAME)
    except FileNotFoundError:
        return False
    return value == build_command()


def enable() -> None:
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, build_command())
    _remove_legacy_targets()


def disable() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
    _remove_legacy_targets()


def _remove_legacy_targets() -> None:
    for target in LEGACY_TARGETS:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
