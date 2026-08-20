# -*- coding: utf-8 -*-
"""BindX UI: 主窗口页签（总览 / Hot Key / Mouse）。"""

import json
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from .. import shortcut_manager
from .entry_dialogs import AddMappingDialog, EntryDialog
from .inspector import InputInspectorWindow
from .theme import (BUTTON_DEFAULT_FG, BUTTON_DEFAULT_HOVER,
                    menu_font, scaled, ui_font)

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
        ctk.CTkButton(action_row, text="重置窗口", command=self.app._reset_window_layout, width=96, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(action_row, text="导出配置", command=self.export_config, width=96, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(action_row, text="导入配置", command=self.import_config, width=96, fg_color="#52525b", hover_color="#3f3f46").pack(side=tk.LEFT, padx=(0, 8))
        ctk.CTkButton(action_row, text="退出 BindX", command=self.app._quit_app, width=104, fg_color="#991b1b", hover_color="#7f1d1d").pack(side=tk.RIGHT)

        font_row = ctk.CTkFrame(actions, fg_color="transparent")
        font_row.pack(fill=tk.X, padx=16, pady=(0, 16))
        ctk.CTkLabel(font_row, text="字体大小", font=ui_font(self, 14)).pack(side=tk.LEFT, padx=(0, 12))
        self.font_preset_menu = ctk.CTkOptionMenu(
            font_row,
            values=["紧凑", "稍小", "常规", "特大", "超大"],
            command=self.app._change_font_preset,
            width=120,
            font=ui_font(self, 14),
        )
        self.font_preset_menu.pack(side=tk.LEFT)
        self.font_preset_menu.set(self.app._get_font_preset())

        startup_row = ctk.CTkFrame(actions, fg_color="transparent")
        startup_row.pack(fill=tk.X, padx=16, pady=(0, 16))
        ctk.CTkLabel(startup_row, text="开机启动", font=ui_font(self, 14)).pack(side=tk.LEFT, padx=(0, 12))
        self.autostart_var = tk.BooleanVar(value=self.controller.get_autostart_enabled())
        self.autostart_switch = ctk.CTkSwitch(
            startup_row,
            text="登录后后台运行",
            variable=self.autostart_var,
            onvalue=True,
            offvalue=False,
            command=self._toggle_autostart,
            font=ui_font(self, 14),
        )
        self.autostart_switch.pack(side=tk.LEFT)

        shortcut_row = ctk.CTkFrame(actions, fg_color="transparent")
        shortcut_row.pack(fill=tk.X, padx=16, pady=(0, 16))
        ctk.CTkLabel(shortcut_row, text="快捷方式", font=ui_font(self, 14)).pack(side=tk.LEFT, padx=(0, 12))
        self.desktop_shortcut_btn = ctk.CTkButton(shortcut_row, text="创建桌面图标", command=self._toggle_desktop_shortcut, width=128)
        self.desktop_shortcut_btn.pack(side=tk.LEFT, padx=(0, 8))
        self.start_menu_shortcut_btn = ctk.CTkButton(
            shortcut_row,
            text="创建开始菜单图标",
            command=self._toggle_start_menu_shortcut,
            width=152,
        )
        self.start_menu_shortcut_btn.pack(side=tk.LEFT)

        self.refresh_shortcut_buttons()
        self.refresh_status()

    def _start_hk(self):
        self.controller.start_hotkey()
        self.refresh_status()

    def _stop_hk(self):
        self.controller.stop_hotkey()
        self.refresh_status()

    def _start_mc(self):
        self.controller.start_mouse()
        self.refresh_status()

    def _stop_mc(self):
        self.controller.stop_mouse()
        self.refresh_status()

    def _start_all(self):
        self.controller.start_hotkey()
        self.controller.start_mouse()
        self.refresh_status()

    def _stop_all(self):
        self.controller.stop_hotkey()
        self.controller.stop_mouse()
        self.refresh_status()

    def _toggle_autostart(self):
        desired = bool(self.autostart_var.get())
        success, error = self.controller.set_autostart_enabled(desired)
        if not success:
            self.autostart_var.set(self.controller.get_autostart_enabled())
            messagebox.showerror("开机启动", f"设置开机启动失败：\n{error}")
            return
        self.autostart_var.set(self.controller.get_autostart_enabled())

    def _toggle_desktop_shortcut(self):
        exists = shortcut_manager.desktop_shortcut_exists()
        try:
            if exists:
                shortcut_manager.remove_desktop_shortcut()
            else:
                shortcut_path = shortcut_manager.create_desktop_shortcut()
        except OSError as exc:
            action = "删除桌面图标" if exists else "创建桌面图标"
            messagebox.showerror(action, f"操作失败：\n{exc}")
            return
        self.refresh_shortcut_buttons()
        if exists:
            messagebox.showinfo("删除桌面图标", "桌面快捷方式已删除。")
        else:
            messagebox.showinfo("创建桌面图标", f"桌面快捷方式已创建：\n{shortcut_path}")

    def _toggle_start_menu_shortcut(self):
        exists = shortcut_manager.start_menu_shortcut_exists()
        try:
            if exists:
                shortcut_manager.remove_start_menu_shortcut()
            else:
                shortcut_path = shortcut_manager.create_start_menu_shortcut()
        except OSError as exc:
            action = "删除开始菜单图标" if exists else "创建开始菜单图标"
            messagebox.showerror(action, f"操作失败：\n{exc}")
            return
        self.refresh_shortcut_buttons()
        if exists:
            messagebox.showinfo("删除开始菜单图标", "开始菜单快捷方式已删除。")
        else:
            messagebox.showinfo(
                "创建开始菜单图标",
                f"开始菜单快捷方式已创建：\n{shortcut_path}\n\n现在可以在开始菜单里找到 BindX，再手动固定。",
            )

    def refresh_shortcut_buttons(self):
        desktop_exists = shortcut_manager.desktop_shortcut_exists()
        start_menu_exists = shortcut_manager.start_menu_shortcut_exists()
        self.desktop_shortcut_btn.configure(
            text="删除桌面图标" if desktop_exists else "创建桌面图标",
            fg_color=BUTTON_DEFAULT_FG if desktop_exists else "#52525b",
            hover_color=BUTTON_DEFAULT_HOVER if desktop_exists else "#3f3f46",
        )
        self.start_menu_shortcut_btn.configure(
            text="删除开始菜单图标" if start_menu_exists else "创建开始菜单图标",
            fg_color=BUTTON_DEFAULT_FG if start_menu_exists else "#52525b",
            hover_color=BUTTON_DEFAULT_HOVER if start_menu_exists else "#3f3f46",
        )

    def refresh_status(self):
        current_autostart = bool(self.controller.app_state.get("autostart_enabled", False))
        if self.autostart_var.get() != current_autostart:
            self.autostart_var.set(current_autostart)
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

    def export_config(self):
        from .. import config_store

        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile="bindx_config.json",
            title="导出配置",
        )
        if not path:
            return
        try:
            cfg = config_store.load_root_config()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("导出失败", str(e), parent=self)
            return
        messagebox.showinfo("导出成功", f"配置已导出到：\n{path}", parent=self)

    def import_config(self):
        from .. import config_store

        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")], title="导入配置")
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            messagebox.showerror("导入失败", f"无法读取配置文件：\n{e}", parent=self)
            return
        if not config_store._looks_like_centralized_config(raw):
            messagebox.showerror("导入失败", "文件格式无效，不是合法的 BindX 配置。", parent=self)
            return
        try:
            config_store.save_root_config(raw)
            self.controller.reload_all_config()
            self.refresh_status()
            self.app.hotkey_tab._refresh_list()
            self.app.mouse_tab.reload_config()
        except Exception as e:
            messagebox.showerror("导入失败", str(e), parent=self)
            return
        messagebox.showinfo("导入成功", "配置已导入，热键与鼠标映射已重新加载。", parent=self)



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

        columns = ("target", "app", "hotkey", "enabled", "registered", "launch", "path")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("target", text="类型")
        self.tree.heading("app", text="应用")
        self.tree.heading("hotkey", text="快捷键")
        self.tree.heading("enabled", text="启用")
        self.tree.heading("registered", text="注册")
        self.tree.heading("launch", text="热键启动")
        self.tree.heading("path", text="安装路径")
        self.tree.column("target", width=150, minwidth=110)
        self.tree.column("app", width=140, minwidth=90)
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

        self.context_menu = tk.Menu(self, tearoff=0, font=menu_font(self))
        self.context_menu.add_command(label="编辑", command=self._edit_entry)
        self.context_menu.add_command(label="启用/禁用", command=self._toggle_entry)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_entry)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill=tk.X)
        self.status_label = ctk.CTkLabel(status_frame, text="就绪", text_color="#71717a", font=ui_font(self, 14))
        self.status_label.pack(side=tk.LEFT, padx=2, pady=(8, 0))

    def refresh_native_menu_style(self):
        self.context_menu.configure(font=menu_font(self))

    def _refresh_list(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for entry in self.manager.entries:
            config_entry = entry["config_entry"]
            app_id = config_entry.get("app", "")
            target_type = config_entry.get("target_type")
            if target_type not in EntryDialog.TARGET_TYPE_IDS:
                if app_id == "web_app":
                    target_type = "browser_tab"
                elif target_type == "tray":
                    target_type = "win32"
                elif target_type == "uwp_multi":
                    target_type = "uwp"
                else:
                    target_type = EntryDialog.BUILTIN_TARGET_TYPES.get(app_id, "win32")
            if app_id in EntryDialog.BUILTIN_APP_IDS:
                target_type = "builtin"
            target_name = EntryDialog.TARGET_TYPE_NAMES.get(target_type, "Win32 窗口")
            if config_entry.get("tray_aware") or config_entry.get("target_type") == "tray":
                target_name = f"{target_name} + 托盘"
            if config_entry.get("multi_window") or config_entry.get("target_type") == "uwp_multi":
                target_name = f"{target_name} + 多窗口"
            display_name = config_entry.get("name", "").strip()
            if app_id == "generic":
                exe_name = config_entry.get("exe_name", "")
                if not exe_name:
                    install_path = config_entry.get("install_path", "")
                    if install_path:
                        exe_name = Path(install_path).name
                app_name = display_name or exe_name or config_entry.get("title_keyword", "") or "通用应用"
            elif app_id == "web_app":
                exe_name = config_entry.get("exe_name", "")
                browser = "Chrome" if exe_name == "chrome.exe" else "Edge"
                keyword = config_entry.get("title_keyword", "")
                app_name = display_name or (f"{browser} | {keyword}" if keyword else browser)
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
            launch = "✓" if config_entry.get("launch_if_not_running", False) else "✗"
            path = EntryDialog._display_path(config_entry.get("install_path", ""))
            self.tree.insert("", tk.END, iid=str(entry["id"]),
                             values=(target_name, app_name, hotkey, enabled, registered, launch, path))
        count = len(self.manager.entries)
        self.status_label.configure(text=f"共 {count} 个条目")

    def _warn_hotkey_conflict(self, entry, exclude_id=None):
        hotkey = (entry.get("hotkey") or "").replace(" ", "").upper()
        if not hotkey:
            return
        conflicts = []
        for other in self.manager.entries:
            other_id = other.get("id")
            if exclude_id is not None and other_id == exclude_id:
                continue
            other_hotkey = (other.get("hotkey") or "").replace(" ", "").upper()
            if other_hotkey == hotkey:
                ce = other.get("config_entry", {})
                conflicts.append(f"• {ce.get('name') or ce.get('app')}（ID {other_id}）")
        if conflicts:
            messagebox.showwarning(
                "热键冲突提示",
                "以下条目的快捷键与刚保存的条目相同：\n" + "\n".join(conflicts)
                + "\n\n保存已生效，但系统只会触发其中一个，请自行调整。",
                parent=self,
            )

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
                    name=data.get("name", ""),
                    target_type=data.get("target_type", ""),
                    tray_aware=data.get("tray_aware", False),
                    multi_window=data.get("multi_window", False),
                )
            except ValueError as e:
                messagebox.showerror("错误", str(e), parent=self)
                return
            if entry:
                self._warn_hotkey_conflict(entry)
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
                    name=data.get("name", ""),
                    target_type=data.get("target_type", ""),
                    tray_aware=data.get("tray_aware", False),
                    multi_window=data.get("multi_window", False),
                )
            except ValueError as e:
                messagebox.showerror("错误", str(e), parent=self)
                return
            self._warn_hotkey_conflict(self.manager.entry_map.get(entry_id) or {}, exclude_id=entry_id)
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
        if column == "#4":
            self.manager.toggle_entry(entry_id)
            self._refresh_list()
            self.after(100, self._refresh_list)
        elif column == "#6":
            old_val = entry["config_entry"].get("launch_if_not_running", False)
            self.manager.set_launch_if_not_running(entry_id, not old_val)
            self._refresh_list()
        else:
            self._edit_entry()

    def _on_right_click(self, event):
        item = self.tree.identify_row(event.y)
        if item:
            self.tree.selection_set(item)
            self.context_menu.tk_popup(event.x_root, event.y_root)

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

        self.context_menu = tk.Menu(self, tearoff=0, font=menu_font(self))
        self.context_menu.add_command(label="编辑", command=self._edit_entry)
        self.context_menu.add_command(label="启用/禁用", command=self._toggle_enabled)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="删除", command=self._delete_entry)

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.pack(fill=tk.X)
        self.status_label = ctk.CTkLabel(status_frame, text="就绪", text_color="#71717a", font=ui_font(self, 14))
        self.status_label.pack(side=tk.LEFT, padx=2, pady=(8, 0))

    def refresh_native_menu_style(self):
        self.context_menu.configure(font=menu_font(self))

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
        win = InputInspectorWindow(self, self.controller)
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


