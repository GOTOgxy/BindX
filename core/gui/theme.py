# -*- coding: utf-8 -*-

"""BindX 统一 UI。

单进程、单托盘、单 mainloop，内含三页 customtkinter 视图：
  - 总览：双引擎运行状态 + 启停按钮 + 全局动作
  - Hot Key：热键条目管理
  - Mouse：鼠标映射管理
"""

import ctypes
import os
import queue
import threading
import time
import tkinter as tk
from pathlib import Path
from ctypes import wintypes
from tkinter import ttk, messagebox, filedialog

import customtkinter as ctk

from .. import config_proxy, shortcut_manager
from ..tray import TrayIcon

_hk_logic = config_proxy.hk_module()


ctk.set_appearance_mode("system")
ctk.set_default_color_theme("blue")

BUTTON_THEME = ctk.ThemeManager.theme["CTkButton"]
BUTTON_DEFAULT_FG = tuple(BUTTON_THEME["fg_color"])
BUTTON_DEFAULT_HOVER = tuple(BUTTON_THEME["hover_color"])


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


def menu_font(widget):
    root = widget.winfo_toplevel()
    if hasattr(root, "_get_font_preset"):
        preset = root._get_font_preset()
    else:
        preset = "常规"
    size = FONT_PRESET_TRAY_SIZE.get(preset, FONT_PRESET_TRAY_SIZE["常规"])
    return ("Microsoft YaHei UI", scaled(widget, size))


def _force_toplevel_foreground(window):
    try:
        hwnd = int(window.winfo_id())
    except (tk.TclError, ValueError):
        return False
    if not hwnd:
        return False
    try:
        window.lift()
        window.attributes("-topmost", True)
        window.update_idletasks()
        ok = bool(_hk_logic.force_foreground_window(hwnd))
        window.attributes("-topmost", False)
        window.focus_force()
        return ok
    except tk.TclError:
        return False


FONT_PRESET_TABLE_SIZE = {
    "紧凑": 16,
    "稍小": 19,
    "常规": 22,
    "特大": 26,
    "超大": 30,
}

FONT_PRESET_TRAY_SIZE = {
    "紧凑": 16,
    "稍小": 19,
    "常规": 22,
    "特大": 26,
    "超大": 30,
}

FONT_PRESET_DIALOG_SIZE = {
    "紧凑": 15,
    "稍小": 17,
    "常规": 19,
    "特大": 22,
    "超大": 25,
}


def _parse_window_size(value):
    if not isinstance(value, str) or "x" not in value:
        return None
    width_text, height_text = value.split("x", 1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError:
        return None
    if width <= 0 or height <= 0:
        return None
    return width, height


def _dialog_font(widget, delta=0, weight=None):
    root = getattr(widget, "_bindx_root", None) or widget.winfo_toplevel()
    if hasattr(root, "_get_font_preset"):
        preset = root._get_font_preset()
    else:
        preset = getattr(widget, "_dialog_font_preset", "常规")
    size = FONT_PRESET_DIALOG_SIZE.get(preset, FONT_PRESET_DIALOG_SIZE["常规"]) + delta
    return ctk.CTkFont(family="Microsoft YaHei UI", size=scaled(widget, size), weight=weight)


def _readonly_entry(parent, variable, width=None):
    kwargs = {"textvariable": variable, "font": _dialog_font(parent)}
    if width is not None:
        kwargs["width"] = width
    entry = ctk.CTkEntry(parent, **kwargs)
    entry.bind("<Key>", lambda _event: "break")
    return entry


class _BindXDialog(ctk.CTkToplevel):
    def __init__(self, parent, title, width, height):
        super().__init__(parent)
        self._bindx_root = parent.winfo_toplevel()
        self.ui_scale = getattr(self._bindx_root, "ui_scale", 1.0)
        self._dialog_font_preset = (
            self._bindx_root._get_font_preset()
            if hasattr(self._bindx_root, "_get_font_preset")
            else "常规"
        )
        self.result = None

        self.title(title)
        self.geometry(f"{scaled(self, width)}x{scaled(self, height)}")
        self.minsize(scaled(self, width), scaled(self, height))
        self.resizable(False, False)
        self.configure(fg_color=("#f4f4f5", "#18181b"))
        self.transient(self._bindx_root)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill=tk.BOTH, expand=True, padx=scaled(self, 20), pady=scaled(self, 18))
        self.after(50, self.focus_force)

    def _center_on_parent(self):
        self.update_idletasks()
        parent = self._bindx_root
        x = parent.winfo_x() + max(0, (parent.winfo_width() - self.winfo_width()) // 2)
        y = parent.winfo_y() + max(0, (parent.winfo_height() - self.winfo_height()) // 2)
        self.geometry(f"+{x}+{y}")

    def _label(self, parent, text, width=118):
        return ctk.CTkLabel(parent, text=text, width=scaled(self, width), anchor="w", font=_dialog_font(self))

    def _row(self, parent=None, pady=(0, 10)):
        row = ctk.CTkFrame(parent or self.body, fg_color="transparent")
        row.pack(fill=tk.X, pady=(scaled(self, pady[0]), scaled(self, pady[1])))
        return row

    def _button_row(self):
        row = ctk.CTkFrame(self.body, fg_color="transparent")
        row.pack(fill=tk.X, pady=(scaled(self, 12), 0))
        return row

    def _secondary_button(self, parent, text, command, width=84):
        return ctk.CTkButton(
            parent,
            text=text,
            command=command,
            width=scaled(self, width),
            font=_dialog_font(self),
            fg_color="#52525b",
            hover_color="#3f3f46",
        )

    def _on_cancel(self):
        self.result = None
        self.destroy()


