# -*- coding: utf-8 -*-

"""BindX 子项目逻辑模块加载器。

两个内联模块现在只向 BindX 提供逻辑与业务处理：

  - mouse_click/engine.py -> sys.modules["engine"]
  - app_hotkey_manager/hotkey_manager.py -> sys.modules["hotkey_manager"]
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
    _load_module("hotkey_manager", HOT_KEY_DIR / "hotkey_manager.py")
    _initialized = True


def hk_module():
    if "hotkey_manager" not in sys.modules:
        init_subprojects()
    return sys.modules["hotkey_manager"]


def mc_engine_module():
    if "engine" not in sys.modules:
        init_subprojects()
    return sys.modules["engine"]
