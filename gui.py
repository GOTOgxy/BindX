# -*- coding: utf-8 -*-

"""BindX 统一 UI。

单进程、单托盘、单 mainloop，内含三页 Notebook：
  - 总览：双引擎运行状态 + 启停按钮 + 全局动作
  - Hot Key：复刻 app_hotkey_manager/gui.py 的条目管理 Treeview，复用 EntryDialog
  - Mouse：复刻 mouse_click/gui.py 的映射管理 Treeview，复用 AddMappingDialog

对话框类经 config_proxy 从子项目模块（bindx_hk_gui / bindx_mc_gui）取得，
子项目源码零修改。
"""

import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox

import config_proxy
from tray import TrayIcon

_hk_gui = config_proxy.hk_gui_module()
_mc_gui = config_proxy.mc_gui_module()

EntryDialog = _hk_gui.EntryDialog
HotkeyCaptureDialog = _hk_gui.HotkeyCaptureDialog
AddMappingDialog = _mc_gui.AddMappingDialog


class OverviewTab(ttk.Frame):
    def __init__(self, parent, controller, app):
        super().__init__(parent, padding=15)
        self.controller = controller
        self.app = app

        ttk.Label(self, text="BindX 引擎总览", font=("", 14, "bold")).pack(anchor=tk.W, pady=(0, 15))

        cards = ttk.Frame(self)
        cards.pack(fill=tk.X)
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)

        self.hk_card = ttk.LabelFrame(cards, text="Hot Key 引擎", padding=15)
        self.hk_card.grid(row=0, column=0, sticky=tk.NSEW, padx=(0, 8))
        self.hk_status = ttk.Label(self.hk_card, text="运行中 ●", font=("", 11))
        self.hk_status.pack(anchor=tk.W, pady=(0, 10))
        btns_hk = ttk.Frame(self.hk_card)
        btns_hk.pack(fill=tk.X)
        ttk.Button(btns_hk, text="启动", command=self._start_hk, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btns_hk, text="停止", command=self._stop_hk, width=8).pack(side=tk.LEFT)

        self.mc_card = ttk.LabelFrame(cards, text="Mouse 引擎", padding=15)
        self.mc_card.grid(row=0, column=1, sticky=tk.NSEW)
        self.mc_status = ttk.Label(self.mc_card, text="运行中 ●", font=("", 11))
        self.mc_status.pack(anchor=tk.W, pady=(0, 10))
        btns_mc = ttk.Frame(self.mc_card)
        btns_mc.pack(fill=tk.X)
        ttk.Button(btns_mc, text="启动", command=self._start_mc, width=8).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(btns_mc, text="停止", command=self._stop_mc, width=8).pack(side=tk.LEFT)

        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=20)

        actions = ttk.LabelFrame(self, text="全局动作", padding=15)
        actions.pack(fill=tk.X)
        ttk.Button(actions, text="全部启动", command=self._start_all, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="全部停止", command=self._stop_all, width=12).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(actions, text="退出 BindX", command=self.app._quit_app, width=12).pack(side=tk.RIGHT)

        info = ttk.Frame(self, padding=(0, 15, 0, 0))
        info.pack(fill=tk.X)
        ttk.Label(
            info,
            text='提示：关闭主窗口将最小化到托盘；如需退出请点「退出 BindX」或托盘菜单「退出」。\n'
                 'Hot Key 自热键 CTRL+ALT+H 可切换本窗口显隐。',
            foreground="gray",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

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
        self.hk_status.config(text="运行中 ●" if self.controller.hk_running else "已停止 ○")
        self.mc_status.config(text="运行中 ●" if self.controller.mc_running else "已停止 ○")


class HotKeyTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.manager = controller.hotkey_manager
        self._create_ui()
        self._refresh_list()

    def _create_ui(self):
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="添加", command=self._add_entry, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="删除", command=self._delete_entry, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="编辑", command=self._edit_entry, width=8).pack(side=tk.LEFT, padx=2)

        list_frame = ttk.Frame(self, padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("app", "hotkey", "enabled", "launch", "path")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("app", text="应用")
        self.tree.heading("hotkey", text="快捷键")
        self.tree.heading("enabled", text="启用")
        self.tree.heading("launch", text="启动未运行")
        self.tree.heading("path", text="安装路径")
        self.tree.column("app", width=120, minwidth=80)
        self.tree.column("hotkey", width=120, minwidth=100)
        self.tree.column("enabled", width=60, minwidth=50, anchor=tk.CENTER)
        self.tree.column("launch", width=100, minwidth=80, anchor=tk.CENTER)
        self.tree.column("path", width=240, minwidth=100)

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

        status_frame = ttk.Frame(self, padding=(5, 2))
        status_frame.pack(fill=tk.X)
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)

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
            launch = "✓" if entry["config_entry"].get("launch_if_not_running", False) else "✗"
            path = entry["config_entry"].get("install_path", "")
            self.tree.insert("", tk.END, iid=str(entry["id"]),
                             values=(app_name, hotkey, enabled, launch, path))
        count = len(self.manager.entries)
        self.status_label.config(text=f"共 {count} 个条目")

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
        elif column == "#4":
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


class MouseTab(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        self.config = controller.mc_config
        self._create_ui()
        self._refresh_list()

    def _create_ui(self):
        toolbar = ttk.Frame(self, padding=5)
        toolbar.pack(fill=tk.X)

        ttk.Button(toolbar, text="添加映射", command=self._add_mapping, width=12).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="删除", command=self._delete_entry, width=8).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="编辑", command=self._edit_entry, width=8).pack(side=tk.LEFT, padx=2)

        list_frame = ttk.Frame(self, padding=5)
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

        status_frame = ttk.Frame(self, padding=(5, 2))
        status_frame.pack(fill=tk.X)
        self.status_label = ttk.Label(status_frame, text="就绪")
        self.status_label.pack(side=tk.LEFT)

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
        self.status_label.config(text=f"共 {total} 个映射")

    def _add_mapping(self):
        dlg = AddMappingDialog(self, "keyboard")
        self.wait_window(dlg)
        if dlg.result:
            if dlg.mapping_type == "mouse":
                mapping = {
                    "button": dlg.result["button"],
                    "output": dlg.result["output"],
                    "description": dlg.result.get("description", ""),
                    "enabled": dlg.result.get("enabled", True),
                }
                self.config.setdefault("mouse_mappings", []).append(mapping)
            else:
                self.config.setdefault("mappings", []).append(dlg.result)
            self._save_and_restart()

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
            if dlg.mapping_type == "mouse":
                self.config["mouse_mappings"][idx] = {
                    "button": dlg.result["button"],
                    "output": dlg.result["output"],
                    "description": dlg.result.get("description", ""),
                    "enabled": dlg.result.get("enabled", True),
                }
            else:
                self.config["mappings"][idx] = dlg.result
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


class BindXApp(tk.Tk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller

        self.title("BindX")
        self.geometry("900x600")
        self.minsize(760, 450)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.overview_tab = OverviewTab(self.notebook, controller, self)
        self.hotkey_tab = HotKeyTab(self.notebook, controller)
        self.mouse_tab = MouseTab(self.notebook, controller)
        self.notebook.add(self.overview_tab, text="总览")
        self.notebook.add(self.hotkey_tab, text="Hot Key")
        self.notebook.add(self.mouse_tab, text="Mouse")

        self.tray = TrayIcon(on_show=self._show_window, on_menu=self._show_tray_menu)

        self.controller.set_hotkey_self_callback(self.toggle_ui)

        self._poll_tray()
        self._poll_hotkeys()
        self._refresh_status_loop()

    def _poll_tray(self):
        self.tray.poll()
        self.after(10, self._poll_tray)

    def _poll_hotkeys(self):
        self.controller.process_hotkeys()
        self.after(20, self._poll_hotkeys)

    def _refresh_status_loop(self):
        self.overview_tab.refresh()
        self.after(500, self._refresh_status_loop)

    def _show_tray_menu(self):
        menu = tk.Menu(self, tearoff=0)
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
