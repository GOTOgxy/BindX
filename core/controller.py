# -*- coding: utf-8 -*-

"""BindX trigger controller。

HotKeyManager 仍负责热键配置 CRUD 和 AppController 动作；TriggerEngine 负责统一
WH_KEYBOARD_LL / WH_MOUSE_LL 低层 hook、触发匹配与 hook 自恢复。
"""

import threading

from . import config_proxy, config_store, startup_manager
from .trigger_engine import TriggerEngine


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
        # 标准热键（带修饰键）改由原生 RegisterHotKey 注册，
        # 不再需要 external_trigger_mode；LL 钩子仅在存在
        # 无修饰键热键或启用的按键/鼠标映射时才安装。

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
        self.trigger_engine.set_output_options(
            delay_ms=self.app_state.get("output_delay_ms", 20),
            restore_held_modifiers=self.app_state.get("restore_held_modifiers", True),
        )
        # 原生热键轮询线程：把启用的带修饰键热键通过 RegisterHotKey
        # 注册（零侵入）；主线程定时器经 process_hotkeys() 消费
        # pop_hotkey_events() 分发。
        self.hotkey_manager.start_polling_thread(register_enabled=self.hk_running)
        self._wrap_hotkey_crud()
        self._sync_autostart_state()

    def set_hotkey_self_callback(self, callback):
        self.hotkey_manager.set_self_callback(callback)

    def process_hotkeys(self):
        # Tk 主线程定时器调用：消费两路热键事件——
        # TriggerEngine 钩子队列（无修饰键热键）与
        # 原生 RegisterHotKey 队列（标准修饰键热键）。
        if self.trigger_engine is None:
            return
        event_ids = list(self.trigger_engine.pop_hotkey_events())
        try:
            event_ids.extend(self.hotkey_manager.pop_hotkey_events())
        except Exception:
            pass
        for entry_id in event_ids:
            self._dispatch_hotkey(entry_id)

    def _dispatch_hotkey(self, entry_id):
        entry = self.hotkey_manager.entry_map.get(entry_id)
        if not entry or not entry.get("enabled", True):
            return
        controller = entry.get("controller")
        if controller is None:
            return
        # BindX 自身的热键回调（如显示/隐藏主窗口）是 Tk 操作，
        # 必须在 Tk 主线程执行；其余 AppController 动作（激活/隐藏/
        # 启动目标窗口）是慢速 Win32 跨进程调用，在主线程里执行会
        # 长时间占用 GIL，饿死 hook 线程（输入卡顿的根源之一），
        # 放到后台线程并加 in-flight 保护避免同一动作并发。
        if hasattr(controller, "callback"):
            self._invoke_hotkey_action(entry)
        else:
            self._spawn_hotkey_action(entry)

    def _invoke_hotkey_action(self, entry):
        try:
            entry["controller"].callback()
        except Exception as error:
            entry["last_error"] = str(error)

    def _spawn_hotkey_action(self, entry):
        if entry.get("_action_inflight"):
            return
        entry["_action_inflight"] = True
        thread = threading.Thread(
            target=self._run_hotkey_action, args=(entry,), daemon=True
        )
        thread.start()

    def _run_hotkey_action(self, entry):
        try:
            entry["controller"].toggle()
        except Exception as error:
            entry["last_error"] = str(error)
        finally:
            entry["_action_inflight"] = False

    def _wrap_hotkey_crud(self):
        # GUI 直接对 hotkey_manager 调 CRUD（绕过 controller）；
        # CRUD 后通知 TriggerEngine 重新评估是否需要低级钩子
        # （新增无修饰键热键/按键映射需要钩子；恢复全原生则卸载）。
        manager = self.hotkey_manager
        engine = self.trigger_engine
        for name in (
            "add_entry", "update_entry", "remove_entry",
            "toggle_entry", "set_launch_if_not_running",
        ):
            original = getattr(manager, name)

            def wrapped(*args, _original=original, **kwargs):
                result = _original(*args, **kwargs)
                try:
                    engine.notify_hotkeys_changed()
                except Exception:
                    pass
                return result

            wrapped.__name__ = name
            setattr(manager, name, wrapped)

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

    def set_output_options(self, delay_ms=None, restore_held_modifiers=None):
        if delay_ms is not None:
            try:
                delay_ms = int(delay_ms)
            except (TypeError, ValueError):
                delay_ms = 20
            delay_ms = max(0, min(delay_ms, 500))
            self.app_state["output_delay_ms"] = delay_ms
        if restore_held_modifiers is not None:
            self.app_state["restore_held_modifiers"] = bool(restore_held_modifiers)
        self.trigger_engine.set_output_options(
            delay_ms=self.app_state.get("output_delay_ms", 20),
            restore_held_modifiers=self.app_state.get("restore_held_modifiers", True),
        )
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
        # 原生模式：重新注册所有启用的带修饰键热键（进入 poll 线程队列）
        try:
            self.hotkey_manager.register_all()
        except Exception:
            pass
        self.trigger_engine.set_enabled(keyboard_enabled=True)
        self.app_state["hotkey_running"] = True
        if persist:
            self._save_engine_state()

    def stop_hotkey(self, persist=True):
        if self.hotkey_manager is None:
            return
        self.hk_running = False
        self.hotkey_manager.external_trigger_active = False
        try:
            self.hotkey_manager.unregister_all()
        except Exception:
            pass
        self.trigger_engine.set_enabled(keyboard_enabled=False)
        self.app_state["hotkey_running"] = False
        if persist:
            self._save_engine_state()

    def reload_hotkey_config(self):
        self.hk_config = self._load_hotkey_config()

    def reload_all_config(self):
        self_cb = None
        for entry in self.hotkey_manager.entries:
            if entry.get("config_entry", {}).get("app") == "hot_key_manager":
                ctrl = entry.get("controller")
                if ctrl is not None and hasattr(ctrl, "callback"):
                    self_cb = ctrl.callback
                break
        # 先停旧 manager 的轮询线程（卸载其原生热键、销毁消息窗口），
        # 避免残留注册造成重复触发
        try:
            self.hotkey_manager.stop_polling_thread()
        except Exception:
            pass
        self.hk_config = self._load_hotkey_config()
        self.hotkey_manager = self._HotkeyManager(self.hk_config)
        self.hotkey_manager.external_trigger_active = self.hk_running
        if self_cb is not None:
            self.hotkey_manager.set_self_callback(self_cb)
        self.hotkey_manager.start_polling_thread(register_enabled=self.hk_running)
        self.trigger_engine.hotkey_manager = self.hotkey_manager
        self.mc_config = self._load_mouse_config()
        self.trigger_engine.update_mouse_config(self.mc_config)
        self._wrap_hotkey_crud()

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
        try:
            if self.hotkey_manager is not None:
                self.hotkey_manager.stop_polling_thread()
        except Exception:
            pass
