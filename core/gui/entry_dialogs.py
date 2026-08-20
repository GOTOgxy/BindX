# -*- coding: utf-8 -*-
"""BindX UI: 热键条目编辑与鼠标映射添加对话框。"""

import os
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox

from .capture import HotkeyCaptureDialog, KeyCaptureDialog, MouseCaptureDialog
from .theme import _BindXDialog, _dialog_font, _readonly_entry, scaled

class EntryDialog(_BindXDialog):
    BUILTIN_APP_IDS = ["cloudmusic", "zotero", "termius", "hot_key_manager"]
    TARGET_TYPE_IDS = ["win32", "chromium", "browser_tab", "uwp", "builtin"]
    TARGET_TYPE_NAMES = {
        "win32": "Win32 窗口",
        "chromium": "Chromium 应用",
        "browser_tab": "浏览器 App",
        "uwp": "UWP 应用",
        "builtin": "内置适配",
    }
    TARGET_TYPE_NAME_TO_ID = {name: type_id for type_id, name in TARGET_TYPE_NAMES.items()}
    APP_NAMES = {
        "cloudmusic": "网易云音乐",
        "zotero": "Zotero",
        "termius": "Termius",
        "hot_key_manager": "BindX",
        "generic": "通用应用",
        "web_app": "浏览器 App",
    }
    APP_NAME_TO_ID = {name: app_id for app_id, name in APP_NAMES.items()}
    BUILTIN_TARGET_TYPES = {
        "cloudmusic": "win32",
        "zotero": "win32",
        "termius": "chromium",
        "hot_key_manager": "win32",
    }
    BUILTIN_PRESETS = {
        "cloudmusic": {
            "tray_aware": True,
            "multi_window": False,
            "launch_if_not_running": False,
            "exe_name": "cloudmusic.exe",
            "title_keyword": "",
            "path_candidates": [
                "C:/Program Files/NetEase/CloudMusic/cloudmusic.exe",
                "C:/Program Files (x86)/NetEase/CloudMusic/cloudmusic.exe",
                "%LOCALAPPDATA%/Netease/CloudMusic/cloudmusic.exe",
            ],
        },
        "zotero": {
            "tray_aware": False,
            "multi_window": False,
            "launch_if_not_running": True,
            "exe_name": "zotero.exe",
            "title_keyword": "",
            "path_candidates": [
                "C:/Program Files/Zotero/zotero.exe",
                "C:/Program Files (x86)/Zotero/zotero.exe",
            ],
        },
        "termius": {
            "tray_aware": False,
            "multi_window": False,
            "launch_if_not_running": True,
            "exe_name": "Termius.exe",
            "title_keyword": "",
            "path_candidates": [
                "%LOCALAPPDATA%/Programs/Termius/Termius.exe",
                "C:/Program Files/Termius/Termius.exe",
                "C:/Program Files (x86)/Termius/Termius.exe",
            ],
        },
        "hot_key_manager": {
            "tray_aware": True,
            "multi_window": False,
            "launch_if_not_running": False,
            "exe_name": "",
            "title_keyword": "",
            "path_candidates": [],
        },
    }
    BROWSER_MAP = {"Edge": "msedge.exe", "Chrome": "chrome.exe"}

    def __init__(self, parent, entry=None):
        super().__init__(parent, "编辑条目" if entry else "添加条目", 680, 560)
        self.entry = entry

        config_entry = entry["config_entry"] if entry else {}
        initial_app = config_entry.get("app", "generic")
        initial_target = self._target_type_for_entry(config_entry)
        self.target_type_var = tk.StringVar(value=self.TARGET_TYPE_NAMES[initial_target])
        builtin_app = initial_app if initial_app in self.BUILTIN_APP_IDS else self.BUILTIN_APP_IDS[0]
        builtin_value = self.APP_NAMES[builtin_app]
        self.builtin_var = tk.StringVar(value=builtin_value)
        self.hotkey_var = tk.StringVar(value=entry["hotkey"] if entry else "")
        self.enabled_var = tk.BooleanVar(value=entry["enabled"] if entry else True)
        self.tray_var = tk.BooleanVar(value=self._is_tray_aware(config_entry))
        self.multi_window_var = tk.BooleanVar(value=self._is_multi_window(config_entry))
        default_launch = config_entry.get("launch_if_not_running", False) if entry else False
        if entry is None and initial_target != "browser_tab":
            default_launch = True
        self.launch_var = tk.BooleanVar(value=default_launch)
        self.path_var = tk.StringVar(value=self._display_path(config_entry.get("install_path", "")))
        self.exe_var = tk.StringVar(value=config_entry.get("exe_name", ""))
        self.name_var = tk.StringVar(value=config_entry.get("name", ""))
        self.keyword_var = tk.StringVar(value=config_entry.get("title_keyword", ""))
        self.path_var.trace_add("write", lambda *_args: self._refresh_exe_row())
        saved_exe = config_entry.get("exe_name", "")
        self.browser_var = tk.StringVar(value="Chrome" if saved_exe == "chrome.exe" else "Edge")

        row = self._row()
        self._label(row, "目标类型：").pack(side=tk.LEFT)
        self.target_combo = ctk.CTkOptionMenu(
            row,
            values=[self.TARGET_TYPE_NAMES[type_id] for type_id in self.TARGET_TYPE_IDS],
            variable=self.target_type_var,
            command=self._on_app_changed,
            width=scaled(self, 230),
            font=_dialog_font(self),
        )
        self.target_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.row_builtin = self._row()
        self._label(self.row_builtin, "内置适配：").pack(side=tk.LEFT)
        self.builtin_combo = ctk.CTkOptionMenu(
            self.row_builtin,
            values=[self.APP_NAMES[app_id] for app_id in self.BUILTIN_APP_IDS],
            variable=self.builtin_var,
            width=scaled(self, 230),
            font=_dialog_font(self),
            command=self._on_builtin_changed,
        )
        self.builtin_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.row_name = self._row()
        self._label(self.row_name, "应用名：").pack(side=tk.LEFT)
        ctk.CTkEntry(self.row_name, textvariable=self.name_var, font=_dialog_font(self)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        row = self._row()
        self._label(row, "快捷键：").pack(side=tk.LEFT)
        self.hotkey_entry = _readonly_entry(row, self.hotkey_var)
        self.hotkey_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(row, text="录制", command=self._capture_hotkey, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        row = self._row()
        self._label(row, "启用：").pack(side=tk.LEFT)
        ctk.CTkCheckBox(row, text="", variable=self.enabled_var, width=scaled(self, 28), font=_dialog_font(self)).pack(side=tk.LEFT)

        row = self._row()
        self._label(row, "托盘隐藏：").pack(side=tk.LEFT)
        ctk.CTkCheckBox(row, text="", variable=self.tray_var, width=scaled(self, 28), font=_dialog_font(self)).pack(side=tk.LEFT)

        row = self._row()
        self._label(row, "多窗口：").pack(side=tk.LEFT)
        ctk.CTkCheckBox(row, text="", variable=self.multi_window_var, width=scaled(self, 28), font=_dialog_font(self)).pack(side=tk.LEFT)

        row = self._row()
        self._label(row, "热键启动：").pack(side=tk.LEFT)
        ctk.CTkCheckBox(row, text="", variable=self.launch_var, width=scaled(self, 28), font=_dialog_font(self)).pack(side=tk.LEFT)

        self.row_path = self._row()
        self._label(self.row_path, "安装路径：").pack(side=tk.LEFT)
        ctk.CTkEntry(self.row_path, textvariable=self.path_var, font=_dialog_font(self)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._secondary_button(self.row_path, "浏览", self._browse, width=82).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        self.row_exe = self._row()
        self._label(self.row_exe, "进程名：").pack(side=tk.LEFT)
        ctk.CTkEntry(self.row_exe, textvariable=self.exe_var, font=_dialog_font(self)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.row_keyword = self._row()
        self._label(self.row_keyword, "标题关键词：").pack(side=tk.LEFT)
        ctk.CTkEntry(self.row_keyword, textvariable=self.keyword_var, font=_dialog_font(self)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.row_browser = self._row()
        self._label(self.row_browser, "浏览器：").pack(side=tk.LEFT)
        ctk.CTkOptionMenu(self.row_browser, values=["Edge", "Chrome"], variable=self.browser_var, width=scaled(self, 180), font=_dialog_font(self)).pack(side=tk.LEFT)

        btns = self._button_row()
        ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 92), font=_dialog_font(self)).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self._secondary_button(btns, "取消", self._on_cancel, width=92).pack(side=tk.RIGHT)

        self._on_app_changed()
        self._center_on_parent()

    def _target_type_for_entry(self, config_entry):
        target_type = config_entry.get("target_type")
        if target_type == "tray":
            return "win32"
        if target_type == "uwp_multi":
            return "uwp"
        app_id = config_entry.get("app", "generic")
        if app_id in self.BUILTIN_APP_IDS:
            return "builtin"
        if target_type in self.TARGET_TYPE_IDS:
            return target_type
        if app_id == "web_app":
            return "browser_tab"
        return "win32"

    def _is_tray_aware(self, config_entry):
        tray_aware = config_entry.get("tray_aware")
        if isinstance(tray_aware, bool):
            return tray_aware
        if config_entry.get("target_type") == "tray":
            return True
        return config_entry.get("app") == "cloudmusic"

    def _is_multi_window(self, config_entry):
        multi_window = config_entry.get("multi_window")
        if isinstance(multi_window, bool):
            return multi_window
        return config_entry.get("target_type") == "uwp_multi"

    def _selected_target_type(self):
        return self.TARGET_TYPE_NAME_TO_ID.get(self.target_type_var.get(), self.target_type_var.get())

    def _selected_builtin_app(self):
        return self.APP_NAME_TO_ID.get(self.builtin_var.get(), self.builtin_var.get())

    @staticmethod
    def _display_path(path):
        return str(path or "").replace("\\", "/")

    def _resolve_first_existing_path(self, candidates):
        for candidate in candidates or []:
            display_path = self._display_path(os.path.expandvars(candidate))
            if Path(display_path).exists():
                return display_path
        return ""

    def _apply_builtin_preset(self):
        builtin_app = self._selected_builtin_app()
        preset = self.BUILTIN_PRESETS.get(builtin_app, {})
        self.tray_var.set(bool(preset.get("tray_aware", False)))
        self.multi_window_var.set(bool(preset.get("multi_window", False)))
        self.launch_var.set(bool(preset.get("launch_if_not_running", False)))
        self.exe_var.set(preset.get("exe_name", ""))
        self.name_var.set(self.APP_NAMES.get(builtin_app, ""))
        self.keyword_var.set(preset.get("title_keyword", ""))
        self.path_var.set(self._resolve_first_existing_path(preset.get("path_candidates", [])))

    def _on_builtin_changed(self, _value=None):
        self._apply_builtin_preset()
        self._on_app_changed()

    def _capture_hotkey(self):
        dlg = HotkeyCaptureDialog(self, self.hotkey_var.get())
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.hotkey_var.set(dlg.result)

    def _browse(self):
        path = filedialog.askopenfilename(
            title="选择可执行文件",
            filetypes=[("可执行文件", "*.exe"), ("所有文件", "*.*")],
            parent=self,
        )
        if path:
            self.path_var.set(self._display_path(path))
            self.exe_var.set(Path(path).name)
            self._refresh_exe_row()

    def _refresh_exe_row(self):
        target_type = self._selected_target_type()
        if target_type in {"builtin", "browser_tab"}:
            self.row_exe.pack_forget()
            return
        if self.path_var.get().strip():
            self.row_exe.pack_forget()
        else:
            self.row_exe.pack(fill=tk.X, pady=(0, scaled(self, 10)))

    def _on_app_changed(self, _value=None):
        target_type = self._selected_target_type()

        if target_type == "builtin":
            self.row_builtin.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            self.row_name.pack_forget()
            self.row_exe.pack_forget()
            self.row_keyword.pack_forget()
            self.row_browser.pack_forget()
            self.row_path.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            if self.entry is None:
                self._apply_builtin_preset()
        elif target_type == "browser_tab":
            self.row_builtin.pack_forget()
            self.row_name.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            self.row_exe.pack_forget()
            self.row_keyword.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            self.row_browser.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            self.row_path.pack_forget()
            if self.entry is None:
                self.launch_var.set(False)
        else:
            self.row_builtin.pack_forget()
            self.row_name.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            if target_type == "uwp":
                self.row_keyword.pack(fill=tk.X, pady=(0, scaled(self, 10)))
                self.row_path.pack_forget()
                self.row_exe.pack_forget()
            else:
                self.row_keyword.pack(fill=tk.X, pady=(0, scaled(self, 10)))
                self.row_path.pack(fill=tk.X, pady=(0, scaled(self, 10)))
                self._refresh_exe_row()
            self.row_browser.pack_forget()
            if self.entry is None:
                self.launch_var.set(True)

    def _on_ok(self):
        hotkey = self.hotkey_var.get().strip()
        if not hotkey:
            messagebox.showwarning("提示", "请录制快捷键", parent=self)
            return

        target_type = self._selected_target_type()
        if target_type == "browser_tab":
            keyword = self.keyword_var.get().strip()
            if not keyword:
                messagebox.showwarning("提示", "浏览器 App 必须填写标题关键词", parent=self)
                return
            self.result = {
                "app": "web_app",
                "name": self.name_var.get().strip(),
                "target_type": target_type,
                "tray_aware": self.tray_var.get(),
                "multi_window": self.multi_window_var.get(),
                "hotkey": hotkey,
                "enabled": self.enabled_var.get(),
                "launch_if_not_running": False,
                "install_path": "",
                "exe_name": self.BROWSER_MAP[self.browser_var.get()],
                "title_keyword": keyword,
            }
            self.destroy()
            return

        app = self._selected_builtin_app() if target_type == "builtin" else "generic"
        self.result = {
            "app": app,
            "name": self.name_var.get().strip() if app == "generic" else EntryDialog.APP_NAMES.get(app, app),
            "target_type": target_type,
            "tray_aware": self.tray_var.get(),
            "multi_window": self.multi_window_var.get(),
            "hotkey": hotkey,
            "enabled": self.enabled_var.get(),
            "launch_if_not_running": self.launch_var.get(),
            "install_path": self._display_path(self.path_var.get().strip()),
        }
        if app == "generic":
            exe_name = self.exe_var.get().strip()
            install_path = self.path_var.get().strip()
            display_name = self.name_var.get().strip()
            keyword = self.keyword_var.get().strip()
            if not exe_name and not install_path and not display_name and not keyword:
                messagebox.showwarning("提示", "请至少填写应用名、标题关键词、安装路径或进程名", parent=self)
                return
            if install_path:
                self.result["exe_name"] = Path(install_path).name
            elif exe_name:
                self.result["exe_name"] = exe_name
            self.result["title_keyword"] = keyword

        self.destroy()


class AddMappingDialog(_BindXDialog):
    def __init__(self, parent, mapping_type="keyboard"):
        super().__init__(parent, "映射设置", 660, 430)
        self.mapping_type = mapping_type

        self.type_var = tk.StringVar(value=mapping_type)
        self.trigger_var = tk.StringVar(value="")
        self.button_var = tk.StringVar(value="")
        self.output_var = tk.StringVar(value="")
        self.desc_var = tk.StringVar(value="")

        row = self._row()
        self._label(row, "类型：").pack(side=tk.LEFT)
        self.type_combo = ctk.CTkOptionMenu(row, values=["keyboard", "mouse"], variable=self.type_var, command=self._on_type_changed, width=scaled(self, 180), font=_dialog_font(self))
        self.type_combo.pack(side=tk.LEFT)

        self.trigger_frame = self._row()
        self._label(self.trigger_frame, "触发键：").pack(side=tk.LEFT)
        _readonly_entry(self.trigger_frame, self.trigger_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(self.trigger_frame, text="录制", command=self._capture_trigger, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        self.mouse_frame = self._row()
        self._label(self.mouse_frame, "鼠标按键：").pack(side=tk.LEFT)
        self.button_combo = ctk.CTkOptionMenu(self.mouse_frame, values=["left", "right", "middle", "x1", "x2"], variable=self.button_var, width=scaled(self, 180), font=_dialog_font(self))
        self.button_combo.pack(side=tk.LEFT)
        ctk.CTkButton(self.mouse_frame, text="录制", command=self._capture_mouse, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        row = self._row()
        self._label(row, "输出键：").pack(side=tk.LEFT)
        _readonly_entry(row, self.output_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ctk.CTkButton(row, text="录制", command=self._capture_output, width=scaled(self, 82), font=_dialog_font(self)).pack(side=tk.LEFT, padx=(scaled(self, 8), 0))

        row = self._row()
        self._label(row, "描述：").pack(side=tk.LEFT)
        ctk.CTkEntry(row, textvariable=self.desc_var, font=_dialog_font(self)).pack(side=tk.LEFT, fill=tk.X, expand=True)

        btns = self._button_row()
        ctk.CTkButton(btns, text="确认", command=self._on_ok, width=scaled(self, 92), font=_dialog_font(self)).pack(side=tk.RIGHT, padx=(scaled(self, 8), 0))
        self._secondary_button(btns, "取消", self._on_cancel, width=92).pack(side=tk.RIGHT)

        self._on_type_changed()
        self._center_on_parent()

    def _on_type_changed(self, _value=None):
        self.mapping_type = self.type_var.get()
        if self.mapping_type == "keyboard":
            self.trigger_frame.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            self.mouse_frame.pack_forget()
        else:
            self.trigger_frame.pack_forget()
            self.mouse_frame.pack(fill=tk.X, pady=(0, scaled(self, 10)))
            if not self.button_var.get():
                self.button_var.set("x1")

    def _capture_trigger(self):
        dlg = KeyCaptureDialog(self, "录制触发键")
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.trigger_var.set(" + ".join(dlg.result))

    def _capture_output(self):
        dlg = KeyCaptureDialog(self, "录制输出键")
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.output_var.set(" + ".join(dlg.result))

    def _capture_mouse(self):
        dlg = MouseCaptureDialog(self, "录制鼠标按键")
        self.wait_window(dlg)
        if getattr(dlg, "result", None):
            self.button_var.set(dlg.result)

    def _on_ok(self):
        trigger = self.trigger_var.get().strip()
        output = self.output_var.get().strip()
        if self.mapping_type == "mouse":
            button = self.button_var.get().strip()
            if not button or not output:
                messagebox.showwarning("提示", "请录制按键", parent=self)
                return
        else:
            if not trigger or not output:
                messagebox.showwarning("提示", "请录制按键", parent=self)
                return

        self.result = {
            "trigger": [k.strip() for k in trigger.split("+") if k.strip()],
            "output": [k.strip() for k in output.split("+") if k.strip()],
            "description": self.desc_var.get().strip() or f"{trigger if self.mapping_type == 'keyboard' else 'Mouse ' + self.button_var.get()} -> {output}",
            "enabled": True,
        }
        if self.mapping_type == "mouse":
            self.result["button"] = self.button_var.get()

        self.destroy()


