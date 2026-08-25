# -*- coding: utf-8 -*-

import ctypes
import os
import threading
import time
from collections import deque
from ctypes import wintypes

from . import config_proxy

_hk = config_proxy.hk_module()

# ---------------------------------------------------------------------------
# 直接 SendInput 键盘注入
#
# 旧版用 `keyboard` 库注入：该库会另外安装一个 WH_KEYBOARD_LL 全局 hook
# 和专用消息线程，每个按键事件都要被两个 Python 级 hook 各处理一遍
# （输入延迟、GIL 竞争、hook 被系统移除的诱因）；而且它对修饰键的
# "恢复按下"从不释放，会污染系统修饰键状态。
# 现在改为在输出 worker 线程直接 SendInput：每次注入仅两次系统调用
# （全部按下 / 全部抬起），绝不触碰用户物理按住的键。
# ---------------------------------------------------------------------------

INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
BINDX_INJECTION_TAG = 0x58444E42  # "BDNX"，BindX 注入事件的 dwExtraInfo 标记


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUT_UNION)]


def _tb_text():
    import traceback
    return traceback.format_exc()


def _make_send_input():
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(_INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    return user32.SendInput


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
    WM_MOUSEWHEEL = 0x020A
    WM_MOUSEHWHEEL = 0x020E
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
    MODIFIER_KEY_NAMES = {
        VK_LSHIFT: "left shift",
        VK_RSHIFT: "right shift",
        VK_LCONTROL: "left ctrl",
        VK_RCONTROL: "right ctrl",
        VK_LMENU: "left alt",
        VK_RMENU: "right alt",
        VK_LWIN: "left windows",
        VK_RWIN: "right windows",
    }

    # 修饰键组名归一化：具体名（left ctrl 等）与通用名（ctrl 等）都映射到同一个组，
    # 用于判断"用户物理按住的修饰键"与"输出组合中的修饰键"是否属于同一组
    _MODIFIER_GROUP_ALIASES = {
        "ctrl": "ctrl",
        "control": "ctrl",
        "left ctrl": "ctrl",
        "right ctrl": "ctrl",
        "shift": "shift",
        "left shift": "shift",
        "right shift": "shift",
        "alt": "alt",
        "altgr": "alt",
        "left alt": "alt",
        "right alt": "alt",
        "win": "win",
        "windows": "win",
        "cmd": "win",
        "super": "win",
        "left windows": "win",
        "right windows": "win",
    }
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
        "num0": 0x60,
        "num1": 0x61,
        "num2": 0x62,
        "num3": 0x63,
        "num4": 0x64,
        "num5": 0x65,
        "num6": 0x66,
        "num7": 0x67,
        "num8": 0x68,
        "num9": 0x69,
        "numpad0": 0x60,
        "numpad1": 0x61,
        "numpad2": 0x62,
        "numpad3": 0x63,
        "numpad4": 0x64,
        "numpad5": 0x65,
        "numpad6": 0x66,
        "numpad7": 0x67,
        "numpad8": 0x68,
        "numpad9": 0x69,
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
        self._physical_modifiers = set()
        self._active_hotkeys = set()
        self._active_key_mappings = set()
        self._active_hotkey_times = {}
        self._active_key_mapping_times = {}
        self._suppressed_keyups = set()
        self._suppressed_mouse_buttons = set()
        self._user32 = None

        # A3: 输出延迟与是否恢复物理按住的修饰键
        self._output_delay_ms = 20
        self._restore_held_modifiers = True
        # A1: 线程停止时的按键状态快照，下次启动恢复
        self._snap_pressed = None
        self._snap_suppressed = None
        # A4: 输出队列与 worker 线程（串行化输出）
        self._output_queue = []
        self._output_worker = None
        # 钩子回调延迟统计
        self._slow_hook_count = 0
        # B5: 注入事件日志（供按键检查器标注 BindX 注入）
        self._injection_log = deque(maxlen=128)
        self._injection_log_lock = threading.Lock()
        # SendInput 函数（仅输出 worker 线程调用）
        self._send_input = _make_send_input()
        # 预计算的触发索引（配置更新时重建；hook 回调只做查表）
        self._mouse_button_map = {}
        self._down_to_btn = {}
        self._up_to_btn = {}
        self._key_mappings = []
        self._rebuild_mouse_index()

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
            self._rebuild_mouse_index()

    def set_output_options(self, delay_ms=None, restore_held_modifiers=None):
        with self._lock:
            if delay_ms is not None:
                try:
                    delay_ms = int(delay_ms)
                except (TypeError, ValueError):
                    delay_ms = 20
                self._output_delay_ms = max(0, delay_ms)
            # 兼容字段：新版本不再"抬起/恢复"用户物理按住的修饰键
            # （旧行为正是"组合键退化成纯字母键"和"幻影修饰键误触热键"的根源），
            # 保留该设置只为兼容旧配置，不再起作用。
            if restore_held_modifiers is not None:
                self._restore_held_modifiers = bool(restore_held_modifiers)

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
            # A1: 快照当前按键状态，钩子重装后恢复
            self._snap_pressed = set(self._pressed_vks)
            self._snap_suppressed = set(self._suppressed_keyups)
            self._pressed_vks.clear()
            self._physical_modifiers.clear()
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
                    age = (time.monotonic() - self.heartbeat) if self.heartbeat else -1.0
                    self._diag_log(
                        f"watchdog restarted hook thread: dead={dead}, stale={stale}, "
                        f"running={self.running}, heartbeat_age={age:.2f}s"
                    )
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
        self._slow_hook_count = 0
        self._physical_modifiers = {
            vk for vk in self.MODIFIER_KEYS
            if user32.GetAsyncKeyState(vk) & 0x8000
        }
        # A1: 恢复上次停止前的按键状态快照，过滤已不再物理按住的键
        snap_pressed = self._snap_pressed
        snap_suppressed = self._snap_suppressed
        self._snap_pressed = None
        self._snap_suppressed = None
        if snap_pressed is not None:
            snap_suppressed = snap_suppressed or set()
            self._pressed_vks = {
                vk for vk in snap_pressed if user32.GetAsyncKeyState(vk) & 0x8000
            } | self._physical_modifiers
            self._suppressed_keyups = {
                vk for vk in snap_suppressed if vk in self._pressed_vks
            }
        try:
            self._sync_hotkey_status()
            # A4: 启动输出队列 worker 线程
            self._output_worker = threading.Thread(target=self._output_worker_loop, daemon=True)
            self._output_worker.start()
        except Exception:
            self._diag_log("hook startup exception:\n" + _tb_text())
            self.last_error = "Hook startup crashed (see data/bindx_hook_error.log)"
            user32.UnhookWindowsHookEx(keyboard_hook)
            user32.UnhookWindowsHookEx(mouse_hook)
            self.running = False
            return
        # user32 导出的是 MsgWaitForMultipleObjects（没有 W/Ex 后缀变体，
        # 注意别写成 MsgWaitForMultipleObjectsW——该符号不存在）
        user32.MsgWaitForMultipleObjects.argtypes = [
            wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE),
            wintypes.BOOL, wintypes.DWORD, wintypes.DWORD,
        ]
        user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD
        QS_ALLINPUT = 0x04FF
        msg = wintypes.MSG()

        try:
            while not self._stop_event.is_set():
                # 旧实现是 PeekMessage + sleep(10ms)：高频鼠标事件最多要等
                # 10ms 才被派发，移动会成批出现，表现为明显卡顿。
                # MsgWaitForMultipleObjectsW 一有输入立即唤醒，
                # 100ms 超时仅用于检测停止标志。
                try:
                    user32.MsgWaitForMultipleObjects(0, None, False, 100, QS_ALLINPUT)
                    while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, self.PM_REMOVE):
                        user32.TranslateMessage(ctypes.byref(msg))
                        user32.DispatchMessageW(ctypes.byref(msg))
                except Exception:
                    self._diag_log("hook message pump exception:\n" + _tb_text())
                    self.last_error = "Hook pump crashed (see data/bindx_hook_error.log)"
                    break
                self.heartbeat = time.monotonic()
        finally:
            user32.UnhookWindowsHookEx(keyboard_hook)
            user32.UnhookWindowsHookEx(mouse_hook)
            self.running = False
            # A4: 排空输出队列并等待 worker 退出
            with self._queue_lock:
                self._output_queue.clear()
            worker = self._output_worker
            self._output_worker = None
            if worker is not None and worker is not threading.current_thread():
                worker.join(timeout=1.0)
            self._sync_hotkey_status()

    def _output_worker_loop(self):
        while True:
            if self._stop_event.is_set():
                break
            keys = None
            with self._queue_lock:
                if self._output_queue:
                    keys = self._output_queue.pop(0)
            if keys is None:
                time.sleep(0.005)
                continue
            try:
                self._do_output(keys)
            except Exception:
                self._diag_log("output worker exception:\n" + _tb_text())
        # 退出前排空残余输出
        with self._queue_lock:
            remaining = list(self._output_queue)
            self._output_queue.clear()
        for keys in remaining:
            try:
                self._do_output(keys)
            except Exception:
                self._diag_log("output worker drain exception:\n" + _tb_text())

    def _note_hook_latency(self, started):
        if time.monotonic() - started > 0.1:
            self._slow_hook_count += 1
            if self._slow_hook_count == 1:
                self.last_error = "Hook callback is slow (over 100ms); input may feel laggy"

    def _diag_log(self, message):
        # 诊断日志：pythonw 没有控制台，hook 线程/回调/消息泵的异常绝不能静默。
        # 统一追加到 data/bindx_hook_error.log 供事后排查。
        try:
            base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            path = os.path.join(base, "data", "bindx_hook_error.log")
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "a", encoding="utf-8") as f:
                f.write(f"[{stamp}] {message}\n")
        except Exception:
            pass

    def _keyboard_proc(self, n_code, w_param, l_param):
        started = time.monotonic()
        try:
            return self._keyboard_proc_impl(n_code, w_param, l_param)
        except Exception:
            # 异常传播进原生 hook 派发会导致行为未定义（pythonw 下完全无输出）。
            # 记录日志并退回"放行"。
            self._diag_log("keyboard hook exception:\n" + _tb_text())
            try:
                return self._call_next_keyboard(n_code, w_param, l_param)
            except Exception:
                return 0
        finally:
            self._note_hook_latency(started)

    def _keyboard_proc_impl(self, n_code, w_param, l_param):
        if n_code < 0:
            return self._call_next_keyboard(n_code, w_param, l_param)

        info = ctypes.cast(l_param, ctypes.POINTER(self.KBDLLHOOKSTRUCT)).contents
        if info.flags & self.LLKHF_INJECTED:
            return self._call_next_keyboard(n_code, w_param, l_param)

        vk = int(info.vkCode)
        is_down = w_param in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN)
        is_up = w_param in (self.WM_KEYUP, self.WM_SYSKEYUP)

        if is_down:
            if vk in self.MODIFIER_KEYS:
                self._physical_modifiers.add(vk)
            self._sync_modifier_state(exclude_vk=vk)
            was_pressed = vk in self._pressed_vks
            self._pressed_vks.add(vk)
            if was_pressed:
                return 1 if vk in self._suppressed_keyups else self._call_next_keyboard(n_code, w_param, l_param)
            if self.keyboard_enabled:
                if self._match_hotkey(vk):
                    self._suppressed_keyups.add(vk)
                    return 1
                if self._match_key_mapping(vk):
                    self._suppressed_keyups.add(vk)
                    return 1
        elif is_up:
            if vk in self.MODIFIER_KEYS:
                self._physical_modifiers.discard(vk)
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
        # A2: 保留仍按住的键的抑制记录，避免组合状态清除后
        # 被抑制键的物理 key-up 穿透。
        # 注意：仍被物理按住的非修饰键必须保留在 _pressed_vks 中
        # （它们的 key-up 尚未到达），后续 auto-repeat 才会被正确吞掉；
        # 旧实现把它们全部清掉，导致松开某个修饰键后，还在按住的键
        # 的重复事件会以不同的组合（或纯字母）泄漏给目标程序。
        self._suppressed_keyups = {vk for vk in self._suppressed_keyups if vk in self._pressed_vks}
        self._sync_modifier_state()

    def _sync_modifier_state(self, exclude_vk=None):
        # 修饰键状态只以 _physical_modifiers（物理按键事件）为准；
        # 引擎启动/重启时已用 GetAsyncKeyState 做一次性初始化。
        # 旧实现每次按键事件都参考 GetAsyncKeyState，而该状态会被注入事件
        # 污染（尤其是旧版"恢复按下"的修饰键从不释放），产生幻影修饰键——
        # 这是"按纯字母键误触组合热键、乱启动程序"的根源。
        # 同时省掉了每次按键 8 个 GetAsyncKeyState 系统调用。
        self._pressed_vks = {vk for vk in self._pressed_vks if vk not in self.MODIFIER_KEYS}

    def _mouse_proc(self, n_code, w_param, l_param):
        started = time.monotonic()
        try:
            return self._mouse_proc_impl(n_code, w_param, l_param)
        except Exception:
            self._diag_log("mouse hook exception:\n" + _tb_text())
            try:
                return self._call_next_mouse(n_code, w_param, l_param)
            except Exception:
                return 0
        finally:
            self._note_hook_latency(started)

    def _mouse_proc_impl(self, n_code, w_param, l_param):
        if n_code < 0 or not self.mouse_enabled:
            return self._call_next_mouse(n_code, w_param, l_param)

        # 绝大多数事件是移动类事件：直接透传给下一个 hook，
        # 不做任何额外处理，消除高回报率鼠标下的主要卡顿来源。
        if w_param == self.WM_XBUTTONDOWN or w_param == self.WM_XBUTTONUP:
            info = ctypes.cast(l_param, ctypes.POINTER(self.MSLLHOOKSTRUCT)).contents
            xbtn = (int(info.mouseData) >> 16) & 0xFFFF
            btn = {1: "x1", 2: "x2"}.get(xbtn)
            if btn is None:
                return self._call_next_mouse(n_code, w_param, l_param)
            if w_param == self.WM_XBUTTONDOWN:
                mapping = self._mouse_button_map.get(btn)
                if mapping is not None:
                    self._trigger_mouse(btn, mapping)
                    return 1
            elif btn in self._suppressed_mouse_buttons:
                self._suppressed_mouse_buttons.discard(btn)
                return 1
            return self._call_next_mouse(n_code, w_param, l_param)

        btn = self._down_to_btn.get(w_param)
        if btn is not None:
            mapping = self._mouse_button_map.get(btn)
            if mapping is not None:
                self._trigger_mouse(btn, mapping)
                return 1
            return self._call_next_mouse(n_code, w_param, l_param)

        btn = self._up_to_btn.get(w_param)
        if btn is not None and btn in self._suppressed_mouse_buttons:
            self._suppressed_mouse_buttons.discard(btn)
            return 1

        if w_param in (self.WM_MOUSEWHEEL, self.WM_MOUSEHWHEEL):
            # 滚轮不参与触发；顺手同步内部修饰键状态
            # （新版 _sync_modifier_state 不再调用 GetAsyncKeyState，开销可忽略）。
            self._sync_modifier_state()

        return self._call_next_mouse(n_code, w_param, l_param)

    def _trigger_mouse(self, btn, mapping):
        self._suppressed_mouse_buttons.add(btn)
        self.last_event = f"Mouse {btn} -> {'+'.join(mapping.get('output', []))}"
        with self._queue_lock:
            self._output_queue.append(list(mapping.get("output", [])))

    def _call_next_keyboard(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _call_next_mouse(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _current_modifiers(self):
        # 只用物理修饰键状态做匹配。_pressed_vks 曾混入 GetAsyncKeyState
        # 补充的幻影修饰键（被注入事件污染），会导致纯字母键误判成组合键。
        modifiers = 0
        if self._physical_modifiers & self.CTRL_KEYS:
            modifiers |= _hk.MOD_CONTROL
        if self._physical_modifiers & self.SHIFT_KEYS:
            modifiers |= _hk.MOD_SHIFT
        if self._physical_modifiers & self.ALT_KEYS:
            modifiers |= _hk.MOD_ALT
        if self._physical_modifiers & self.WIN_KEYS:
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
        # 使用预计算索引；旧实现每次 key-down 都对每个 mapping 现场
        # _parse_combo 解析字符串。
        for idx, mapping, parsed in self._key_mappings:
            if parsed is None or not mapping.get("enabled", True):
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
            with self._queue_lock:
                self._output_queue.append(list(mapping.get("output", [])))
            return True
        return False

    def _held_modifier_names(self):
        # 只依据物理按键跟踪，避免把注入事件的逻辑状态误当成用户真实按键
        held = frozenset()
        for _ in range(3):
            try:
                held = frozenset(self._physical_modifiers)
                break
            except RuntimeError:
                continue
        return [
            name for vk, name in self.MODIFIER_KEY_NAMES.items()
            if vk in held
        ]

    def _release_active_triggers(self, vk):
        for entry in self.hotkey_manager.entries:
            if entry.get("virtual_key") == vk:
                self._active_hotkeys.discard(entry["id"])
                self._active_hotkey_times.pop(entry["id"], None)
        for idx, _mapping, parsed in self._key_mappings:
            if parsed is not None and parsed[1] == vk:
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

    # 输出键名 -> 虚拟键码（修饰键固定用左侧 vk，与旧 keyboard 库行为一致）
    _OUTPUT_MODIFIER_VKS = {
        "ctrl": VK_LCONTROL,
        "control": VK_LCONTROL,
        "left ctrl": VK_LCONTROL,
        "right ctrl": VK_RCONTROL,
        "shift": VK_LSHIFT,
        "left shift": VK_LSHIFT,
        "right shift": VK_RSHIFT,
        "alt": VK_LMENU,
        "left alt": VK_LMENU,
        "right alt": VK_RMENU,
        "altgr": VK_RMENU,
        "win": VK_LWIN,
        "windows": VK_LWIN,
        "cmd": VK_LWIN,
        "super": VK_LWIN,
        "left windows": VK_LWIN,
        "right windows": VK_RWIN,
    }

    def _output_key_to_vk(self, name):
        n = str(name).strip().lower()
        if not n:
            return None
        if n in self._OUTPUT_MODIFIER_VKS:
            return self._OUTPUT_MODIFIER_VKS[n]
        if n.startswith("num") and len(n) == 4 and n[3:].isdigit():
            return 0x60 + int(n[3])
        return self._key_name_to_vk(n)

    def _rebuild_mouse_index(self):
        """预计算 hook 回调用的触发索引；回调只查表，不再遍历配置/解析字符串。"""
        mouse_map = {}
        down_to_btn = {}
        up_to_btn = {}
        for mapping in self.mouse_config.get("mouse_mappings", []):
            if not mapping.get("enabled", True):
                continue
            btn = mapping.get("button")
            if btn not in self.BUTTON_MAP or btn in mouse_map:
                continue
            mouse_map[btn] = mapping
            if btn not in self.XBUTTON_MAP:
                down_to_btn[self.BUTTON_MAP[btn][0]] = btn
                up_to_btn[self.BUTTON_MAP[btn][1]] = btn
        key_mappings = []
        for idx, mapping in enumerate(self.mouse_config.get("mappings", [])):
            key_mappings.append((idx, mapping, self._parse_combo(mapping.get("trigger", []))))
        self._mouse_button_map = mouse_map
        self._down_to_btn = down_to_btn
        self._up_to_btn = up_to_btn
        self._key_mappings = key_mappings

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

    @classmethod
    def _modifier_group(cls, name):
        return cls._MODIFIER_GROUP_ALIASES.get(str(name).strip().lower())

    def _do_output(self, keys):
        output = self._normalize_output_keys(keys)
        if not output:
            return
        # 用户当前物理按住的修饰键组
        held_mod_groups = set()
        for n in self._held_modifier_names():
            group = self._modifier_group(n)
            if group:
                held_mod_groups.add(group)
        press_vks = []
        unknown = []
        for key in output:
            group = self._modifier_group(key)
            if group and group in held_mod_groups:
                # 用户已物理按住的修饰键不重复注入（保留 Ctrl+C 修复：
                # 目标应用能拿到物理修饰键状态，组合键输入不被破坏）。
                continue
            vk = self._output_key_to_vk(key)
            if vk is None:
                unknown.append(key)
                continue
            if vk in press_vks:
                continue
            press_vks.append(vk)
        if not press_vks:
            return
        if unknown:
            self.last_error = f"Unknown output key: {'+'.join(unknown)}"
        self._log_injection(output)
        self._inject_keys(press_vks)

    def _inject_keys(self, vks):
        """按下 -> 保持 _output_delay_ms -> 反序抬起，各用一次 SendInput。

        绝不释放或按下用户物理按住的修饰键：旧版"先抬起、输出后恢复"
        会在窗口期让目标应用看到修饰键已松开（组合退化成纯字母键），
        且"恢复按下"是一次从不释放的注入，会污染 GetAsyncKeyState
        产生幻影修饰键（纯字母键误触组合热键）。
        """
        n = len(vks)
        inputs = (_INPUT * n)()
        for i, vk in enumerate(vks):
            inputs[i].type = INPUT_KEYBOARD
            inputs[i].u.ki.wVk = vk
            inputs[i].u.ki.dwExtraInfo = BINDX_INJECTION_TAG
        sent = self._send_input(n, inputs, ctypes.sizeof(_INPUT))
        if sent != n:
            self.last_error = f"SendInput press failed: {sent}/{n}"
        time.sleep(self._output_delay_ms / 1000.0)
        inputs = (_INPUT * n)()
        for i, vk in enumerate(reversed(vks)):
            inputs[i].type = INPUT_KEYBOARD
            inputs[i].u.ki.wVk = vk
            inputs[i].u.ki.dwFlags = KEYEVENTF_KEYUP
            inputs[i].u.ki.dwExtraInfo = BINDX_INJECTION_TAG
        self._send_input(n, inputs, ctypes.sizeof(_INPUT))

    def _log_injection(self, keys):
        # 记录一次注入事件，供检查器在短窗口内匹配
        output = self._normalize_output_keys(keys)
        if not output:
            return
        names = set()
        vks = set()
        for name in output:
            n = str(name).strip().lower()
            if n:
                names.add(n)
            vk = self._key_name_to_vk(n)
            if vk is not None:
                vks.add(vk)
        if not names and not vks:
            return
        with self._injection_log_lock:
            self._injection_log.append((time.monotonic(), vks, names))

    def match_injection(self, vk=None, button=None, now=None):
        # 判断给定 vk / 鼠标按钮是否来自近期（250ms 内）的 BindX 注入
        if now is None:
            now = time.monotonic()
        btn = str(button).strip().lower() if button is not None else None
        with self._injection_log_lock:
            log = list(self._injection_log)
        for ts, vks, names in reversed(log):
            if ts < now - 0.25:
                break
            if vk is not None and vk in vks:
                return True
            if btn and btn in names:
                return True
        return False
