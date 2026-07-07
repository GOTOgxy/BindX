# -*- coding: utf-8 -*-

import ctypes
import subprocess
import tempfile
from ctypes import wintypes
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BAT_PATH = ROOT / "BindX.bat"
ICON_PATH = ROOT / "assets" / "bindx_shortcut.ico"
DESCRIPTION = "BindX"

CSIDL_DESKTOPDIRECTORY = 0x0010
CSIDL_PROGRAMS = 0x0002
SHGFP_TYPE_CURRENT = 0

shell32 = ctypes.WinDLL("shell32", use_last_error=True)
shell32.SHGetFolderPathW.argtypes = [
    wintypes.HWND,
    ctypes.c_int,
    wintypes.HANDLE,
    wintypes.DWORD,
    wintypes.LPWSTR,
]
shell32.SHGetFolderPathW.restype = ctypes.c_long


def _special_folder(csidl: int) -> Path:
    buffer = ctypes.create_unicode_buffer(260)
    result = shell32.SHGetFolderPathW(None, csidl, None, SHGFP_TYPE_CURRENT, buffer)
    if result != 0:
        raise OSError(f"SHGetFolderPathW failed: {result}")
    return Path(buffer.value)


def _create_shortcut(link_path: Path) -> Path:
    if not BAT_PATH.exists():
        raise FileNotFoundError(f"BindX.bat not found: {BAT_PATH}")
    if not ICON_PATH.exists():
        raise FileNotFoundError(f"Shortcut icon not found: {ICON_PATH}")

    link_path.parent.mkdir(parents=True, exist_ok=True)

    vbscript = (
        'Set ws = CreateObject("WScript.Shell")\n'
        f'Set sc = ws.CreateShortcut("{str(link_path)}")\n'
        f'sc.TargetPath = "{str(BAT_PATH)}"\n'
        f'sc.WorkingDirectory = "{str(ROOT)}"\n'
        f'sc.Description = "{DESCRIPTION}"\n'
        f'sc.IconLocation = "{str(ICON_PATH)}"\n'
        'sc.Save\n'
    )

    with tempfile.NamedTemporaryFile("w", suffix=".vbs", delete=False, encoding="utf-8") as temp:
        temp.write(vbscript)
        temp_path = Path(temp.name)

    try:
        subprocess.run(
            ["cscript", "//nologo", str(temp_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    if not link_path.exists():
        raise OSError(f"Shortcut not created: {link_path}")
    return link_path


def create_desktop_shortcut() -> Path:
    return _create_shortcut(_special_folder(CSIDL_DESKTOPDIRECTORY) / "BindX.lnk")


def create_start_menu_shortcut() -> Path:
    return _create_shortcut(_special_folder(CSIDL_PROGRAMS) / "BindX.lnk")


def remove_desktop_shortcut() -> bool:
    shortcut_path = _special_folder(CSIDL_DESKTOPDIRECTORY) / "BindX.lnk"
    if not shortcut_path.exists():
        return False
    shortcut_path.unlink()
    return True


def remove_start_menu_shortcut() -> bool:
    shortcut_path = _special_folder(CSIDL_PROGRAMS) / "BindX.lnk"
    if not shortcut_path.exists():
        return False
    shortcut_path.unlink()
    return True


def desktop_shortcut_exists() -> bool:
    return (_special_folder(CSIDL_DESKTOPDIRECTORY) / "BindX.lnk").exists()


def start_menu_shortcut_exists() -> bool:
    return (_special_folder(CSIDL_PROGRAMS) / "BindX.lnk").exists()
