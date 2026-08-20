# -*- coding: utf-8 -*-
"""BindX UI: 按键/鼠标捕获对话框。"""

import tkinter as tk

import customtkinter as ctk

from .theme import _BindXDialog, _dialog_font, _hk_logic, scaled

class HotkeyCaptureDialog(_BindXDialog):
    KEYSYM_MAP = {
        "return": "ENTER",
        "escape": "ESC",
        "space": "SPACE",
        "left": "LEFT",
        "right": "RIGHT",
        "up": "UP",
        "down": "DOWN",
        "home": "HOME",
        "end": "END",
        "prior": "PAGEUP",
        "next": "PAGEDOWN",
        "insert": "INSERT",
        "delete": "DELETE",
        "tab": "TAB",
    }
    MODIFIER_MAP = {
        "control_l": "CTRL",
        "control_r": "CTRL",
        "alt_l": "ALT",
        "alt_r": "ALT",
        "shift_l": "SHIFT",
        "shift_r": "SHIFT",
        "super_l": "WIN",
        "super_r": "WIN",
        "meta_l": "WIN",
        "meta_r": "WIN",
    }
    MODIFIER_ORDER = ("CTRL", "ALT", "SHIFT", "WIN")

    def __init__(self, parent, current_hotkey=""):
        super().__init__(parent, "录制快捷键", 560, 250)
        self.captured_hotkey = current_hotkey
        self.captured = False
        self._pressed = set()

        ctk.CTkLabel(self.body, text="请按下快捷键组合", font=_dialog_font(self, 2, "bold")).pack(anchor=tk.W, pady=(0, scaled(self, 10)))
        self.hotkey_var = tk.StringVar(value=current_hotkey or "等待输入...")
        ctk.CTkLabel(self.body, textvariable=self.hotkey_var, font=_dialog_font(self, 5, "bold")).pack(fill=tk.X, pady=(0, scaled(self, 18)))

        btns = self._button_row()
        ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 88), font=_dialog_font(self)).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self.ok_btn = btns.winfo_children()[-1]
        self.ok_btn.configure(state=tk.NORMAL if current_hotkey else tk.DISABLED)
        self._secondary_button(btns, "取消", self._on_cancel).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self._secondary_button(btns, "清除", self._on_clear).pack(side=tk.RIGHT)

        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self._center_on_parent()

    def _normalize(self, keysym):
        key = keysym.lower()
        if key in self.MODIFIER_MAP:
            return self.MODIFIER_MAP[key]
        if len(key) == 1:
            return key.upper()
        if key.startswith("kp_") and key[3:].isdigit():
            return key[3:]
        if key.startswith("f") and key[1:].isdigit():
            return key.upper()
        return self.KEYSYM_MAP.get(key, key.upper())

    def _on_key_release(self, event):
        name = self._normalize(event.keysym)
        if name in self.MODIFIER_ORDER:
            self._pressed.discard(name)

    def _on_key_press(self, event):
        name = self._normalize(event.keysym)
        if name in self.MODIFIER_ORDER:
            self._pressed.add(name)
            return
        if name not in _hk_logic.VIRTUAL_KEYS:
            self.hotkey_var.set(f"不支持：{name}")
            self.ok_btn.configure(state=tk.DISABLED)
            return
        modifiers = [mod for mod in self.MODIFIER_ORDER if mod in self._pressed]
        self.captured_hotkey = "+".join(modifiers + [name])
        self.hotkey_var.set(self.captured_hotkey)
        self.captured = True
        self.ok_btn.configure(state=tk.NORMAL)

    def _on_clear(self):
        self.captured_hotkey = ""
        self.captured = False
        self._pressed.clear()
        self.hotkey_var.set("等待输入...")
        self.ok_btn.configure(state=tk.DISABLED)

    def _on_ok(self):
        if self.captured_hotkey:
            self.result = self.captured_hotkey
            self.destroy()


class KeyCaptureDialog(_BindXDialog):
    KEYSYM_MAP = {
        "return": "enter",
        "escape": "esc",
        "space": "space",
        "left": "left",
        "right": "right",
        "up": "up",
        "down": "down",
        "home": "home",
        "end": "end",
        "prior": "pageup",
        "next": "pagedown",
        "insert": "insert",
        "delete": "delete",
        "backspace": "backspace",
        "caps_lock": "caps lock",
        "tab": "tab",
    }
    MODIFIER_MAP = {
        "control_l": "ctrl",
        "control_r": "ctrl",
        "alt_l": "alt",
        "alt_r": "alt",
        "shift_l": "shift",
        "shift_r": "shift",
        "super_l": "win",
        "super_r": "win",
        "meta_l": "win",
        "meta_r": "win",
    }
    MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")

    def __init__(self, parent, title="录制按键"):
        super().__init__(parent, title, 540, 230)
        self._pressed = set()
        self._captured = []

        ctk.CTkLabel(self.body, text="请按下目标按键组合", font=_dialog_font(self, 2, "bold")).pack(anchor=tk.W, pady=(0, scaled(self, 10)))
        self.key_var = tk.StringVar(value="等待输入...")
        ctk.CTkLabel(self.body, textvariable=self.key_var, font=_dialog_font(self, 5, "bold")).pack(fill=tk.X, pady=(0, scaled(self, 18)))

        btns = self._button_row()
        ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 88), font=_dialog_font(self)).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self.ok_btn = btns.winfo_children()[-1]
        self.ok_btn.configure(state=tk.DISABLED)
        self._secondary_button(btns, "取消", self._on_cancel).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self._secondary_button(btns, "清除", self._on_clear).pack(side=tk.RIGHT)

        self.bind("<KeyPress>", self._on_key_press)
        self.bind("<KeyRelease>", self._on_key_release)
        self._center_on_parent()

    def _normalize(self, keysym):
        key = keysym.lower()
        if key in self.MODIFIER_MAP:
            return self.MODIFIER_MAP[key]
        if len(key) == 1:
            return key.lower()
        if key.startswith("kp_") and key[3:].isdigit():
            return key[3:]
        if key.startswith("f") and key[1:].isdigit():
            return key.lower()
        return self.KEYSYM_MAP.get(key, key)

    def _on_key_release(self, event):
        name = self._normalize(event.keysym)
        self._pressed.discard(name)

    def _on_key_press(self, event):
        name = self._normalize(event.keysym)
        if name in self.MODIFIER_ORDER:
            self._pressed.add(name)
            return
        modifiers = [mod for mod in self.MODIFIER_ORDER if mod in self._pressed]
        self._captured = modifiers + [name]
        self.key_var.set(" + ".join(self._captured))
        self.ok_btn.configure(state=tk.NORMAL)

    def _on_clear(self):
        self._pressed.clear()
        self._captured = []
        self.key_var.set("等待输入...")
        self.ok_btn.configure(state=tk.DISABLED)

    def _on_ok(self):
        if self._captured:
            self.result = self._captured
            self.destroy()


class MouseCaptureDialog(_BindXDialog):
    def __init__(self, parent, title="录制鼠标按键"):
        super().__init__(parent, title, 540, 230)
        self._listener = None

        ctk.CTkLabel(self.body, text="请按下鼠标按键", font=_dialog_font(self, 2, "bold")).pack(anchor=tk.W, pady=(0, scaled(self, 10)))
        self.key_var = tk.StringVar(value="等待输入...")
        ctk.CTkLabel(self.body, textvariable=self.key_var, font=_dialog_font(self, 5, "bold")).pack(fill=tk.X, pady=(0, scaled(self, 18)))

        btns = self._button_row()
        ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 88), font=_dialog_font(self)).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self.ok_btn = btns.winfo_children()[-1]
        self.ok_btn.configure(state=tk.DISABLED)
        self._secondary_button(btns, "取消", self._on_cancel).pack(side=tk.RIGHT)

        self._start_listener()
        self._center_on_parent()

    def _start_listener(self):
        try:
            from pynput import mouse as pynput_mouse
        except ImportError as exc:
            self.key_var.set(f"鼠标监听不可用：{exc}")
            return

        def on_click(_x, _y, button, pressed):
            if pressed:
                self.after(0, lambda: self._on_detected(getattr(button, "name", str(button))))

        self._listener = pynput_mouse.Listener(on_click=on_click)
        self._listener.start()

    def _on_detected(self, name):
        self.key_var.set(name)
        self.ok_btn.configure(state=tk.NORMAL)

    def _on_ok(self):
        val = self.key_var.get()
        if val and val != "等待输入..." and not val.startswith("鼠标监听不可用"):
            self.result = val
        self._stop_listener()
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self._stop_listener()
        self.destroy()

    def _stop_listener(self):
        if self._listener:
            self._listener.stop()
            self._listener = None


