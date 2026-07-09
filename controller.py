# -*- coding: utf-8 -*-

"""BindX trigger controller。

HotKeyManager 仍负责热键配置 CRUD 和 AppController 动作；TriggerEngine 负责统一
WH_KEYBOARD_LL / WH_MOUSE_LL 低层 hook、触发匹配与 hook 自恢复。
"""

import config_proxy
import config_store
import startup_manager
from trigger_engine import TriggerEngine


class BindXController:
    def __init__(self):
        hk = config_proxy.hk_module()
        mc = config_proxy.mc_engine_module()

        self._HotkeyManager = hk.HotkeyManager
        self._load_hotkey_config = hk.load_config
        self._load_mouse_config = mc.load_config
        self._save_mouse_config = mc.save_config
        self.app_state = config_store.load_app_state()

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
        config_store.save_app_state(self.app_state)

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
