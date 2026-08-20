# -*- coding: utf-8 -*-
"""BindX UI: 按键检查器窗口。"""

import ctypes
import queue
import threading
import time
import tkinter as tk
from ctypes import wintypes

import customtkinter as ctk

from .theme import scaled, ui_font

class InputInspectorWindow(ctk.CTkToplevel):
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

    LLKHF_EXTENDED = 0x01
    LLKHF_INJECTED = 0x10
    PM_REMOVE = 0x0001
    MAX_HISTORY = 200

    KEY_DOWN_MESSAGES = {WM_KEYDOWN, WM_SYSKEYDOWN}
    KEY_UP_MESSAGES = {WM_KEYUP, WM_SYSKEYUP}
    KEY_MESSAGES = KEY_DOWN_MESSAGES | KEY_UP_MESSAGES
    MOUSE_DOWN_MESSAGES = {
        WM_LBUTTONDOWN: ("left", "左键"),
        WM_RBUTTONDOWN: ("right", "右键"),
        WM_MBUTTONDOWN: ("middle", "中键"),
        WM_XBUTTONDOWN: ("x", "侧键"),
    }
    MOUSE_UP_MESSAGES = {
        WM_LBUTTONUP: ("left", "左键"),
        WM_RBUTTONUP: ("right", "右键"),
        WM_MBUTTONUP: ("middle", "中键"),
        WM_XBUTTONUP: ("x", "侧键"),
    }
    MOUSE_BUTTON_MESSAGES = set(MOUSE_DOWN_MESSAGES) | set(MOUSE_UP_MESSAGES)

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

    def __init__(self, parent, controller=None):
        super().__init__(parent)
        self.controller = controller
        root = parent.winfo_toplevel()
        self.ui_scale = getattr(root, "ui_scale", 1.0)
        self._events = queue.Queue()
        self._stop_event = threading.Event()
        self._thread = None
        self._user32 = None
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_proc_ref = None
        self._mouse_proc_ref = None
        self._poll_after_id = None
        self._closed = False
        self._hook_generation = 0
        self._keyboard_down = {}
        self._mouse_down = {}
        self._keyboard_history = []
        self._mouse_history = []
        self._ignore_history_until = 0.0

        self.title("按键检查")
        self.geometry(f"{scaled(self, 760)}x{scaled(self, 460)}")
        self.minsize(scaled(self, 640), scaled(self, 380))
        self.configure(fg_color=("#f4f4f5", "#18181b"))
        self.transient(root)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._create_ui()
        self._start_hooks()
        self._poll_events()

    def _create_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=scaled(self, 18), pady=(scaled(self, 16), scaled(self, 10)))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(header, text="按键检查", font=ui_font(self, 20, "bold")).grid(row=0, column=0, sticky="w")
        self.start_button = ctk.CTkButton(header, text="启动检查", command=self._start_inspection, width=scaled(self, 92))
        self.start_button.grid(row=0, column=1, sticky="e", padx=(0, scaled(self, 8)))
        self.stop_button = ctk.CTkButton(header, text="停止检查", command=self._stop_inspection, width=scaled(self, 92), fg_color="#52525b", hover_color="#3f3f46")
        self.stop_button.grid(row=0, column=2, sticky="e", padx=(0, scaled(self, 8)))
        ctk.CTkButton(header, text="清空记录", command=self._clear_records, width=scaled(self, 92), fg_color="#52525b", hover_color="#3f3f46").grid(row=0, column=3, sticky="e", padx=(0, scaled(self, 8)))
        ctk.CTkButton(header, text="关闭", command=self._on_close, width=scaled(self, 72), fg_color="#52525b", hover_color="#3f3f46").grid(row=0, column=4, sticky="e")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.grid(row=1, column=0, sticky="nsew", padx=scaled(self, 18), pady=(0, scaled(self, 10)))
        content.grid_columnconfigure(0, weight=1)
        content.grid_columnconfigure(1, weight=1)
        content.grid_rowconfigure(0, weight=1)

        keyboard_panel = ctk.CTkFrame(content, corner_radius=10)
        keyboard_panel.grid(row=0, column=0, sticky="nsew", padx=(0, scaled(self, 8)))
        keyboard_panel.grid_columnconfigure(0, weight=1)
        keyboard_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(keyboard_panel, text="键盘按键记录", font=ui_font(self, 15, "bold")).grid(row=0, column=0, sticky="w", padx=scaled(self, 14), pady=(scaled(self, 12), scaled(self, 8)))
        self.keyboard_box = ctk.CTkTextbox(keyboard_panel, wrap="none", font=ui_font(self, 13), corner_radius=8)
        self.keyboard_box.grid(row=1, column=0, sticky="nsew", padx=scaled(self, 12), pady=(0, scaled(self, 12)))

        mouse_panel = ctk.CTkFrame(content, corner_radius=10)
        mouse_panel.grid(row=0, column=1, sticky="nsew", padx=(scaled(self, 8), 0))
        mouse_panel.grid_columnconfigure(0, weight=1)
        mouse_panel.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(mouse_panel, text="鼠标按键记录", font=ui_font(self, 15, "bold")).grid(row=0, column=0, sticky="w", padx=scaled(self, 14), pady=(scaled(self, 12), scaled(self, 8)))
        self.mouse_box = ctk.CTkTextbox(mouse_panel, wrap="none", font=ui_font(self, 13), corner_radius=8)
        self.mouse_box.grid(row=1, column=0, sticky="nsew", padx=scaled(self, 12), pady=(0, scaled(self, 12)))

        self.status_label = ctk.CTkLabel(self, text="正在启动检查", anchor="w", text_color="#71717a", font=ui_font(self, 13))
        self.status_label.grid(row=2, column=0, sticky="ew", padx=scaled(self, 20), pady=(0, scaled(self, 14)))

        self._set_text(self.keyboard_box, "无")
        self._set_text(self.mouse_box, "无")

    def _start_hooks(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._keyboard_down.clear()
        self._mouse_down.clear()
        self._update_control_state(True)
        self.status_label.configure(text="正在启动检查")
        self._hook_generation += 1
        generation = self._hook_generation
        self._thread = threading.Thread(target=self._run_hook_loop, args=(generation,), daemon=True)
        self._thread.start()

    def _start_inspection(self):
        self._start_hooks()

    def _stop_inspection(self):
        self._stop_hooks("检查已停止，记录已保留")

    def _stop_hooks(self, status_text=None):
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._keyboard_down.clear()
        self._mouse_down.clear()
        self._update_control_state(False)
        self._render_pressed()
        if status_text and not self._closed:
            self.status_label.configure(text=status_text)

    def _update_control_state(self, running):
        if not hasattr(self, "start_button"):
            return
        self.start_button.configure(state="disabled" if running else "normal")
        self.stop_button.configure(state="normal" if running else "disabled")

    def _run_hook_loop(self, generation):
        try:
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
            user32.GetKeyNameTextW.argtypes = [wintypes.LONG, wintypes.LPWSTR, ctypes.c_int]
            user32.GetKeyNameTextW.restype = ctypes.c_int
            user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
            user32.MapVirtualKeyW.restype = wintypes.UINT
            kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
            kernel32.GetModuleHandleW.restype = wintypes.HMODULE

            self._keyboard_proc_ref = HOOKPROC(self._keyboard_proc)
            self._mouse_proc_ref = HOOKPROC(self._mouse_proc)
            hinst = kernel32.GetModuleHandleW(None)
            self._keyboard_hook = user32.SetWindowsHookExW(self.WH_KEYBOARD_LL, self._keyboard_proc_ref, hinst, 0)
            self._mouse_hook = user32.SetWindowsHookExW(self.WH_MOUSE_LL, self._mouse_proc_ref, hinst, 0)
            if not self._keyboard_hook or not self._mouse_hook:
                self._events.put(("status", f"检查启动失败：SetWindowsHookExW={ctypes.get_last_error()}"))
                return

            self._events.put(("status", "按下键盘或鼠标按键后会保留记录"))
            msg = wintypes.MSG()
            while not self._stop_event.is_set():
                while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, self.PM_REMOVE):
                    user32.TranslateMessage(ctypes.byref(msg))
                    user32.DispatchMessageW(ctypes.byref(msg))
                time.sleep(0.01)
        except Exception as exc:
            self._events.put(("status", f"检查异常：{exc}"))
        finally:
            if self._user32 is not None:
                if self._keyboard_hook:
                    self._user32.UnhookWindowsHookEx(self._keyboard_hook)
                if self._mouse_hook:
                    self._user32.UnhookWindowsHookEx(self._mouse_hook)
            self._keyboard_hook = None
            self._mouse_hook = None
            self._keyboard_proc_ref = None
            self._mouse_proc_ref = None
            self._events.put(("stopped", generation))

    def _keyboard_proc(self, n_code, w_param, l_param):
        try:
            if n_code >= 0 and w_param in self.KEY_MESSAGES:
                info = ctypes.cast(l_param, ctypes.POINTER(self.KBDLLHOOKSTRUCT)).contents
                event = "key_down" if w_param in self.KEY_DOWN_MESSAGES else "key_up"
                self._events.put((event, self._keyboard_payload(info, int(w_param))))
        except Exception as exc:
            self._events.put(("status", f"键盘检查异常：{exc}"))
        return self._call_next_keyboard(n_code, w_param, l_param)

    def _mouse_proc(self, n_code, w_param, l_param):
        try:
            msg = int(w_param)
            if n_code >= 0 and msg in self.MOUSE_BUTTON_MESSAGES:
                info = ctypes.cast(l_param, ctypes.POINTER(self.MSLLHOOKSTRUCT)).contents
                event = "mouse_down" if msg in self.MOUSE_DOWN_MESSAGES else "mouse_up"
                self._events.put((event, self._mouse_payload(info, msg)))
        except Exception as exc:
            self._events.put(("status", f"鼠标检查异常：{exc}"))
        return self._call_next_mouse(n_code, w_param, l_param)

    def _keyboard_payload(self, info, msg):
        vk = int(info.vkCode)
        scan = int(info.scanCode)
        flags = int(info.flags)
        extended = bool(flags & self.LLKHF_EXTENDED)
        return {
            "id": f"{vk:02X}:{scan:02X}:{int(extended)}",
            "name": self._key_name(vk, scan, flags),
            "vk": vk,
            "scan": scan,
            "flags": flags,
            "msg": msg,
            "time": time.monotonic(),
            "recorded_at": time.strftime("%H:%M:%S"),
            "injected": bool(flags & self.LLKHF_INJECTED),
        }

    def _mouse_payload(self, info, msg):
        mouse_data = int(info.mouseData)
        flags = int(info.flags)
        x_button = (mouse_data >> 16) & 0xFFFF
        source = self.MOUSE_DOWN_MESSAGES.get(msg) or self.MOUSE_UP_MESSAGES.get(msg)
        button_key, label = source
        if button_key == "x":
            if x_button == 1:
                button_key = "x1"
                label = "X1 侧键"
            elif x_button == 2:
                button_key = "x2"
                label = "X2 侧键"
            elif x_button:
                button_key = f"x{x_button}"
                label = f"X{x_button} 侧键"
            else:
                button_key = "x?"
                label = "未知侧键"
        return {
            "id": button_key,
            "name": f"{button_key}（{label}）",
            "msg": msg,
            "mouse_data": mouse_data,
            "x_button": x_button,
            "flags": flags,
            "x": int(info.pt.x),
            "y": int(info.pt.y),
            "time": time.monotonic(),
            "recorded_at": time.strftime("%H:%M:%S"),
            "injected": bool(flags & self.LLKHF_INJECTED),
        }

    def _key_name(self, vk, scan, flags):
        user32 = self._user32
        if user32 is None:
            return f"VK 0x{vk:02X}"
        scan_code = scan or int(user32.MapVirtualKeyW(vk, 0))
        lparam = scan_code << 16
        if flags & self.LLKHF_EXTENDED:
            lparam |= 1 << 24
        buf = ctypes.create_unicode_buffer(128)
        if user32.GetKeyNameTextW(lparam, buf, len(buf)):
            return buf.value
        return f"VK 0x{vk:02X}"

    def _call_next_keyboard(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(self._keyboard_hook, n_code, w_param, l_param)

    def _call_next_mouse(self, n_code, w_param, l_param):
        if self._user32 is None:
            return 0
        return self._user32.CallNextHookEx(self._mouse_hook, n_code, w_param, l_param)

    def _poll_events(self):
        if self._closed:
            return
        changed = False
        try:
            while True:
                event, payload = self._events.get_nowait()
                if event == "status":
                    self.status_label.configure(text=payload)
                elif event == "stopped":
                    if payload == self._hook_generation:
                        self._update_control_state(False)
                elif event == "key_down":
                    if payload["time"] < self._ignore_history_until:
                        continue
                    payload["label"] = self._injection_label(payload)
                    if payload["id"] not in self._keyboard_down:
                        self._keyboard_history.append(payload)
                        self._trim_history(self._keyboard_history)
                    self._keyboard_down[payload["id"]] = payload
                    changed = True
                elif event == "key_up":
                    self._keyboard_down.pop(payload["id"], None)
                    changed = True
                elif event == "mouse_down":
                    if payload["time"] < self._ignore_history_until:
                        continue
                    payload["label"] = self._injection_label(payload)
                    if payload["id"] not in self._mouse_down:
                        self._mouse_history.append(payload)
                        self._trim_history(self._mouse_history)
                    self._mouse_down[payload["id"]] = payload
                    changed = True
                elif event == "mouse_up":
                    self._mouse_down.pop(payload["id"], None)
                    changed = True
        except queue.Empty:
            pass

        if changed:
            self._render_pressed()
        self._poll_after_id = self.after(30, self._poll_events)

    def _render_pressed(self):
        keyboard_follow = self._textbox_at_bottom(self.keyboard_box)
        mouse_follow = self._textbox_at_bottom(self.mouse_box)
        keyboard_lines = []
        for index, item in enumerate(self._keyboard_history, start=1):
            keyboard_lines.append(
                f"{index}. {item['recorded_at']}  {item['name']}{item.get('label', '')}\n"
                f"  VK=0x{item['vk']:02X} ({item['vk']})  "
                f"SC=0x{item['scan']:02X} ({item['scan']})  "
                f"flags=0x{item['flags']:02X}  msg=0x{item['msg']:04X}"
            )
        mouse_lines = []
        for index, item in enumerate(self._mouse_history, start=1):
            mouse_lines.append(
                f"{index}. {item['recorded_at']}  {item['name']}{item.get('label', '')}\n"
                f"  msg=0x{item['msg']:04X}  mouseData=0x{item['mouse_data']:08X}  "
                f"xButton={item['x_button']}  flags=0x{item['flags']:02X}  pos=({item['x']}, {item['y']})"
            )
        self._set_text(self.keyboard_box, "\n\n".join(keyboard_lines) if keyboard_lines else "无", keyboard_follow)
        self._set_text(self.mouse_box, "\n\n".join(mouse_lines) if mouse_lines else "无", mouse_follow)
        self.status_label.configure(
            text=(
                f"记录：键盘 {len(self._keyboard_history)} 条 / 鼠标 {len(self._mouse_history)} 条；"
                f"当前按下：键盘 {len(self._keyboard_down)} 个 / 鼠标 {len(self._mouse_down)} 个"
            )
        )

    def _injection_label(self, payload):
        # B5: 标注该事件是否由 BindX 注入（LLKHF_INJECTED + 近期注入日志匹配）
        if not payload.get("injected"):
            return ""
        te = self.controller.trigger_engine if self.controller is not None else None
        if te is not None:
            if "vk" in payload:
                if te.match_injection(vk=payload["vk"], now=payload["time"]):
                    return "  [BindX 注入]"
            else:
                if te.match_injection(button=payload["id"], now=payload["time"]):
                    return "  [BindX 注入]"
        return "  [注入]"

    def _trim_history(self, history):
        if len(history) > self.MAX_HISTORY:
            del history[:-self.MAX_HISTORY]

    def _clear_records(self):
        self._ignore_history_until = time.monotonic() + 0.2
        self._keyboard_history.clear()
        self._mouse_history.clear()
        self._render_pressed()

    def _textbox_at_bottom(self, textbox):
        try:
            return textbox.yview()[1] >= 0.98
        except tk.TclError:
            return True

    def _set_text(self, textbox, text, follow_bottom=False):
        try:
            first, _ = textbox.yview()
            x_first, _ = textbox.xview()
        except tk.TclError:
            first = 0.0
            x_first = 0.0
        textbox.configure(state="normal")
        textbox.delete("1.0", tk.END)
        textbox.insert("1.0", text)
        textbox.configure(state="disabled")
        if follow_bottom:
            textbox.yview_moveto(1.0)
        else:
            textbox.yview_moveto(first)
        textbox.xview_moveto(x_first)

    def _on_close(self):
        if self._closed:
            return
        self._closed = True
        if self._poll_after_id is not None:
            try:
                self.after_cancel(self._poll_after_id)
            except tk.TclError:
                pass
        self._stop_hooks()
        super().destroy()


