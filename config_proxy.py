# -*- coding: utf-8 -*-

"""BindX 子项目模块加载器。

app_hotkey_manager 与 mouse_click 各自包含 gui.py / app.py，模块名会冲突；
且二者各自以裸名 import 自己的引擎（hotkey_manager / engine）。
本模块用 importlib 按受控名字把子项目源码加载进 sys.modules：

  - mouse_click/engine.py          -> sys.modules["engine"]            （mouse_click/gui.py 依赖）
  - mouse_click/gui.py             -> sys.modules["bindx_mc_gui"]       （别名，避免与 app_hotkey_manager/gui.py 冲突）
  - app_hotkey_manager/hotkey_manager.py -> sys.modules["hotkey_manager"]  （app_hotkey_manager/gui.py 依赖）
  - app_hotkey_manager/gui.py      -> sys.modules["bindx_hk_gui"]       （别名）

加载顺序刻意为 mouse_click 在前、app_hotkey_manager 在后：mouse_click/gui.py 顶层会设置若干
user32 函数的 argtypes/restype，而后加载的 app_hotkey_manager/hotkey_manager.py 会覆盖回
所需的签名（HotkeyManager 依赖这些签名）。BindX 仅复用 mouse_click/gui.py 的对话框类
（纯 tkinter），不使用其 ctypes 托盘代码，故覆盖无副作用。
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
HOT_KEY_DIR = ROOT / "app_hotkey_manager"
MOUSE_CLICK_DIR = ROOT / "mouse_click"

_initialized = False


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载模块 {name} 来自 {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def init_subprojects():
    global _initialized
    if _initialized:
        return
    if not HOT_KEY_DIR.is_dir():
        raise FileNotFoundError(f"未找到 app_hotkey_manager 子项目目录：{HOT_KEY_DIR}")
    if not MOUSE_CLICK_DIR.is_dir():
        raise FileNotFoundError(f"未找到 mouse_click 子项目目录：{MOUSE_CLICK_DIR}")

    _load_module("engine", MOUSE_CLICK_DIR / "engine.py")
    _load_module("bindx_mc_gui", MOUSE_CLICK_DIR / "gui.py")
    _load_module("hotkey_manager", HOT_KEY_DIR / "hotkey_manager.py")
    _load_module("bindx_hk_gui", HOT_KEY_DIR / "gui.py")
    _initialized = True


def hk_module():
    if "hotkey_manager" not in sys.modules:
        init_subprojects()
    return sys.modules["hotkey_manager"]


def mc_engine_module():
    if "engine" not in sys.modules:
        init_subprojects()
    return sys.modules["engine"]


def hk_gui_module():
    if "bindx_hk_gui" not in sys.modules:
        init_subprojects()
    return sys.modules["bindx_hk_gui"]


def mc_gui_module():
    if "bindx_mc_gui" not in sys.modules:
        init_subprojects()
    return sys.modules["bindx_mc_gui"]
