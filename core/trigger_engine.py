# -*- coding: utf-8 -*-

import ctypes
import os
import queue
import threading
import time
import traceback
from collections import deque
from ctypes import wintypes

from . import config_proxy

_hk = config_proxy.hk_module()

BINDX_EXTRA_INFO = 0x42494E58
GCS_COMPSTR = 0x0008


def _tb_text():
    # 取当前正在处理的异常的 traceback 文本。
    # 钩子回调的异常处理路径依赖它；旧版缺失时会在 except 块里
    # 再抛 NameError，异常直接传进原生 hook 派发（行为未定义）。
    return traceback.format_exc()


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", wintypes.DWORD),
        ("wParamL", wintypes.WORD),
        ("wParamH", wintypes.WORD),
    ]


class INPUTUNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", wintypes.DWORD),
        ("union", INPUTUNION),
    ]


class GUITHREADINFO(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("hwndActive", wintypes.HWND),
        ("hwndFocus", wintypes.HWND),
        ("hwndCapture", wintypes.HWND),
        ("hwndMenuOwner", wintypes.HWND),
        ("hwndMoveSize", wintypes.HWND),
        ("hwndCaret", wintypes.HWND),
        ("rcCaret", wintypes.RECT),
    ]


class _RunState:
    """Per-run 输出队列。

    僵尸线程（卡在阻塞调用里迟迟不结束的旧 _run）与新 _run
    各自持有独立的队列/代际号，僵尸线程退出时只清理自己的
    局部状态，永远不会覆盖、清空或消费新 run 的队列与标志。
    """

    __slots__ = ("gen", "queue", "queue_lock")

    def __init__(self, gen):
        self.gen = gen
        self.queue = []
        self.queue_lock = threading.Lock()


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
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1
    EVENT_LOG_SIZE = 500
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
    # 可被 GetAsyncKeyState 单独查询的具体修饰键 VK
    # （不含通用 0x10/0x11/0x12）。用于快速"同进程"物理按键状态
    # 对账，绝不跨进程。
    SPECIFIC_MODIFIER_VKS = (
        VK_LSHIFT, VK_RSHIFT, VK_LCONTROL, VK_RCONTROL,
        VK_LMENU, VK_RMENU, VK_LWIN, VK_RWIN,
    )

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

    OUTPUT_MODIFIER_VKS = {
        "ctrl": VK_CONTROL,
        "control": VK_CONTROL,
        "left ctrl": VK_LCONTROL,
        "right ctrl": VK_RCONTROL,
        "shift": VK_SHIFT,
        "left shift": VK_LSHIFT,
        "right shift": VK_RSHIFT,
        "alt": VK_MENU,
        "altgr": VK_RMENU,
        "left alt": VK_LMENU,
        "right alt": VK_RMENU,
        "win": VK_LWIN,
        "windows": VK_LWIN,
        "left windows": VK_LWIN,
        "right windows": VK_RWIN,
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
        self._imm32 = None

        # A3: 输出延迟与是否恢复物理按住的修饰键
        self._output_delay_ms = 20
        self._restore_held_modifiers = True
        # A1: 线程停止时的按键状态快照，下次启动恢复
        self._snap_pressed = None
        self._snap_suppressed = None
        # 钩子回调延迟统计
        self._slow_hook_count = 0
        # B5: 注入事件日志（供按键检查器标注 BindX 注入）
        self._injection_log = deque(maxlen=128)
        self._injection_log_lock = threading.Lock()
        # 键盘事件诊断日志：只保留最近事件，用于定位吞键/增键
        self._event_log = deque(maxlen=self.EVENT_LOG_SIZE)
        # per-run 状态：代际号 + 私有输出队列（僵尸线程无法覆盖新 run）
        self._gen = 0
        self._run_state = None
        self._keyboard_hook = None
        self._mouse_hook = None
        self._output_worker = None
        # IME 状态：钩子回调只读该标志（回调内不做跨进程调用），
        # 由 _ime_monitor 后台线程约 100ms 刷新一次
        self._ime_composing = False
        self._ime_monitor = None
        self._ime_monitor_gen = 0
        self._ime_monitor_heartbeat = 0.0
        # 诊断日志：hook 线程只入队，专用 writer 线程做文件 I/O，
        # 磁盘阻塞不会拖住低级钩子（阻塞超时会令系统禁用钩子）
        self._diag_queue = queue.Queue()
        self._diag_writer = None
        # 修复：旧版只在首次 update_mouse_config 时才建索引，
        # 在此之前按键/鼠标事件会在钩子内抛 AttributeError 并被静默吞掉
        self._rebuild_mouse_index()

    def set_enabled(self, keyboard_enabled=None, mouse_enabled=None):
        if keyboard_enabled is not None:
            with self._lock:
                self.keyboard_enabled = bool(keyboard_enabled)
        if mouse_enabled is not None:
            with self._lock:
                self.mouse_enabled = bool(mouse_enabled)
        with self._lock:
            self._sync_hotkey_status()
            desired = self.keyboard_enabled or self.mouse_enabled
        # 启/停在锁外进行：_stop_thread 需要 join 钩子线程，而钩子回调
        # 又会获取 self._lock，持锁等待会等死自己（也会触发低级钩子超时）。
        if desired:
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

    def export_event_log(self):
        with self._lock:
            entries = list(self._event_log)
        exported = []
        for entry in entries:
            item = dict(entry)
            item["time"] = time.strftime(
                "%Y-%m-%d %H:%M:%S", time.localtime(item.pop("wall_time"))
            )
            exported.append(item)
        return exported

    def reinstall_hooks(self):
        self._stop_thread()
        with self._lock:
            desired = self.keyboard_enabled or self.mouse_enabled
        if desired:
            self._ensure_running()

    def shutdown(self):
        self._watchdog_stop.set()
        self._stop_thread()
        thread = self._watchdog_thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        # 停止诊断 writer：放入哨兵，等待其把剩余日志落盘后退出
        try:
            self._diag_queue.put(None)
        except Exception:
            pass
        writer = self._diag_writer
        if writer and writer.is_alive() and writer is not threading.current_thread():
            writer.join(timeout=1.0)
        self._diag_writer = None

    def _ensure_running(self):
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._start_diag_writer()
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            watchdog_needed = (
                not self._watchdog_thread or not self._watchdog_thread.is_alive()
            )
        if watchdog_needed:
            self._watchdog_stop.clear()
            self._watchdog_thread = threading.Thread(
                target=self._watchdog_loop, daemon=True
            )
            self._watchdog_thread.start()

    def _stop_thread(self):
        # 使当前 run 与 IME 监控失效（代际号让旧线程自行退出），
        # 之后僵尸 _run 再也无法修改任何共享状态。
        self._gen += 1
        self._ime_monitor_gen += 1
        self._ime_composing = False
        self._stop_event.set()
        thread = None
        with self._lock:
            thread = self._thread
            self._thread = None
            self.running = False
            self._run_state = None
            self._output_worker = None
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
        # join 必须在锁外：钩子回调也会获取 self._lock，持锁等待
        # 会让旧线程超时而成为僵尸（同时触发低级钩子超时）。
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
            if thread.is_alive():
                # 僵尸：卡在阻塞调用里（旧版钩子回调内有跨进程 IME
                # 查询，可卡数小时）。立即摘掉它的钩子，让旧线程
                # 不再接收事件；僵尸最终醒来时只做局部清理
                # （代际号保护），不会碰新 run。
                self._diag_log("hook thread stuck; forced unhook (zombie will self-clean)")
                self._force_unhook()

    def _force_unhook(self):
        with self._lock:
            user32 = self._user32
            keyboard_hook = self._keyboard_hook
            mouse_hook = self._mouse_hook
            self._keyboard_hook = None
            self._mouse_hook = None
        if not keyboard_hook and not mouse_hook:
            return
        if user32 is None:
            user32 = ctypes.WinDLL("user32", use_last_error=True)
            user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
            user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        for handle in (keyboard_hook, mouse_hook):
            if handle:
                try:
                    user32.UnhookWindowsHookEx(handle)
                except Exception:
                    pass

    def _watchdog_loop(self):
        while not self._watchdog_stop.wait(2.0):
            try:
                restart_needed = False
                with self._lock:
                    desired = self.keyboard_enabled or self.mouse_enabled
                    if not desired:
                        continue
                    stale = bool(
                        self.running and self.heartbeat
                        and time.monotonic() - self.heartbeat > 5.0
                    )
                    dead = not self._thread or not self._thread.is_alive()
                    if dead or stale:
                        restart_needed = True
                        self.last_error = "Hook watchdog restarted trigger engine"
                        age = (time.monotonic() - self.heartbeat) if self.heartbeat else -1.0
                        self._diag_log(
                            f"watchdog restarted hook thread: dead={dead}, stale={stale}, "
                            f"running={self.running}, heartbeat_age={age:.2f}s"
                        )
                # _stop_thread 可能 join 至多 1 秒，不能在持锁时做
                if restart_needed:
                    self._stop_thread()
                    self._ensure_running()
            except Exception:
                self._diag_log("watchdog exception:\n" + _tb_text())

    def _sync_hotkey_status(self):
        active = bool(self.keyboard_enabled and self.running)
        self.hotkey_manager.external_trigger_active = active
        for entry in self.hotkey_manager.entries:
            entry["registered"] = bool(active and entry.get("enabled", True))
            if entry["registered"]:
                entry["last_error"] = None

    def _run(self):
        # 本次 run 的代际号与私有停止标志：被 _stop_thread 判为僵尸的
        # run 不再与新 run 共享 _stop_event / _run_state。
        gen = self._gen
        run_stop = threading.Event()
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        imm32 = ctypes.WinDLL("imm32", use_last_error=True)
        self._user32 = user32
        self._imm32 = imm32

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
        user32.SendInput.argtypes = [
            wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int
        ]
        user32.SendInput.restype = wintypes.UINT
        user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
        user32.MapVirtualKeyW.restype = wintypes.UINT
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        user32.GetWindowThreadProcessId.argtypes = [
            wintypes.HWND, ctypes.POINTER(wintypes.DWORD)
        ]
        user32.GetWindowThreadProcessId.restype = wintypes.DWORD
        user32.GetGUIThreadInfo.argtypes = [
            wintypes.DWORD, ctypes.POINTER(GUITHREADINFO)
        ]
        user32.GetGUIThreadInfo.restype = wintypes.BOOL
        imm32.ImmGetContext.argtypes = [wintypes.HWND]
        imm32.ImmGetContext.restype = ctypes.c_void_p
        imm32.ImmReleaseContext.argtypes = [wintypes.HWND, ctypes.c_void_p]
        imm32.ImmReleaseContext.restype = wintypes.BOOL
        imm32.ImmGetCompositionStringW.argtypes = [
            ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD
        ]
        imm32.ImmGetCompositionStringW.restype = ctypes.c_long
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE

        keyboard_proc = HOOKPROC(self._keyboard_proc)
        mouse_proc = HOOKPROC(self._mouse_proc)
        hinst = kernel32.GetModuleHandleW(None)
        keyboard_hook = user32.SetWindowsHookExW(self.WH_KEYBOARD_LL, keyboard_proc, hinst, 0)
        mouse_hook = user32.SetWindowsHookExW(self.WH_MOUSE_LL, mouse_proc, hinst, 0)

        if not keyboard_hook or not mouse_hook:
            self.last_error = f"SetWindowsHookExW failed: {ctypes.get_last_error()}"
            self._finish_run(user32, keyboard_hook, mouse_hook, run_stop, gen)
            self._sync_hotkey_status()
            return

        with self._lock:
            self._keyboard_hook = keyboard_hook
            self._mouse_hook = mouse_hook
            self._run_state = _RunState(gen)
        self.running = True
        self.last_error = None
        self._slow_hook_count = 0
        # 种子物理修饰键状态：只查具体 VK（通用 VK_CONTROL/SHIFT/MENU
        # 与具体 VK 同组、状态相同；若把通用 VK 也存进来，会留下
        # 永远清不掉的幽灵状态）
        self._physical_modifiers = {
            vk for vk in self.SPECIFIC_MODIFIER_VKS
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
        except Exception:
            self._diag_log("hook startup exception:\n" + _tb_text())
            self.last_error = "Hook startup crashed (see data/bindx_hook_error.log)"
            self._finish_run(user32, keyboard_hook, mouse_hook, run_stop, gen)
            return
        # A4: 启动输出 worker（本次 run 的私有队列）
        with self._lock:
            state = self._run_state
        worker = None
        if state is not None:
            worker = threading.Thread(
                target=self._output_worker_loop, args=(run_stop, state), daemon=True
            )
            with self._lock:
                self._output_worker = worker
            worker.start()
        # IME 状态监控：跨进程查询绝不能出现在钩子回调里
        # （回调超时会被系统禁用钩子——那是滚轮失效/按键错乱的根源），
        # 由后台线程约 100ms 刷新一次 _ime_composing。
        self._ime_composing = False
        self._ime_monitor_heartbeat = time.monotonic()
        self._ime_monitor = threading.Thread(target=self._ime_monitor_loop, daemon=True)
        self._ime_monitor.start()
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
            # gen 自检：僵尸 run 被 _stop_thread 失效（代际号+1）后，
            # 从阻塞调用里醒来就立即退出，不再触碰新 run 的状态。
            while gen == self._gen and not run_stop.is_set() and not self._stop_event.is_set():
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
                # IME 监控自愈：心跳超过 3 秒未更新说明它很可能卡在
                # 跨进程调用里，作废旧代际并起新线程（旧线程醒来后
                # 自行退出）。
                if (
                    self._ime_monitor_heartbeat
                    and time.monotonic() - self._ime_monitor_heartbeat > 3.0
                ):
                    self._ime_monitor_gen += 1
                    self._ime_monitor = threading.Thread(
                        target=self._ime_monitor_loop, daemon=True
                    )
                    self._ime_monitor.start()
        finally:
            self._finish_run(user32, keyboard_hook, mouse_hook, run_stop, gen)
            if worker is not None and worker is not threading.current_thread():
                worker.join(timeout=1.0)
            if gen == self._gen:
                self._sync_hotkey_status()

    def _finish_run(self, user32, keyboard_hook, mouse_hook, run_stop, gen):
        """卸载钩子并（仅当本 run 仍是当前）清理共享状态。

        僵尸 run（被 _stop_thread 判失效）只做局部卸载，绝不碰
        新 run 的队列、标志与线程。
        """
        run_stop.set()
        for handle in (keyboard_hook, mouse_hook):
            if handle:
                try:
                    user32.UnhookWindowsHookEx(handle)
                except Exception:
                    pass
        if gen == self._gen:
            with self._lock:
                self._keyboard_hook = None
                self._mouse_hook = None
                self.running = False
                self._run_state = None
                self._output_worker = None
            self._ime_monitor_gen += 1

    def _output_worker_loop(self, run_stop, state):
        # 只处理所属 run 的输出队列；run 结束（run_stop）即自行退出，
        # 僵尸 run 的 worker 不会触碰新 run 的队列。
        if state is None:
            return
        while not run_stop.is_set() and not self._stop_event.is_set():
            keys = None
            with state.queue_lock:
                if state.queue:
                    keys = state.queue.pop(0)
            if keys is None:
                if run_stop.wait(0.005):
                    break
                continue
            try:
                self._do_output(keys, run_stop)
            except Exception:
                self._diag_log("output worker exception:\n" + _tb_text())

    def _note_hook_latency(self, started):
        if time.monotonic() - started > 0.1:
            self._slow_hook_count += 1
            if self._slow_hook_count == 1:
                self.last_error = "Hook callback is slow (over 100ms); input may feel laggy"

    def _diag_log(self, message):
        # 诊断日志：pythonw 没有控制台，hook 线程/回调/消息泵的异常绝不能静默，
        # 统一记录到 data/bindx_hook_error.log。
        # hook 线程只入队、writer 线程落盘：文件 I/O 绝不能阻塞
        # 低级钩子回调（阻塞超时会令系统禁用钩子）。
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            if self._diag_queue.qsize() >= 200:
                return
            self._diag_queue.put(f"[{stamp}] {message}")
            self._start_diag_writer()
        except Exception:
            pass

    def _start_diag_writer(self):
        writer = self._diag_writer
        if writer is None or not writer.is_alive():
            self._diag_writer = threading.Thread(
                target=self._diag_writer_loop, daemon=True
            )
            self._diag_writer.start()

    def _diag_writer_loop(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "data", "bindx_hook_error.log",
        )
        while True:
            try:
                line = self._diag_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                break
            try:
                with open(path, "a", encoding="utf-8") as f:
                    f.write(line + "\n")
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

    def _append_event_log_locked(self, vk, msg, flags, extra_info, source, action, modifiers, detail=""):
        self._event_log.append({
            "monotonic": time.monotonic(),
            "wall_time": time.time(),
            "vk": vk,
            "msg": int(msg),
            "flags": int(flags),
            "extra_info": int(extra_info),
            "source": source,
            "action": action,
            "modifiers": sorted(modifiers),
            "detail": detail,
        })

    def _keyboard_proc_impl(self, n_code, w_param, l_param):
        if n_code < 0:
            return self._call_next_keyboard(n_code, w_param, l_param)

        info = ctypes.cast(l_param, ctypes.POINTER(self.KBDLLHOOKSTRUCT)).contents
        vk = int(info.vkCode)
        is_down = w_param in (self.WM_KEYDOWN, self.WM_SYSKEYDOWN)
        is_up = w_param in (self.WM_KEYUP, self.WM_SYSKEYUP)
        flags = int(info.flags)
        extra_info = int(info.dwExtraInfo)

        if flags & self.LLKHF_INJECTED:
            source = "bindx" if extra_info == BINDX_EXTRA_INFO else "injected"
            with self._lock:
                self._append_event_log_locked(
                    vk, w_param, flags, extra_info, source,
                    "injected_pass", self._physical_modifiers,
                )
            return self._call_next_keyboard(n_code, w_param, l_param)

        suppress = False
        action = "pass"
        detail = ""
        with self._lock:
            modifiers = frozenset(self._physical_modifiers)
            if is_down:
                if vk in self.MODIFIER_KEYS:
                    self._physical_modifiers.add(vk)
                    # 与系统实际物理状态对账（同进程快调用），
                    # 漏掉的 key-up / 幽灵状态从此无法累积
                    self._sync_modifier_state(exclude_vk=vk)
                    modifiers = frozenset(self._physical_modifiers)
                was_pressed = vk in self._pressed_vks
                self._pressed_vks.add(vk)
                if was_pressed:
                    suppress = vk in self._suppressed_keyups
                    action = "repeat_suppressed" if suppress else "repeat_pass"
                elif self.keyboard_enabled:
                    if self._match_hotkey(vk):
                        self._suppressed_keyups.add(vk)
                        suppress = True
                        action = "hotkey_suppressed"
                        detail = self.last_event
                    elif self._match_key_mapping(vk):
                        self._suppressed_keyups.add(vk)
                        suppress = True
                        action = "mapping_suppressed"
                        detail = self.last_event
            elif is_up:
                if vk in self.MODIFIER_KEYS:
                    self._physical_modifiers.discard(vk)
                    # 旧版在这里调用不存在的 _sync_modifier_state，
                    # 每个修饰键 key-up 都让回调抛异常（按键错乱/
                    # 修饰键卡死的直接根源之一）
                    self._sync_modifier_state(exclude_vk=vk)
                    modifiers = frozenset(self._physical_modifiers)
                self._pressed_vks.discard(vk)
                self._release_active_triggers(vk)
                if vk in self.MODIFIER_KEYS:
                    self._clear_chord_state()
                if vk in self._suppressed_keyups:
                    self._suppressed_keyups.discard(vk)
                    suppress = True
                    action = "keyup_suppressed"
                else:
                    action = "keyup_pass"
            else:
                action = "unknown_pass"

            self._append_event_log_locked(
                vk, w_param, flags, extra_info, "physical", action,
                modifiers, detail,
            )

        if suppress:
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
        """按系统物理按键状态对账 _physical_modifiers。

        只用 GetAsyncKeyState（同进程快查询，无跨进程调用），在每次
        物理修饰键 down/up 以及输出注入前调用。
        exclude_vk 是当前正在处理事件的具体 VK：系统的异步状态可能
        比物理事件晚几毫秒，该键既不剔除也不参与对账，避免把
        "刚按下/刚松开"误判为幽灵或漏按。
        """
        user32 = self._user32
        if user32 is None:
            return
        preserved = (
            {exclude_vk}
            if (exclude_vk is not None and exclude_vk in self._physical_modifiers)
            else set()
        )
        live = set()
        for vk in self.SPECIFIC_MODIFIER_VKS:
            if vk == exclude_vk:
                continue
            try:
                if int(user32.GetAsyncKeyState(vk)) & 0x8000:
                    live.add(vk)
            except Exception:
                return
        self._physical_modifiers.difference_update(self.SPECIFIC_MODIFIER_VKS)
        self._physical_modifiers.update(preserved)
        self._physical_modifiers.update(live)
        self._pressed_vks.update(self._physical_modifiers)

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

        if w_param in (self.WM_MOUSEWHEEL, self.WM_MOUSEHWHEEL):
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
                self._enqueue_output(mapping.get("output", []))
                return 1
            if w_param == up_msg and btn in self._suppressed_mouse_buttons:
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

        return self._call_next_mouse(n_code, w_param, l_param)

    def _trigger_mouse(self, btn, mapping):
        self._suppressed_mouse_buttons.add(btn)
        self.last_event = f"Mouse {btn} -> {'+'.join(mapping.get('output', []))}"
        self._enqueue_output(mapping.get("output", []))

    def _enqueue_output(self, output):
        # 把输出组合放入当前 run 的私有队列（worker 串行注入）；
        # run 未激活（钩子未装/已停用）时直接丢弃。
        state = self._run_state
        if state is None:
            return
        with state.queue_lock:
            state.queue.append(list(output))

    def _call_next_keyboard(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _call_next_mouse(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(None, n_code, w_param, l_param)

    def _current_modifiers(self):
        with self._lock:
            # Physical event tracking is authoritative for BindX-injected state,
            # but hotkeys still require an async-state confirmation. This removes
            # missed-keyup residue before a normal letter can trigger Ctrl+Alt apps.
            eff = set(self._physical_modifiers)
            user32 = self._user32
            if user32 is not None:
                for group in self.MODIFIER_GROUPS:
                    physical = eff & group
                    if not physical:
                        continue
                    confirmed = False
                    for vk in group:
                        try:
                            if int(user32.GetAsyncKeyState(vk)) & 0x8000:
                                confirmed = True
                                break
                        except Exception:
                            confirmed = True
                            break
                    if not confirmed:
                        self._physical_modifiers.difference_update(group)
                        eff.difference_update(group)
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

    def _ime_monitor_loop(self):
        # IME 组合状态查询涉及跨进程调用（GetForegroundWindow /
        # GetGUIThreadInfo / ImmGetCompositionStringW），前台程序不响应时
        # 可能阻塞很久。因此放在后台线程；钩子回调只读
        # self._ime_composing。代际号让旧 run 的监控线程自行退出。
        gen = self._ime_monitor_gen
        while not self._stop_event.is_set():
            if self._ime_monitor_gen != gen:
                return
            started = time.monotonic()
            try:
                composing = self._ime_composition_active()
                if time.monotonic() - started > 1.0:
                    # 单次查询超过 1 秒，结果已过时，视为"未组合"
                    composing = False
            except Exception:
                composing = False
            if self._ime_monitor_gen != gen:
                return
            self._ime_composing = composing
            self._ime_monitor_heartbeat = time.monotonic()
            self._stop_event.wait(0.1)

    def _ime_composition_active(self):
        user32 = self._user32
        imm32 = self._imm32
        if user32 is None or imm32 is None:
            return False

        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return False
            thread_id = int(user32.GetWindowThreadProcessId(hwnd, None))
            if not thread_id:
                return False
            info = GUITHREADINFO()
            info.cbSize = ctypes.sizeof(GUITHREADINFO)
            if not user32.GetGUIThreadInfo(thread_id, ctypes.byref(info)):
                return False
            focus = info.hwndFocus or hwnd
            himc = imm32.ImmGetContext(focus)
            if not himc:
                return False
            try:
                size = int(
                    imm32.ImmGetCompositionStringW(himc, GCS_COMPSTR, None, 0)
                )
                return size > 0
            finally:
                imm32.ImmReleaseContext(focus, himc)
        except Exception:
            return False

    def _match_hotkey(self, vk):
        if vk in self.MODIFIER_KEYS:
            return False
        # 只读后台监控线程刷新的标志；绝不能在这里做跨进程查询
        # （回调超时 => 系统禁用钩子 => 滚轮失效/按键错乱）
        if self._ime_composing:
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
        if self._ime_composing:
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
            self._enqueue_output(mapping.get("output", []))
            return True
        return False

    def _held_modifier_names(self):
        with self._lock:
            held = frozenset(self._physical_modifiers)
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

    def _output_key_vk(self, name):
        return self.OUTPUT_MODIFIER_VKS.get(name) or self._key_name_to_vk(name)

    def _inject_key(self, name, down):
        vk = self._output_key_vk(name)
        if vk is None:
            raise ValueError(f"Unsupported output key: {name}")
        user32 = self._user32
        if user32 is None:
            raise RuntimeError("Trigger engine is not running")

        scan = int(user32.MapVirtualKeyW(vk, 0))
        flags = self.KEYEVENTF_KEYUP if down is False else 0
        item = INPUT()
        item.type = self.INPUT_KEYBOARD
        item.union.ki = KEYBDINPUT(vk, scan, flags, 0, BINDX_EXTRA_INFO)
        array = (INPUT * 1)(item)
        sent = int(user32.SendInput(1, array, ctypes.sizeof(INPUT)))
        if sent != 1:
            raise RuntimeError(f"SendInput failed for {name}")
        return True

    def _do_output(self, keys, stop=None):
        output = self._normalize_output_keys(keys)
        if not output:
            return
        stop = stop or self._stop_event
        if stop.wait(self._output_delay_ms / 1000.0):
            return
        if stop.is_set() or self._stop_event.is_set():
            return
        # 注入序列与物理事件处理共用一把锁：读取“用户仍按住”和发送
        # SendInput 之间不可能插入物理 key-up。
        with self._lock:
            # 注入前与系统实际物理按键状态对账（同进程快调用）：
            # 用户物理按住的修饰键原样保留 —— 绝不抬起、也绝不恢复
            # 用户的物理修饰键。旧实现“先抬起再恢复”正是幻影
            # Ctrl/Esc/Alt 闪烁、打断输入法、以及 Ctrl 卡死导致
            # 滚轮变网页缩放的根源。
            self._sync_modifier_state()
            held_names = set(self._held_modifier_names())
            held_mod_groups = {
                group for group in (
                    self._modifier_group(name) for name in held_names
                ) if group
            }
            self._log_injection(output)
            pressed = []
            try:
                for key in output:
                    group = self._modifier_group(key)
                    if group and group in held_mod_groups:
                        continue
                    if self._inject_key(key, True):
                        pressed.append(key)
            finally:
                for key in reversed(pressed):
                    self._inject_key(key, False)

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
            vk = self._output_key_vk(n)
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
