# -*- coding: utf-8 -*-

"""BindX trigger controller。

HotKeyManager 仍负责热键配置 CRUD 和 AppController 动作；TriggerEngine 负责统一
WH_KEYBOARD_LL / WH_MOUSE_LL 低层 hook、触发匹配与 hook 自恢复。
"""

import json
import os
from pathlib import Path

import config_proxy
import startup_manager
from trigger_engine import TriggerEngine

APP_STATE_FILE = Path(__file__).resolve().with_name("bindx_config.json")
DEFAULT_APP_STATE = {
    "hotkey_running": True,
    "mouse_running": True,
    "window_size": None,
    "window_zoomed": False,
    "font_preset": "常规",
    "autostart_enabled": False,
}


def load_app_state():
    if not APP_STATE_FILE.exists():
        return dict(DEFAULT_APP_STATE)
    try:
        state = json.loads(APP_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(DEFAULT_APP_STATE)
    merged = dict(DEFAULT_APP_STATE)
    merged["hotkey_running"] = bool(state.get("hotkey_running", DEFAULT_APP_STATE["hotkey_running"]))
    merged["mouse_running"] = bool(state.get("mouse_running", DEFAULT_APP_STATE["mouse_running"]))
    size = state.get("window_size")
    if not (isinstance(size, str) and size):
        legacy_geometry = state.get("window_geometry")
        if isinstance(legacy_geometry, str) and "x" in legacy_geometry:
            size = legacy_geometry.split("+", 1)[0]
    merged["window_size"] = size if isinstance(size, str) and size else None
    merged["window_zoomed"] = bool(state.get("window_zoomed", DEFAULT_APP_STATE["window_zoomed"]))
    font_preset = state.get("font_preset", DEFAULT_APP_STATE["font_preset"])
    legacy_font_map = {
        "标准": "常规",
        "大": "特大",
        "特大": "超大",
    }
    font_preset = legacy_font_map.get(font_preset, font_preset)
    if font_preset not in {"紧凑", "稍小", "常规", "特大", "超大"}:
        font_preset = DEFAULT_APP_STATE["font_preset"]
    merged["font_preset"] = font_preset
    merged["autostart_enabled"] = bool(state.get("autostart_enabled", DEFAULT_APP_STATE["autostart_enabled"]))
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
        self._load_mouse_config = mc.load_config
        self._save_mouse_config = mc.save_config
        self.app_state = load_app_state()

        self.hk_config = self._load_hotkey_config()
        self.hotkey_manager = self._HotkeyManager(self.hk_config)
        self.hotkey_manager.external_trigger_mode = True

        self.hk_running = bool(self.app_state.get("hotkey_running", True))
        self.hotkey_manager.external_trigger_active = self.hk_running
        self.mc_config = self._load_mouse_config()
        self.mc_running = bool(self.app_state.get("mouse_running", True))

        self.trigger_engine = TriggerEngine(self.hotkey_manager, self.mc_config)
        self.mouse_engine = self.trigger_engine
        self.trigger_engine.set_enabled(
            keyboard_enabled=self.hk_running,
            mouse_enabled=self.mc_running,
        )
        self._sync_autostart_state()

    def set_hotkey_self_callback(self, callback):
        self.hotkey_manager.set_self_callback(callback)

    def process_hotkeys(self):
        if self.trigger_engine is None:
            return
        for entry_id in self.trigger_engine.pop_hotkey_events():
            entry = self.hotkey_manager.entry_map.get(entry_id)
            if not entry or not entry.get("enabled", True):
                continue
            try:
                if hasattr(entry["controller"], "callback"):
                    entry["controller"].callback()
                else:
                    entry["controller"].toggle()
            except Exception:
                pass

    def _save_engine_state(self):
        save_app_state(self.app_state)

    def save_window_state(self, size=None, zoomed=None):
        if size is not None:
            self.app_state["window_size"] = size
        if zoomed is not None:
            self.app_state["window_zoomed"] = bool(zoomed)
        self._save_engine_state()

    def save_font_preset(self, font_preset):
        if font_preset not in {"紧凑", "稍小", "常规", "特大", "超大"}:
            return
        self.app_state["font_preset"] = font_preset
        self._save_engine_state()

    def _sync_autostart_state(self):
        self.app_state["autostart_enabled"] = startup_manager.is_enabled()
        self._save_engine_state()

    def get_autostart_enabled(self):
        enabled = startup_manager.is_enabled()
        if self.app_state.get("autostart_enabled") != enabled:
            self.app_state["autostart_enabled"] = enabled
            self._save_engine_state()
        return enabled

    def set_autostart_enabled(self, enabled):
        try:
            if enabled:
                startup_manager.enable()
            else:
                startup_manager.disable()
        except OSError as exc:
            actual = startup_manager.is_enabled()
            self.app_state["autostart_enabled"] = actual
            self._save_engine_state()
            return False, str(exc)
        self.app_state["autostart_enabled"] = bool(enabled)
        self._save_engine_state()
        return True, None

    def start_hotkey(self, persist=True):
        if self.hotkey_manager is None:
            return
        self.hk_running = True
        self.hotkey_manager.external_trigger_active = True
        self.trigger_engine.set_enabled(keyboard_enabled=True)
        self.app_state["hotkey_running"] = True
        if persist:
            self._save_engine_state()

    def stop_hotkey(self, persist=True):
        if self.hotkey_manager is None:
            return
        self.hk_running = False
        self.hotkey_manager.external_trigger_active = False
        self.trigger_engine.set_enabled(keyboard_enabled=False)
        self.app_state["hotkey_running"] = False
        if persist:
            self._save_engine_state()

    def reload_hotkey_config(self):
        self.hk_config = self._load_hotkey_config()

    def start_mouse(self, persist=True):
        if self.trigger_engine is None:
            return
        self.mc_config = self._load_mouse_config()
        self.trigger_engine.update_mouse_config(self.mc_config)
        self.mc_running = True
        self.trigger_engine.set_enabled(mouse_enabled=True)
        self.app_state["mouse_running"] = True
        if persist:
            self._save_engine_state()

    def stop_mouse(self, persist=True):
        if self.trigger_engine is None:
            return
        self.mc_running = False
        self.trigger_engine.set_enabled(mouse_enabled=False)
        self.app_state["mouse_running"] = False
        if persist:
            self._save_engine_state()

    def restart_mouse(self):
        was_running = bool(self.app_state.get("mouse_running", self.mc_running))
        self.mc_config = self._load_mouse_config()
        self.trigger_engine.update_mouse_config(self.mc_config)
        if was_running:
            self.mc_running = True
            self.trigger_engine.set_enabled(mouse_enabled=True)
        else:
            self.mc_running = False

    def save_mouse_config(self, config):
        self.mc_config = config
        self._save_mouse_config(config)
        self.trigger_engine.update_mouse_config(config)

    def reinstall_hooks(self):
        if self.trigger_engine is not None:
            self.trigger_engine.reinstall_hooks()

    def quit(self):
        try:
            self.trigger_engine.shutdown()
        except Exception:
            pass
