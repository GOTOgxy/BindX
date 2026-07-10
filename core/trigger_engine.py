# -*- coding: utf-8 -*-

import ctypes
import threading
import time
from ctypes import wintypes

import keyboard as kb

from . import config_proxy

_hk = config_proxy.hk_module()


class TriggerEngine:
    """Unified low-level keyboard/mouse trigger engine for BindX."""

    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14

    WM_KEYDOWN = 0x0100
    WM_KEYUP = 0x0101
    WM_SYSKEYDOWN = 0x0104
    WM_SYSKEYUP = 0x0105

    WM_LBUTTONDOWN = 0x0201
    WM_LBUTTONUP = 0x0202
    WM_RBUTTONDOWN = 0x0204
    WM_RBUTTONUP = 0x0205
    WM_MBUTTONDOWN = 0x0207
    WM_MBUTTONUP = 0x0208
    WM_XBUTTONDOWN = 0x020B
    WM_XBUTTONUP = 0x020C

    LLKHF_INJECTED = 0x10
    PM_REMOVE = 0x0001

    VK_SHIFT = 0x10
    VK_CONTROL = 0x11
    VK_MENU = 0x12
    VK_LWIN = 0x5B
    VK_RWIN = 0x5C
    VK_LSHIFT = 0xA0
    VK_RSHIFT = 0xA1
    VK_LCONTROL = 0xA2
    VK_RCONTROL = 0xA3
    VK_LMENU = 0xA4
    VK_RMENU = 0xA5

    CTRL_KEYS = {VK_CONTROL, VK_LCONTROL, VK_RCONTROL}
    SHIFT_KEYS = {VK_SHIFT, VK_LSHIFT, VK_RSHIFT}
    ALT_KEYS = {VK_MENU, VK_LMENU, VK_RMENU}
    WIN_KEYS = {VK_LWIN, VK_RWIN}
    MODIFIER_KEYS = CTRL_KEYS | SHIFT_KEYS | ALT_KEYS | WIN_KEYS
    MODIFIER_GROUPS = (CTRL_KEYS, SHIFT_KEYS, ALT_KEYS, WIN_KEYS)

    BUTTON_MAP = {
        "left": (WM_LBUTTONDOWN, WM_LBUTTONUP),
        "right": (WM_RBUTTONDOWN, WM_RBUTTONUP),
        "middle": (WM_MBUTTONDOWN, WM_MBUTTONUP),
        "x1": (WM_XBUTTONDOWN, WM_XBUTTONUP),
        "x2": (WM_XBUTTONDOWN, WM_XBUTTONUP),
    }
    XBUTTON_MAP = {"x1": 1, "x2": 2}

    SPECIAL_KEYS = {
        "tab": 0x09,
        "esc": 0x1B,
        "escape": 0x1B,
        "space": 0x20,
        "enter": 0x0D,
        "return": 0x0D,
        "left": 0x25,
        "up": 0x26,
        "right": 0x27,
        "down": 0x28,
        "home": 0x24,
        "end": 0x23,
        "pageup": 0x21,
        "page down": 0x22,
        "pagedown": 0x22,
        "insert": 0x2D,
        "delete": 0x2E,
        "backspace": 0x08,
        "caps lock": 0x14,
        "capslock": 0x14,
    }

    class KBDLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("vkCode", wintypes.DWORD),
            ("scanCode", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    class MSLLHOOKSTRUCT(ctypes.Structure):
        _fields_ = [
            ("pt", wintypes.POINT),
            ("mouseData", wintypes.DWORD),
            ("flags", wintypes.DWORD),
            ("time", wintypes.DWORD),
            ("dwExtraInfo", ctypes.c_size_t),
        ]

    def __init__(self, hotkey_manager, mouse_config):
        self.hotkey_manager = hotkey_manager
        self.mouse_config = mouse_config

        self.keyboard_enabled = False
        self.mouse_enabled = False
        self.running = False
        self.last_error = None
        self.last_event = "无"
        self.heartbeat = 0.0

        self._thread = None
        self._watchdog_thread = None
        self._stop_event = threading.Event()
        self._watchdog_stop = threading.Event()
        self._lock = threading.RLock()
        self._queue_lock = threading.Lock()
        self._hotkey_queue = []

        self._pressed_vks = set()
        self._active_hotkeys = set()
        self._active_key_mappings = set()
        self._active_hotkey_times = {}
        self._active_key_mapping_times = {}
        self._suppressed_keyups = set()
        self._suppressed_mouse_buttons = set()
        self._user32 = None

    def set_enabled(self, keyboard_enabled=None, mouse_enabled=None):
        with self._lock:
            if keyboard_enabled is not None:
                self.keyboard_enabled = bool(keyboard_enabled)
            if mouse_enabled is not None:
                self.mouse_enabled = bool(mouse_enabled)
            self._sync_hotkey_status()
            if self.keyboard_enabled or self.mouse_enabled:
                self._ensure_running()
            else:
                self._stop_thread()

    def update_mouse_config(self, config):
        with self._lock:
            self.mouse_config = config

    def pop_hotkey_events(self):
        with self._queue_lock:
            events = list(self._hotkey_queue)
            self._hotkey_queue.clear()
        return events

    def reinstall_hooks(self):
        with self._lock:
            self._stop_thread()
            if self.keyboard_enabled or self.mouse_enabled:
                self._ensure_running()

    def shutdown(self):
        self._watchdog_stop.set()
        self._stop_thread()
        thread = self._watchdog_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)

    def _ensure_running(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        if not self._watchdog_thread or not self._watchdog_thread.is_alive():
            self._watchdog_stop.clear()
            self._watchdog_thread = threading.Thread(target=self._watchdog_loop, daemon=True)
            self._watchdog_thread.start()

    def _stop_thread(self):
        self._stop_event.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        if not thread or not thread.is_alive():
            self._thread = None
            self.running = False
            self._pressed_vks.clear()
            self._active_hotkeys.clear()
            self._active_key_mappings.clear()
            self._active_hotkey_times.clear()
            self._active_key_mapping_times.clear()
            self._suppressed_keyups.clear()
            self._suppressed_mouse_buttons.clear()
            self._sync_hotkey_status()

    def _watchdog_loop(self):
        while not self._watchdog_stop.wait(2.0):
            with self._lock:
                desired = self.keyboard_enabled or self.mouse_enabled
                if not desired:
                    continue
                stale = self.running and self.heartbeat and time.monotonic() - self.heartbeat > 5.0
                dead = not self._thread or not self._thread.is_alive()
                if dead or stale:
                    self.last_error = "Hook watchdog restarted trigger engine"
                    self._stop_thread()
                    self._ensure_running()

    def _sync_hotkey_status(self):
        active = bool(self.keyboard_enabled and self.running)
        self.hotkey_manager.external_trigger_active = active
        for entry in self.hotkey_manager.entries:
            entry["registered"] = bool(active and entry.get("enabled", True))
            if entry["registered"]:
                entry["last_error"] = None

    def _run(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        self._user32 = user32

        HOOKPROC = ctypes.WINFUNCTYPE(
            wintypes.LPARAM, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        )
        user32.SetWindowsHookExW.argtypes = [
            ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
        ]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [
            wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
        ]
        user32.CallNextHookEx.restype = wintypes.LPARAM
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        user32.PeekMessageW.argtypes = [
            ctypes.POINTER(wintypes.MSG), wintypes.HWND,
            wintypes.UINT, wintypes.UINT, wintypes.UINT
        ]
        user32.PeekMessageW.restype = wintypes.BOOL
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.TranslateMessage.restype = wintypes.BOOL
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.restype = wintypes.LPARAM
        user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
        user32.GetAsyncKeyState.restype = ctypes.c_short
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        keyboard_proc = HOOKPROC(self._keyboard_proc)
        mouse_proc = HOOKPROC(self._mouse_proc)
        hinst = kernel32.GetModuleHandleW(None)
        keyboard_hook = user32.SetWindowsHookExW(self.WH_KEYBOARD_LL, keyboard_proc, hinst, 0)
        mouse_hook = user32.SetWindowsHookExW(self.WH_MOUSE_LL, mouse_proc, hinst, 0)

        if not keyboard_hook or not mouse_hook:
            self.last_error = f"SetWindowsHookExW failed: {ctypes.get_last_error()}"
            if keyboard_hook:
                user32.UnhookWindowsHookEx(keyboard_hook)
            if mouse_hook:
                user32.UnhookWindowsHookEx(mouse_hook)
            self.running = False
            self._sync_hotkey_status()
            return

        self.running = True
        self.last_error = None
        self._sync_hotkey_status()
        msg = wintypes.MSG()

        try:
            while not self._stop_event.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, self.PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                self.heartbeat = time.monotonic()
                time.sleep(0.01)
        finally:
            user32.UnhookWindowsHookEx(keyboard_hook)
            user32.UnhookWindowsHookEx(mouse_hook)
            self.running = False
            self._sync_hotkey_status()

    def _keyboard_proc(self, n_code, w_param, l_param):
        if n_code < 0:
            return self._call_next_keyboard(n_code, w_param, l_param)

        info = ctypes.cast(l_param, ctypes.POINTER(self.KBDLLHOOKSTRUCT)).contents
        if info.flags & self.LLKHF_INJECTED:
            return self._call_next_keyboard(n_code, w_param, l_param)

        vk = int(info.vkCode)
        is_down = w_param in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN)
        is_up = w_param in (self.WM_KEYUP, self.WM_SYSKEYUP)

        if is_down:
            self._sync_modifier_state(exclude_vk=vk)
            was_pressed = vk in self._pressed_vks
            self._pressed_vks.add(vk)
            if was_pressed:
                return 1 if vk in self._suppressed_keyups else self._call_next_keyboard(n_code, w_param, l_param)
            if self.keyboard_enabled:
                if self._match_hotkey(vk):
                    self._suppressed_keyups.add(vk)
                    self._suppressed_keyups.update(self._pressed_vks & self.MODIFIER_KEYS)
                    return 1
                if self._match_key_mapping(vk):
                    self._suppressed_keyups.add(vk)
                    self._suppressed_keyups.update(self._pressed_vks & self.MODIFIER_KEYS)
                    return 1
        elif is_up:
            self._sync_modifier_state(exclude_vk=vk)
            self._pressed_vks.discard(vk)
            self._release_active_triggers(vk)
            if vk in self.MODIFIER_KEYS:
                self._clear_chord_state()
            if vk in self._suppressed_keyups:
                self._suppressed_keyups.discard(vk)
                return 1

        return self._call_next_keyboard(n_code, w_param, l_param)

    def _clear_chord_state(self):
        self._active_hotkeys.clear()
        self._active_key_mappings.clear()
        self._active_hotkey_times.clear()
        self._active_key_mapping_times.clear()
        self._suppressed_keyups.clear()
        self._pressed_vks = {vk for vk in self._pressed_vks if vk in self.MODIFIER_KEYS}
        self._sync_modifier_state()

    def _sync_modifier_state(self, exclude_vk=None):
        user32 = self._user32
        if user32 is None:
            return
        live_modifiers = set()
        for group in self.MODIFIER_GROUPS:
            if exclude_vk in group:
                live_modifiers.update(vk for vk in self._pressed_vks if vk in group)
                continue
            for candidate in group:
                try:
                    if user32.GetAsyncKeyState(candidate) & 0x8000:
                        live_modifiers.add(candidate)
                except Exception:
                    break
        self._pressed_vks = {vk for vk in self._pressed_vks if vk not in self.MODIFIER_KEYS}
        self._pressed_vks.update(live_modifiers)

    def _mouse_proc(self, n_code, w_param, l_param):
        if n_code < 0 or not self.mouse_enabled:
            return self._call_next_mouse(n_code, w_param, l_param)

        info = ctypes.cast(l_param, ctypes.POINTER(self.MSLLHOOKSTRUCT)).contents
        for mapping in self.mouse_config.get("mouse_mappings", []):
            if not mapping.get("enabled", True):
                continue
            btn = mapping.get("button")
            if btn not in self.BUTTON_MAP:
                continue
            down_msg, up_msg = self.BUTTON_MAP[btn]
            if w_param == down_msg:
                if btn in self.XBUTTON_MAP:
                    xbtn = info.mouseData >> 16
                    if xbtn != self.XBUTTON_MAP[btn]:
                        continue
                self._suppressed_mouse_buttons.add(btn)
                self.last_event = f"Mouse {btn} -> {'+'.join(mapping.get('output', []))}"
                threading.Thread(target=self._do_output, args=(mapping.get("output", []),), daemon=True).start()
                return 1
            if w_param == up_msg and btn in self._suppressed_mouse_buttons:
                self._suppressed_mouse_buttons.discard(btn)
                return 1
        return self._call_next_mouse(n_code, w_param, l_param)

    def _call_next_keyboard(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _call_next_mouse(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _current_modifiers(self):
        modifiers = 0
        if self._pressed_vks & self.CTRL_KEYS:
            modifiers |= _hk.MOD_CONTROL
        if self._pressed_vks & self.SHIFT_KEYS:
            modifiers |= _hk.MOD_SHIFT
        if self._pressed_vks & self.ALT_KEYS:
            modifiers |= _hk.MOD_ALT
        if self._pressed_vks & self.WIN_KEYS:
            modifiers |= _hk.MOD_WIN
        return modifiers

    def _match_hotkey(self, vk):
        if vk in self.MODIFIER_KEYS:
            return False
        current_mods = self._current_modifiers()
        for entry in self.hotkey_manager.entries:
            if not entry.get("enabled", True):
                continue
            if entry["virtual_key"] != vk or entry["modifiers"] != current_mods:
                continue
            entry_id = entry["id"]
            if entry_id in self._active_hotkeys:
                if time.monotonic() - self._active_hotkey_times.get(entry_id, 0) < 0.25:
                    return True
                self._active_hotkeys.discard(entry_id)
            self._active_hotkeys.add(entry_id)
            self._active_hotkey_times[entry_id] = time.monotonic()
            with self._queue_lock:
                self._hotkey_queue.append(entry_id)
            self.last_event = f"HotKey {entry['hotkey']}"
            return True
        return False

    def _match_key_mapping(self, vk):
        if vk in self.MODIFIER_KEYS:
            return False
        current_mods = self._current_modifiers()
        for idx, mapping in enumerate(self.mouse_config.get("mappings", [])):
            if not mapping.get("enabled", True):
                continue
            parsed = self._parse_combo(mapping.get("trigger", []))
            if parsed is None:
                continue
            trigger_mods, trigger_vk = parsed
            if trigger_vk != vk or trigger_mods != current_mods:
                continue
            if idx in self._active_key_mappings:
                if time.monotonic() - self._active_key_mapping_times.get(idx, 0) < 0.25:
                    return True
                self._active_key_mappings.discard(idx)
            self._active_key_mappings.add(idx)
            self._active_key_mapping_times[idx] = time.monotonic()
            self.last_event = f"Key {'+'.join(mapping.get('trigger', []))} -> {'+'.join(mapping.get('output', []))}"
            threading.Thread(target=self._do_output, args=(mapping.get("output", []),), daemon=True).start()
            return True
        return False

    def _release_active_triggers(self, vk):
        for entry in self.hotkey_manager.entries:
            if entry.get("virtual_key") == vk:
                self._active_hotkeys.discard(entry["id"])
                self._active_hotkey_times.pop(entry["id"], None)
        for idx, mapping in enumerate(self.mouse_config.get("mappings", [])):
            parsed = self._parse_combo(mapping.get("trigger", []))
            if parsed and parsed[1] == vk:
                self._active_key_mappings.discard(idx)
                self._active_key_mapping_times.pop(idx, None)

    def _parse_combo(self, keys):
        if not isinstance(keys, (list, tuple)):
            return None
        modifiers = 0
        key_vk = None
        for key in keys:
            name = self._normalize_key_name(str(key))
            if name in ("ctrl", "control"):
                modifiers |= _hk.MOD_CONTROL
            elif name == "shift":
                modifiers |= _hk.MOD_SHIFT
            elif name == "alt":
                modifiers |= _hk.MOD_ALT
            elif name in ("win", "windows", "cmd"):
                modifiers |= _hk.MOD_WIN
            else:
                vk = self._key_name_to_vk(name)
                if vk is None or key_vk is not None:
                    return None
                key_vk = vk
        if key_vk is None:
            return None
        return modifiers, key_vk

    def _key_name_to_vk(self, name):
        upper = name.upper()
        if len(upper) == 1 and ("A" <= upper <= "Z" or "0" <= upper <= "9"):
            return ord(upper)
        if upper.startswith("F") and upper[1:].isdigit():
            num = int(upper[1:])
            if 1 <= num <= 24:
                return 0x6F + num
        return self.SPECIAL_KEYS.get(name)

    @staticmethod
    def _normalize_key_name(name):
        name = name.strip().lower().replace("_", " ")
        mapping = {
            "ctrl l": "ctrl",
            "ctrl r": "ctrl",
            "control l": "ctrl",
            "control r": "ctrl",
            "shift l": "shift",
            "shift r": "shift",
            "alt l": "alt",
            "alt r": "alt",
            "windows": "win",
            "cmd": "win",
        }
        return mapping.get(name, name)

    @staticmethod
    def _normalize_output_keys(keys):
        if isinstance(keys, str):
            if "+" not in keys:
                return []
            keys = keys.split("+")
        if not isinstance(keys, (list, tuple)):
            return []
        return [str(k).strip().lower() for k in keys if str(k).strip()]

    def _do_output(self, keys):
        output = self._normalize_output_keys(keys)
        if not output:
            return
        pressed = []
        try:
            time.sleep(0.02)
            for key in output:
                kb.press(key)
                pressed.append(key)
            for key in reversed(pressed):
                kb.release(key)
        finally:
            for key in reversed(pressed):
                try:
                    kb.release(key)
                except Exception:
                    pass
