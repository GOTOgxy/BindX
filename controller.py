# -*- coding: utf-8 -*-

"""BindX 双引擎控制器。

封装 app_hotkey_manager 的 HotkeyManager 与 mouse_click 的 RemapperEngine 生命周期，
让 gui.py 不必直接接触子项目内部 API。

关键约束（来自子项目源码）：
  - HotkeyManager.start_polling_thread() 内部才初始化 _pending_registers /
    _pending_unregisters（hotkey_manager.py:829-830）；在此之前的 _register_one /
    _unregister_one 会 AttributeError。因此控制器在 init 时先 start_polling_thread，
    其后所有 CRUD 才安全。
  - start_polling_thread 启动轮询线程时会自动 RegisterHotKey 所有 enabled 条目
    （hotkey_manager.py:854-856），等价于"启动即注册"。所以 hk_running 初值跟随
    该事实设为 True。
  - RemapperEngine.start() 是重入 no-op；stop() 会唤醒消息循环并等待线程退出，
    所以重启可直接 stop()->start()。
"""

import json
import os
from pathlib import Path

import config_proxy

APP_STATE_FILE = Path(__file__).resolve().with_name("bindx_config.json")
DEFAULT_APP_STATE = {"hotkey_running": True, "mouse_running": True}


def load_app_state():
    if not APP_STATE_FILE.exists():
        return dict(DEFAULT_APP_STATE)
    try:
        state = json.loads(APP_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_APP_STATE)
    merged = dict(DEFAULT_APP_STATE)
    merged.update({k: bool(v) for k, v in state.items() if k in DEFAULT_APP_STATE})
    return merged


def save_app_state(state):
    tmp_path = APP_STATE_FILE.with_suffix(APP_STATE_FILE.suffix + ".tmp")
    tmp_path.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, APP_STATE_FILE)


class BindXController:
    def __init__(self):
        hk = config_proxy.hk_module()
        mc = config_proxy.mc_engine_module()

        self._HotkeyManager = hk.HotkeyManager
        self._load_hotkey_config = hk.load_config
        self._RemapperEngine = mc.RemapperEngine
        self._load_mouse_config = mc.load_config
        self._save_mouse_config = mc.save_config
        self.app_state = load_app_state()

        self.hk_config = self._load_hotkey_config()
        self.hotkey_manager = self._HotkeyManager(self.hk_config)

        self.hk_running = bool(self.app_state.get("hotkey_running", True))
        self.hotkey_manager.start_polling_thread(register_enabled=self.hk_running)

        self.mc_config = self._load_mouse_config()
        self.mouse_engine = self._RemapperEngine()
        self.mc_running = False
        if self.app_state.get("mouse_running", True):
            self.start_mouse(persist=False)

    def set_hotkey_self_callback(self, callback):
        self.hotkey_manager.set_self_callback(callback)

    def process_hotkeys(self):
        if self.hotkey_manager is not None:
            self.hotkey_manager.process_hotkeys()

    def _save_engine_state(self):
        save_app_state(self.app_state)

    def start_hotkey(self, persist=True):
        if self.hotkey_manager is None:
            return
        self.hotkey_manager.register_all()
        self.hk_running = True
        self.app_state["hotkey_running"] = True
        if persist:
            self._save_engine_state()

    def stop_hotkey(self, persist=True):
        if self.hotkey_manager is None:
            return
        self.hotkey_manager.unregister_all()
        self.hk_running = False
        self.app_state["hotkey_running"] = False
        if persist:
            self._save_engine_state()

    def reload_hotkey_config(self):
        self.hk_config = self._load_hotkey_config()

    def start_mouse(self, persist=True):
        if self.mouse_engine is None:
            return
        self.mc_config = self._load_mouse_config()
        self.mouse_engine.start(self.mc_config)
        self.mc_running = self.mouse_engine.running
        self.app_state["mouse_running"] = True
        if persist:
            self._save_engine_state()

    def stop_mouse(self, persist=True):
        if self.mouse_engine is None:
            return
        self.mouse_engine.stop()
        self.mc_running = False
        self.app_state["mouse_running"] = False
        if persist:
            self._save_engine_state()

    def restart_mouse(self):
        was_running = bool(self.app_state.get("mouse_running", self.mc_running))
        self.mouse_engine.stop()
        if was_running:
            self.mc_config = self._load_mouse_config()
            self.mouse_engine.start(self.mc_config)
            self.mc_running = self.mouse_engine.running
        else:
            self.mc_config = self._load_mouse_config()

    def save_mouse_config(self, config):
        self.mc_config = config
        self._save_mouse_config(config)

    def quit(self):
        try:
            self.hotkey_manager.unregister_all()
            self.hotkey_manager.stop_polling_thread()
        except Exception:
            pass
        try:
            self.mouse_engine.stop()
        except Exception:
            pass
