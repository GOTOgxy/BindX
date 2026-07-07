# -*- coding: utf-8 -*-

"""BindX 统一 UI。

单进程、单托盘、单 mainloop，内含三页 customtkinter 视图：
  - 总览：双引擎运行状态 + 启停按钮 + 全局动作
  - Hot Key：复刻 app_hotkey_manager/gui.py 的条目管理 Treeview，复用 EntryDialog
  - Mouse：复刻 mouse_click/gui.py 的映射管理 Treeview，复用 AddMappingDialog

对话框类经 config_proxy 从子项目模块（bindx_hk_gui / bindx_mc_gui）取得，
子项目源码零修改。
"""

import ctypes
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from ctypes import wintypes
from tkinter import ttk, messagebox

import customtkinter as ctk

import config_proxy
from tray import TrayIcon

_hk_gui = config_proxy.hk_gui_module()
_mc_gui = config_proxy.mc_gui_module()

EntryDialog = _hk_gui.EntryDialog
HotkeyCaptureDialog = _hk_gui.HotkeyCaptureDialog
AddMappingDialog = _mc_gui.AddMappingDialog


ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")


def _clamp(value, low, high):
    return max(low, min(high, value))


def _compute_ui_scale(root):
    try:
        dpi_scale = root.winfo_fpixels("1i") / 96.0
    except tk.TclError:
        dpi_scale = 1.0
    screen_w = max(root.winfo_screenwidth(), 1)
    screen_h = max(root.winfo_screenheight(), 1)
    resolution_scale = min(screen_w / 1920, screen_h / 1080)
    return _clamp(max(dpi_scale, resolution_scale, 1.0), 1.0, 1.45)


def scaled(widget, value):
    scale = getattr(widget.winfo_toplevel(), "ui_scale", 1.0)
    return int(round(value * scale))


def ui_font(widget, size, weight=None):
    return ctk.CTkFont(family="Microsoft YaHei UI", size=scaled(widget, size), weight=weight)


class OverviewTab(ctk.CTkFrame):
    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.app = app

        ctk.CTkLabel(self, text="引擎总览", font=ui_font(self, 20, "bold")).pack(anchor=tk.W, pady=(0, scaled(self, 16)))

        cards = ctk.CTkFrame(self, fg_color="transparent")
        cards.pack(fill=tk.X)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self.hk_card = ctk.CTkFrame(cards, corner_radius=10)
        self.hk_card.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 8))
        ctk.CTkLabel(self.hk_card, text="热键引擎", font=ui_font(self, 15, "bold")).pack(anchor=tk.W, padx=scaled(self, 16), pady=(scaled(self, 14), scaled(self, 6)))
        self.hk_status = ctk.CTkLabel(self.hk_card, text="运行中", anchor="w", font=ui_font(self, 13))
        self.hk_status.pack(anchor=tk.W, fill=tk.X, padx=16, pady=(0, 12))
        btns_hk = ctk.CTkFrame(self.hk_card, fg_color="transparent")
        btns_hk.pack(fill=tk.X, padx=16, pady=(0, 16))
        ctk.CTkButton(btns_hk, text="启动", command=self._start_hk, width=72).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(btns_hk, text="停止", command=self._stop_hk, width=72, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT)

        self.mc_card = ctk.CTkFrame(cards, corner_radius=10)
        self.mc_card.grid(row=0, column=1, sticky=tk.NSEW)
        ctk.CTkLabel(self.mc_card, text="鼠标映射", font=ui_font(self, 15, "bold")).pack(anchor=tk.W, padx=scaled(self, 16), pady=(scaled(self, 14), scaled(self, 6)))
        self.mc_status = ctk.CTkLabel(self.mc_card, text="运行中", anchor="w", font=ui_font(self, 13))
        self.mc_status.pack(anchor=tk.W, fill=tk.X, padx=16, pady=(0, 12))
        btns_mc = ctk.CTkFrame(self.mc_card, fg_color="transparent")
        btns_mc.pack(fill=tk.X, padx=16, pady=(0, 16))
        ctk.CTkButton(btns_mc, text="启动", command=self._start_mc, width=72).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(btns_mc, text="停止", command=self._stop_mc, width=72, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT)

        actions = ctk.CTkFrame(self, corner_radius=10)
        actions.pack(fill=tk.X, pady=(16, 0))
        ctk.CTkLabel(actions, text="全局动作", font=ui_font(self, 15, "bold")).pack(anchor=tk.W, padx=scaled(self, 16), pady=(scaled(self, 14), scaled(self, 10)))
        action_row = ctk.CTkFrame(actions, fg_color="transparent")
        action_row.pack(fill=tk.X, padx=16, pady=(0, 16))
        ctk.CTkButton(action_row, text="全部启动", command=self._start_all, width=96).pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(action_row, text="全部停止", command=self._stop_all, width=96, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(action_row, text="退出 BindX", command=self.app._quit_app, width=104, fg_color="#991b1b", hover_color="#7f1d1d").pack(side=tk.RIGHT)

        self.refresh()

    def _start_hk(self):
        self.controller.start_hotkey()
        self.refresh()

    def _stop_hk(self):
        self.controller.stop_hotkey()
        self.refresh()

    def _start_mc(self):
        self.controller.start_mouse()
        self.refresh()

    def _stop_mc(self):
        self.controller.stop_mouse()
        self.refresh()

    def _start_all(self):
        self.controller.start_hotkey()
        self.controller.start_mouse()
        self.refresh()

    def _stop_all(self):
        self.controller.stop_hotkey()
        self.controller.stop_mouse()
        self.refresh()

    def refresh(self):
        if self.controller.hk_running:
            enabled_entries = [e for e in self.controller.hotkey_manager.entries if e.get("enabled", True)]
            registered = sum(1 for e in enabled_entries if e.get("registered"))
            failed = sum(1 for e in enabled_entries if e.get("last_error"))
            suffix = f"（{registered}/{len(enabled_entries)} 已注册"
            if failed:
                suffix += f"，{failed} 失败"
            suffix += "）"
            self.hk_status.configure(text=f"运行中 {suffix}")
        else:
            self.hk_status.configure(text="已停止")

        if self.controller.mc_running and self.controller.trigger_engine.running:
            self.mc_status.configure(text="运行中")
        elif self.controller.mc_running and self.controller.trigger_engine.last_error:
            self.mc_status.configure(text=f"启动失败 {self.controller.trigger_engine.last_error}")
        else:
            self.mc_status.configure(text="已停止")


class HotKeyTab(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.manager = controller.hotkey_manager
        self._create_ui()
        self._refresh_list()
        self.after(100, self._refresh_list)

    def _create_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 12))
        ctk.CTkLabel(header, text="热键", font=ui_font(self, 20, "bold")).pack(side=tk.LEFT)

        toolbar = ctk.CTkFrame(self, corner_radius=10)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        ctk.CTkButton(toolbar, text="添加", command=self._add_entry, width=76).pack(side=tk.LEFT, padx=(12, 6), pady=10)
        ctk.CTkButton(toolbar, text="编辑", command=self._edit_entry, width=76).pack(side=tk.LEFT, padx=6, pady=10)
        ctk.CTkButton(toolbar, text="删除", command=self._delete_entry, width=76, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=6, pady=10)
        ctk.CTkButton(toolbar, text="刷新", command=self._refresh_list, width=76, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=6, pady=10)

        list_frame = ctk.CTkFrame(self, corner_radius=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("app", "hotkey", "enabled", "registered", "launch", "path")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("app", text="应用")
        self.tree.heading("hotkey", text="快捷键")
        self.tree.heading("enabled", text="启用")
        self.tree.heading("registered", text="注册")
        self.tree.heading("launch", text="启动未运行")
        self.tree.heading("path", text="安装路径")
        self.tree.column("app", width=120, minwidth=80)
        self.tree.column("hotkey", width=120, minwidth=100)
        self.tree.column("enabled", width=60, minwidth=50, anchor=tk.CENTER)
        self.tree.column("registered", width=90, minwidth=70, anchor=tk.CENTER)
        self.tree.column("launch", width=100, minwidth=80, anchor=tk.CENTER)
        self.tree.column("path", width=210, minwidth=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="编辑", command=self._edit_entry)
        self.context_menu.add_command(label="启用/禁用", command=self._toggle_entry)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_entry)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill=tk.X)
        self.status_label = ctk.CTkLabel(status_frame, text="就绪", text_color="#71717a", font=ui_font(self, 14))
        self.status_label.pack(side=tk.LEFT, padx=2, pady=(8, 0))

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for entry in self.manager.entries:
            app_id = entry["config_entry"].get("app", "")
            if app_id == "generic":
                exe_name = entry["config_entry"].get("exe_name", "")
                if not exe_name:
                    install_path = entry["config_entry"].get("install_path", "")
                    if install_path:
                        exe_name = Path(install_path).name
                app_name = f"通用 | {exe_name}" if exe_name else "通用"
            elif app_id == "web_app":
                exe_name = entry["config_entry"].get("exe_name", "")
                browser = "Chrome" if exe_name == "chrome.exe" else "Edge"
                keyword = entry["config_entry"].get("title_keyword", "")
                app_name = f"网页 | {browser} | {keyword}"
            else:
                app_name = EntryDialog.APP_NAMES.get(app_id, app_id)
            hotkey = entry["hotkey"]
            enabled = "✓" if entry.get("enabled", True) else "✗"
            if not entry.get("enabled", True):
                registered = "未启用"
            elif not self.controller.hk_running:
                registered = "引擎停止"
            elif entry.get("registered"):
                registered = "已注册"
            else:
                err = entry.get("last_error")
                registered = f"失败 {err}" if err else "待注册"
            launch = "✓" if entry["config_entry"].get("launch_if_not_running", False) else "✗"
            path = entry["config_entry"].get("install_path", "")
            self.tree.insert("", tk.END, iid=str(entry["id"]),
                             values=(app_name, hotkey, enabled, registered, launch, path))
        count = len(self.manager.entries)
        self.status_label.configure(text=f"共 {count} 个条目")

    def _get_selected_id(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _add_entry(self):
        dlg = EntryDialog(self)
        self.wait_window(dlg)
        if hasattr(dlg, "result") and dlg.result:
            data = dlg.result
            try:
                entry = self.manager.add_entry(
                    app_id=data["app"], hotkey=data["hotkey"], enabled=data["enabled"],
                    launch_if_not_running=data["launch_if_not_running"],
                    install_path=data["install_path"],
                    exe_name=data.get("exe_name", ""), title_keyword=data.get("title_keyword", ""),
                )
            except ValueError as e:
                messagebox.showerror("错误", str(e), parent=self)
                return
            if entry:
                self._refresh_list()
                self.after(100, self._refresh_list)

    def _edit_entry(self):
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("提示", "请先选择一个条目", parent=self)
            return
        entry = self.manager.entry_map.get(entry_id)
        if not entry:
            return
        dlg = EntryDialog(self, entry)
        self.wait_window(dlg)
        if hasattr(dlg, "result") and dlg.result:
            data = dlg.result
            try:
                self.manager.update_entry(
                    entry_id=entry_id, app_id=data["app"], hotkey=data["hotkey"],
                    enabled=data["enabled"], launch_if_not_running=data["launch_if_not_running"],
                    install_path=data["install_path"],
                    exe_name=data.get("exe_name", ""), title_keyword=data.get("title_keyword", ""),
                )
            except ValueError as e:
                messagebox.showerror("错误", str(e), parent=self)
                return
            self._refresh_list()
            self.after(100, self._refresh_list)

    def _delete_entry(self):
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("提示", "请先选择一个条目", parent=self)
            return
        if messagebox.askyesno("确认", "确定要删除这个条目吗？", parent=self):
            self.manager.remove_entry(entry_id)
            self._refresh_list()

    def _toggle_entry(self):
        entry_id = self._get_selected_id()
        if entry_id is None:
            messagebox.showinfo("提示", "请先选择一个条目", parent=self)
            return
        self.manager.toggle_entry(entry_id)
        self._refresh_list()
        self.after(100, self._refresh_list)

    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region != "cell":
            return
        column = self.tree.identify_column(event.x)
        entry_id = self._get_selected_id()
        if entry_id is None:
            return
        entry = self.manager.entry_map.get(entry_id)
        if not entry:
            return
        if column == "#3":
            self.manager.toggle_entry(entry_id)
            self._refresh_list()
            self.after(100, self._refresh_list)
        elif column == "#5":
            old_val = entry["config_entry"].get("launch_if_not_running", False)
            entry["config_entry"]["launch_if_not_running"] = not old_val
            self.manager._save_config()
            self._refresh_list()
        else:
            self._edit_entry()

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)


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

    def __init__(self, parent):
        super().__init__(parent)
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
                f"{index}. {item['recorded_at']}  {item['name']}\n"
                f"  VK=0x{item['vk']:02X} ({item['vk']})  "
                f"SC=0x{item['scan']:02X} ({item['scan']})  "
                f"flags=0x{item['flags']:02X}  msg=0x{item['msg']:04X}"
            )
        mouse_lines = []
        for index, item in enumerate(self._mouse_history, start=1):
            mouse_lines.append(
                f"{index}. {item['recorded_at']}  {item['name']}\n"
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


class MouseTab(ctk.CTkFrame):
    def __init__(self, parent, controller):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.config = controller.mc_config
        self._create_ui()
        self._refresh_list()

    def _create_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill=tk.X, pady=(0, 12))
        ctk.CTkLabel(header, text="鼠标映射", font=ui_font(self, 20, "bold")).pack(side=tk.LEFT)

        toolbar = ctk.CTkFrame(self, corner_radius=10)
        toolbar.pack(fill=tk.X, pady=(0, 12))

        ctk.CTkButton(toolbar, text="添加映射", command=self._add_mapping, width=92).pack(side=tk.LEFT, padx=(12, 6), pady=10)
        ctk.CTkButton(toolbar, text="编辑", command=self._edit_entry, width=76).pack(side=tk.LEFT, padx=6, pady=10)
        ctk.CTkButton(toolbar, text="删除", command=self._delete_entry, width=76, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=6, pady=10)
        ctk.CTkButton(toolbar, text="按键检查", command=self._open_input_inspector, width=92, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=6, pady=10)

        list_frame = ctk.CTkFrame(self, corner_radius=10)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("enabled", "type", "trigger", "output", "desc")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("enabled", text="启用")
        self.tree.heading("type", text="类型")
        self.tree.heading("trigger", text="触发")
        self.tree.heading("output", text="输出")
        self.tree.heading("desc", text="描述")
        self.tree.column("enabled", width=50, minwidth=40, anchor=tk.CENTER)
        self.tree.column("type", width=60, minwidth=50, anchor=tk.CENTER)
        self.tree.column("trigger", width=160, minwidth=100)
        self.tree.column("output", width=160, minwidth=100)
        self.tree.column("desc", width=220, minwidth=100)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Button-3>", self._on_right_click)

        self.context_menu = tk.Menu(self, tearoff=0)
        self.context_menu.add_command(label="编辑", command=self._edit_entry)
        self.context_menu.add_command(label="启用/禁用", command=self._toggle_enabled)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_entry)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill=tk.X)
        self.status_label = ctk.CTkLabel(status_frame, text="就绪", text_color="#71717a", font=ui_font(self, 14))
        self.status_label.pack(side=tk.LEFT, padx=2, pady=(8, 0))

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        idx = 0
        for m in self.config.get("mappings", []):
            trigger = " + ".join(m.get("trigger", []))
            output = " + ".join(m.get("output", []))
            desc = m.get("description", f"{trigger} -> {output}")
            enabled = "✓" if m.get("enabled", True) else "✗"
            self.tree.insert("", tk.END, iid=f"k{idx}", values=(enabled, "键盘", trigger, output, desc))
            idx += 1
        idx = 0
        for m in self.config.get("mouse_mappings", []):
            button = m.get("button", "")
            output = " + ".join(m.get("output", []))
            desc = m.get("description", f"Mouse {button} -> {output}")
            enabled = "✓" if m.get("enabled", True) else "✗"
            self.tree.insert("", tk.END, iid=f"m{idx}", values=(enabled, "鼠标", f"Mouse {button}", output, desc))
            idx += 1
        total = len(self.config.get("mappings", [])) + len(self.config.get("mouse_mappings", []))
        self.status_label.configure(text=f"共 {total} 个映射")

    def _add_mapping(self):
        dlg = AddMappingDialog(self, "keyboard")
        self.wait_window(dlg)
        if dlg.result:
            mapping = self._mapping_from_dialog(dlg, dlg.result.get("enabled", True))
            if dlg.mapping_type == "mouse":
                self.config.setdefault("mouse_mappings", []).append(mapping)
            else:
                self.config.setdefault("mappings", []).append(mapping)
            self._save_and_restart()

    def _open_input_inspector(self):
        win = InputInspectorWindow(self)
        win.focus_force()

    def _mapping_from_dialog(self, dlg, enabled):
        if dlg.mapping_type == "mouse":
            return {
                "button": dlg.result["button"],
                "output": dlg.result["output"],
                "description": dlg.result.get("description", ""),
                "enabled": enabled,
            }
        mapping = dict(dlg.result)
        mapping["enabled"] = enabled
        return mapping

    def _on_double_click(self, event):
        region = self.tree.identify("region", event.x, event.y)
        if region == "cell":
            column = self.tree.identify_column(event.x)
            if column == "#1":
                self._toggle_enabled()

    def _toggle_enabled(self):
        sel = self.tree.selection()
        if not sel:
            return
        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])
        if is_keyboard:
            mappings = self.config.get("mappings", [])
        else:
            mappings = self.config.get("mouse_mappings", [])
        if idx >= len(mappings):
            return
        m = mappings[idx]
        m["enabled"] = not m.get("enabled", True)
        self._save_and_restart()

    def _edit_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个映射", parent=self)
            return
        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])
        if is_keyboard:
            mappings = self.config.get("mappings", [])
            if idx >= len(mappings):
                return
            old = mappings[idx]
            dlg = AddMappingDialog(self, "keyboard")
            dlg.type_var.set("keyboard")
            dlg._on_type_changed()
            dlg.trigger_var.set(" + ".join(old.get("trigger", [])))
            dlg.output_var.set(" + ".join(old.get("output", [])))
            dlg.desc_var.set(old.get("description", ""))
        else:
            mappings = self.config.get("mouse_mappings", [])
            if idx >= len(mappings):
                return
            old = mappings[idx]
            dlg = AddMappingDialog(self, "mouse")
            dlg.type_var.set("mouse")
            dlg._on_type_changed()
            dlg.button_var.set(old.get("button", "x1"))
            dlg.output_var.set(" + ".join(old.get("output", [])))
            dlg.desc_var.set(old.get("description", ""))
        self.wait_window(dlg)
        if dlg.result:
            old_enabled = old.get("enabled", True)
            new_mapping = self._mapping_from_dialog(dlg, old_enabled)
            keyboard_mappings = self.config.setdefault("mappings", [])
            mouse_mappings = self.config.setdefault("mouse_mappings", [])
            if dlg.mapping_type == "mouse":
                if is_keyboard:
                    del keyboard_mappings[idx]
                    mouse_mappings.append(new_mapping)
                else:
                    mouse_mappings[idx] = new_mapping
            else:
                if is_keyboard:
                    keyboard_mappings[idx] = new_mapping
                else:
                    del mouse_mappings[idx]
                    keyboard_mappings.append(new_mapping)
            self._save_and_restart()

    def _delete_entry(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("提示", "请先选择一个映射", parent=self)
            return
        if not messagebox.askyesno("确认", "确定要删除这个映射吗？", parent=self):
            return
        item_id = sel[0]
        is_keyboard = item_id.startswith("k")
        idx = int(item_id[1:])
        if is_keyboard:
            mappings = self.config.get("mappings", [])
            if idx < len(mappings):
                del mappings[idx]
        else:
            mappings = self.config.get("mouse_mappings", [])
            if idx < len(mappings):
                del mappings[idx]
        self._save_and_restart()

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)

    def _save_and_restart(self):
        self.controller.save_mouse_config(self.config)
        self.controller.restart_mouse()
        self.config = self.controller.mc_config
        self._refresh_list()

    def reload_config(self):
        self.config = self.controller.mc_config
        self._refresh_list()


class BindXApp(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.ui_scale = _compute_ui_scale(self)
        ctk.set_widget_scaling(self.ui_scale)
        ctk.set_window_scaling(self.ui_scale)
        self.tk.call("tk", "scaling", self.ui_scale)

        self.title("BindX")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        max_w = max(1, int(screen_w * 0.92))
        max_h = max(1, int(screen_h * 0.88))
        default_w = min(max(scaled(self, 980), int(screen_w * 0.72)), max_w)
        default_h = min(max(scaled(self, 640), int(screen_h * 0.72)), max_h)
        self.geometry(f"{default_w}x{default_h}")
        self.minsize(min(scaled(self, 860), max_w), min(scaled(self, 540), max_h))
        self.configure(fg_color=("#f4f4f5", "#18181b"))

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self._setup_tree_style()

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=scaled(self, 190), corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_propagate(False)

        ctk.CTkLabel(self.sidebar, text="BindX", font=ui_font(self, 24, "bold")).pack(anchor=tk.W, padx=scaled(self, 20), pady=(scaled(self, 22), scaled(self, 4)))
        ctk.CTkLabel(self.sidebar, text="全局快捷控制", text_color="#71717a", font=ui_font(self, 12)).pack(anchor=tk.W, padx=scaled(self, 20), pady=(0, scaled(self, 20)))

        self.nav_buttons = {}
        self.nav_buttons["overview"] = self._nav_button("总览", lambda: self._show_page("overview"))
        self.nav_buttons["hotkey"] = self._nav_button("热键", lambda: self._show_page("hotkey"))
        self.nav_buttons["mouse"] = self._nav_button("鼠标映射", lambda: self._show_page("mouse"))

        self.sidebar_status = ctk.CTkLabel(self.sidebar, text="", justify=tk.LEFT, anchor="w", text_color="#71717a", font=ui_font(self, 12))
        self.sidebar_status.pack(side=tk.BOTTOM, fill=tk.X, padx=scaled(self, 20), pady=scaled(self, 18))

        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.grid(row=0, column=1, sticky="nsew", padx=scaled(self, 18), pady=scaled(self, 18))
        self.content.grid_columnconfigure(0, weight=1)
        self.content.grid_rowconfigure(0, weight=1)

        self.overview_tab = OverviewTab(self.content, controller, self)
        self.hotkey_tab = HotKeyTab(self.content, controller)
        self.mouse_tab = MouseTab(self.content, controller)
        self.pages = {
            "overview": self.overview_tab,
            "hotkey": self.hotkey_tab,
            "mouse": self.mouse_tab,
        }
        for page in self.pages.values():
            page.grid(row=0, column=0, sticky="nsew")
        self._show_page("overview")

        self.tray = TrayIcon(on_show=self._show_window, on_menu=self._show_tray_menu)

        self.controller.set_hotkey_self_callback(self.toggle_ui)

        self._poll_tray()
        self._poll_hotkeys()
        self._refresh_status_loop()
        self._resize_after_id = None
        self.bind("<Configure>", self._on_window_configure)

    def _setup_tree_style(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Treeview",
            borderwidth=0,
            relief="flat",
            background="#ffffff",
            fieldbackground="#ffffff",
            foreground="#18181b",
        )
        style.configure(
            "Treeview.Heading",
            background="#e4e4e7",
            foreground="#27272a",
            relief="flat",
        )
        style.map("Treeview", background=[("selected", "#2563eb")], foreground=[("selected", "#ffffff")])
        self._apply_adaptive_table_style()

    def _table_font_size(self):
        width = max(self.winfo_width(), int(self.winfo_screenwidth() * 0.72))
        height = max(self.winfo_height(), int(self.winfo_screenheight() * 0.72))
        size_by_height = 15 + (height - 640) / 240
        size_by_width = 15 + (width - 980) / 360
        return int(round(_clamp(max(size_by_height, size_by_width), 14, 18)))

    def _apply_adaptive_table_style(self):
        base_size = self._table_font_size()
        font_size = scaled(self, base_size)
        rowheight = scaled(self, int(base_size * 3.15))
        style = ttk.Style(self)
        style.configure("Treeview", font=("Microsoft YaHei UI", font_size), rowheight=rowheight)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", font_size, "bold"))

    def _on_window_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(120, self._apply_adaptive_table_style)

    def _nav_button(self, text, command):
        btn = ctk.CTkButton(
            self.sidebar,
            text=text,
            command=command,
            height=scaled(self, 40),
            anchor="w",
            font=ui_font(self, 14),
            fg_color="transparent",
            text_color=("#27272a", "#e4e4e7"),
            hover_color=("#e4e4e7", "#27272a"),
        )
        btn.pack(fill=tk.X, padx=scaled(self, 12), pady=scaled(self, 4))
        return btn

    def _show_page(self, name):
        self.pages[name].tkraise()
        for key, btn in self.nav_buttons.items():
            if key == name:
                btn.configure(fg_color=("#dbeafe", "#1d4ed8"), text_color=("#1d4ed8", "#ffffff"))
            else:
                btn.configure(fg_color="transparent", text_color=("#27272a", "#e4e4e7"))

    def _poll_tray(self):
        self.tray.poll()
        self.after(10, self._poll_tray)

    def _poll_hotkeys(self):
        self.controller.process_hotkeys()
        self.after(20, self._poll_hotkeys)

    def _refresh_status_loop(self):
        self.overview_tab.refresh()
        hook_state = "运行中" if self.controller.trigger_engine.running else "未运行"
        self.sidebar_status.configure(
            text=f"Hook: {hook_state}\n热键: {'开' if self.controller.hk_running else '关'}\n鼠标: {'开' if self.controller.mc_running else '关'}"
        )
        self.after(500, self._refresh_status_loop)

    def _show_tray_menu(self):
        menu_font = ("Microsoft YaHei UI", scaled(self, 14))
        menu = tk.Menu(self, tearoff=0, font=menu_font)
        menu.configure(font=menu_font)
        hook_state = "运行中" if self.controller.trigger_engine.running else "未运行"
        menu.add_command(label=f"Hook：{hook_state}", state=tk.DISABLED)
        menu.add_command(
            label=f"Keyboard：{'开' if self.controller.hk_running else '关'} / Mouse：{'开' if self.controller.mc_running else '关'}",
            state=tk.DISABLED,
        )
        menu.add_command(label=f"最近：{self.controller.trigger_engine.last_event}", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="显示主窗口", command=self._show_window)
        menu.add_separator()
        if self.controller.hk_running:
            menu.add_command(label="停止 Hot Key", command=self._tray_stop_hk)
        else:
            menu.add_command(label="启动 Hot Key", command=self._tray_start_hk)
        if self.controller.mc_running:
            menu.add_command(label="停止 Mouse", command=self._tray_stop_mc)
        else:
            menu.add_command(label="启动 Mouse", command=self._tray_start_mc)
        menu.add_separator()
        menu.add_command(label="全部启动", command=self._tray_start_all)
        menu.add_command(label="全部停止", command=self._tray_stop_all)
        menu.add_command(label="重新安装 Hook", command=self._tray_reinstall_hooks)
        menu.add_separator()
        menu.add_command(label="退出", command=self._quit_app)
        self.tray.show_menu_at_cursor(menu)

    def _tray_start_hk(self):
        self.controller.start_hotkey()
        self.mouse_tab.reload_config()

    def _tray_stop_hk(self):
        self.controller.stop_hotkey()

    def _tray_start_mc(self):
        self.controller.start_mouse()
        self.mouse_tab.reload_config()

    def _tray_stop_mc(self):
        self.controller.stop_mouse()

    def _tray_start_all(self):
        self.controller.start_hotkey()
        self.controller.start_mouse()

    def _tray_stop_all(self):
        self.controller.stop_hotkey()
        self.controller.stop_mouse()

    def _tray_reinstall_hooks(self):
        self.controller.reinstall_hooks()

    def _show_window(self):
        self.deiconify()
        self.lift()
        self.focus_force()

    def toggle_ui(self):
        if self.state() == "withdrawn" or self.state() == "iconic":
            self._show_window()
        else:
            self.withdraw()

    def _on_close(self):
        self.withdraw()

    def _quit_app(self):
        self.controller.quit()
        self.tray.destroy()
        self.after(100, self.destroy)
