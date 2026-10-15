# -*- coding: utf-8 -*-
"""BindX UI: 主应用入口（BindXApp）。"""

import os
import queue
import threading
import tkinter as tk

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from .tabs import HotKeyTab, MouseTab, OverviewTab
from .theme import (FONT_PRESET_TABLE_SIZE, _clamp, _compute_ui_scale,
                    _force_toplevel_foreground, _parse_window_size, menu_font,
                    scaled, ui_font)
from ..tray import TrayIcon

class BindXApp(ctk.CTk):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self._config_sync_busy = False
        self._code_sync_busy = False
        self._ui_queue = queue.Queue()
        self._default_geometry = None
        self.ui_scale = _compute_ui_scale(self)
        ctk.set_widget_scaling(self.ui_scale)
        ctk.set_window_scaling(self.ui_scale)
        self.tk.call("tk", "scaling", self.ui_scale)

        self.title("BindX")
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        logical_screen_w = max(1, int(round(screen_w / self.ui_scale)))
        logical_screen_h = max(1, int(round(screen_h / self.ui_scale)))
        max_w = max(1, int(logical_screen_w * 0.92))
        max_h = max(1, int(logical_screen_h * 0.88))
        default_w = min(max(980, int(logical_screen_w * 0.72)), max_w)
        default_h = min(max(640, int(logical_screen_h * 0.72)), max_h)
        self._window_min_w = min(860, max_w)
        self._window_min_h = min(540, max_h)
        self._window_max_w = max_w
        self._window_max_h = max_h
        self._default_geometry = f"{default_w}x{default_h}"
        self.geometry(self._default_geometry)
        self.minsize(self._window_min_w, self._window_min_h)
        self.configure(fg_color=("#f4f4f5", "#18181b"))
        self._restore_window_state()

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
        self._poll_ui_queue()
        self._resize_after_id = None
        self._window_state_after_id = None
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
        return FONT_PRESET_TABLE_SIZE.get(self._get_font_preset(), FONT_PRESET_TABLE_SIZE["常规"])

    def _apply_adaptive_table_style(self):
        base_size = self._table_font_size()
        font_size = scaled(self, base_size)
        rowheight = scaled(self, int(base_size * 3.0))
        style = ttk.Style(self)
        style.configure("Treeview", font=("Microsoft YaHei UI", font_size), rowheight=rowheight)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", font_size + scaled(self, 1), "bold"))

    def _on_window_configure(self, event):
        if event.widget is not self:
            return
        if self._resize_after_id is not None:
            self.after_cancel(self._resize_after_id)
        self._resize_after_id = self.after(120, self._apply_adaptive_table_style)
        if self._window_state_after_id is not None:
            self.after_cancel(self._window_state_after_id)
        self._window_state_after_id = self.after(240, self._persist_window_state)

    def _restore_window_state(self):
        size = self._normalize_window_size(self.controller.app_state.get("window_size"))
        if size:
            try:
                self.geometry(size)
            except tk.TclError:
                self.geometry(self._default_geometry)
        if self.controller.app_state.get("window_zoomed"):
            try:
                self.state("zoomed")
            except tk.TclError:
                pass

    def _persist_window_state(self):
        self._window_state_after_id = None
        state = self.state()
        zoomed = state == "zoomed"
        if state == "withdrawn":
            return
        size = self._current_window_size()
        if zoomed:
            size = self.controller.app_state.get("window_size") or self._default_geometry
        self.controller.save_window_state(size=size, zoomed=zoomed)

    def _reset_window_layout(self):
        self.deiconify()
        try:
            self.state("normal")
        except tk.TclError:
            pass
        self.geometry(self._default_geometry)
        self.update_idletasks()
        self.controller.save_window_state(size=self._default_geometry, zoomed=False)
        self._apply_adaptive_table_style()
        self.lift()
        self.focus_force()

    def _normalize_window_size(self, size):
        parsed = _parse_window_size(size)
        if not parsed:
            return None
        width, height = parsed
        width = _clamp(width, self._window_min_w, self._window_max_w)
        height = _clamp(height, self._window_min_h, self._window_max_h)
        return f"{width}x{height}"

    def _current_window_size(self):
        normalized = self._normalize_window_size(self.geometry().split("+", 1)[0])
        return normalized or self._default_geometry

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
        self.overview_tab.refresh_status()
        hook_state = "运行中" if self.controller.trigger_engine.running else "未运行(无需钩子)"
        self.sidebar_status.configure(
            text=f"Hook: {hook_state}\n热键: {'开' if self.controller.hk_running else '关'}\n鼠标: {'开' if self.controller.mc_running else '关'}"
        )
        self.after(500, self._refresh_status_loop)

    def _poll_ui_queue(self):
        try:
            while True:
                item = self._ui_queue.get_nowait()
                if item[0] == "config_sync_finish":
                    _, action, result, error = item
                    self._finish_config_sync(action, result, error)
                elif item[0] == "config_sync_status":
                    _, info, error = item
                    self.overview_tab._finish_sync_status(info, error)
                elif item[0] == "code_sync_finish":
                    _, action, result, error = item
                    self._finish_code_sync(action, result, error)
                elif item[0] == "code_sync_status":
                    _, info, error = item
                    self.overview_tab._finish_code_status(info, error)
        except queue.Empty:
            pass
        self.after(10, self._poll_ui_queue)

    def _upload_config_to_git(self):
        self._start_config_sync("upload")

    def _download_config_from_git(self):
        self._start_config_sync("download")

    def _start_config_sync(self, action):
        if self._config_sync_busy:
            return
        self._config_sync_busy = True
        tab = self.overview_tab
        tab.set_sync_buttons_busy(True)
        tab.set_sync_status_text("同步中…（仅同步配置文件，不影响软件其他内容）")

        def worker():
            from .. import config_sync
            try:
                if action == "upload":
                    result = config_sync.upload_config()
                else:
                    result = config_sync.download_config()
            except Exception as exc:
                self._ui_queue.put(("config_sync_finish", action, None, exc))
            else:
                self._ui_queue.put(("config_sync_finish", action, result, None))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_config_sync(self, action, result, error):
        self._config_sync_busy = False
        tab = self.overview_tab
        tab.set_sync_buttons_busy(False)
        label = "上传配置" if action == "upload" else "拉取配置"
        if error is not None:
            tab.set_sync_status_text("同步状态：%s失败" % label)
            messagebox.showerror(label, "操作失败：\n%s" % error, parent=self)
            tab.refresh_sync_status(force=True)
            return
        if action == "download":
            try:
                tab.apply_config_reload()
            except Exception as exc:
                messagebox.showerror(label, "配置文件已更新，但引擎重载失败：\n%s" % exc, parent=self)
                return
        tab.refresh_sync_status(force=True)
        if action == "upload":
            messagebox.showinfo(
                label,
                "本地配置已推送到 Git 远端（config 分支）。\n现在可以在另一台电脑上按「拉取配置」还原。",
                parent=self,
            )
        else:
            sha = (result or {}).get("sha", "")[:7]
            messagebox.showinfo(label, "远端配置已拉取到本地，热键与鼠标映射已重新加载。\n同步提交：%s" % sha, parent=self)


    def _pull_code_from_git(self):
        self._start_code_sync("pull")

    def _push_code_to_git(self):
        self._start_code_sync("push")

    def _start_code_sync(self, action):
        if self._code_sync_busy:
            return
        self._code_sync_busy = True
        tab = self.overview_tab
        tab.set_code_buttons_busy(True)
        if action == "pull":
            tab.set_code_status_text("正在下载代码，请稍候……")
        else:
            tab.set_code_status_text("正在上传代码：先提交本地改动，再推送到远端……")

        def worker():
            from .. import code_sync
            try:
                if action == "pull":
                    result = code_sync.pull_code()
                else:
                    result = code_sync.push_code()
            except Exception as exc:
                self._ui_queue.put(("code_sync_finish", action, None, exc))
            else:
                self._ui_queue.put(("code_sync_finish", action, result, None))

        threading.Thread(target=worker, daemon=True).start()

    def _finish_code_sync(self, action, result, error):
        self._code_sync_busy = False
        tab = self.overview_tab
        tab.set_code_buttons_busy(False)
        label = "下载代码" if action == "pull" else "上传代码"
        if error is not None:
            tab.set_code_status_text("代码状态：%s失败" % label)
            messagebox.showerror(label, "操作失败：\n%s" % error, parent=self)
            tab.refresh_code_status(force=True)
            return
        if action == "pull":
            if result.get("updated"):
                count = len(result.get("files") or [])
                messagebox.showinfo(
                    label,
                    "已拉到最新代码（%s），共更新 %d 个文件。\n如果代码有变化，请按「重新启动」让新代码生效。"
                    % (result["sha"][:7], count),
                    parent=self,
                )
            else:
                messagebox.showinfo(
                    label, "本地代码已经是最新的（%s）。" % result["sha"][:7], parent=self
                )
        else:
            if result.get("committed"):
                messagebox.showinfo(
                    label,
                    "本地改动已提交并推送到 Git 远端（main 分支）。\n提交：%s\n其他机器现在可以按「下载代码」获取最新代码。"
                    % result["sha"][:7],
                    parent=self,
                )
            else:
                messagebox.showinfo(
                    label,
                    "没有发现本地改动（本地配置等被忽略的文件不会上传）。",
                    parent=self,
                )
        tab.refresh_code_status(force=True)

    def _restart_app(self):
        if getattr(self, "_restarting", False):
            return
        self._restarting = True
        from .. import restart as restart_mod
        from .. import single_instance

        try:
            interpreter, script, extra = restart_mod.build_restart_command()
        except Exception as exc:
            messagebox.showerror("重新启动", "无法重启：\n%s" % exc, parent=self)
            self._restarting = False
            return
        self._persist_window_state()
        try:
            self.controller.quit()
        except Exception:
            pass
        single_instance.release()
        try:
            restart_mod.spawn_new_instance(interpreter, script, extra)
        except Exception as exc:
            messagebox.showerror(
                "重新启动",
                "新实例启动失败，当前进程保留（钩子已停止，可手动重新启用）：\n%s" % exc,
                parent=self,
            )
            self._restarting = False
            return
        try:
            self.tray.destroy()
        except Exception:
            pass
        os._exit(0)

    def _show_tray_menu(self):
        current_menu_font = menu_font(self)
        menu = tk.Menu(self, tearoff=0, font=current_menu_font)
        menu.configure(font=current_menu_font)
        hook_state = "运行中" if self.controller.trigger_engine.running else "未运行(无需钩子)"
        menu.add_command(label=f"Hook：{hook_state}", state=tk.DISABLED)
        menu.add_command(
            label=f"Keyboard：{'开' if self.controller.hk_running else '关'} / Mouse：{'开' if self.controller.mc_running else '关'}",
            state=tk.DISABLED,
        )
        menu.add_command(label=f"最近：{self.controller.trigger_engine.last_event}", state=tk.DISABLED)
        last_error = self.controller.trigger_engine.last_error
        if last_error:
            menu.add_command(label=f"错误：{str(last_error)[:60]}", state=tk.DISABLED)
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
        menu.add_command(label="重置窗口大小", command=self._reset_window_layout)
        menu.add_command(label="重新安装 Hook", command=self._tray_reinstall_hooks)
        menu.add_command(label="导出配置", command=lambda: self.overview_tab.export_config())
        menu.add_command(label="导入配置", command=lambda: self.overview_tab.import_config())
        menu.add_separator()
        menu.add_command(label="上传配置到 Git", command=self._upload_config_to_git)
        menu.add_command(label="从 Git 拉取配置", command=self._download_config_from_git)
        menu.add_command(label="下载代码", command=self._pull_code_from_git)
        menu.add_command(label="上传代码", command=self._push_code_to_git)
        menu.add_command(label="重新启动", command=self._restart_app)
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
        try:
            self.state("normal")
        except tk.TclError:
            pass
        if self.controller.app_state.get("window_zoomed"):
            try:
                self.state("zoomed")
            except tk.TclError:
                pass
        self.overview_tab.refresh_shortcut_buttons()
        self.overview_tab.refresh_status()
        if not _force_toplevel_foreground(self):
            self.after(40, lambda: _force_toplevel_foreground(self))

    def toggle_ui(self):
        if self.state() == "withdrawn" or self.state() == "iconic":
            self._show_window()
        else:
            self.withdraw()

    def _on_close(self):
        self._persist_window_state()
        self.withdraw()

    def _quit_app(self):
        self._persist_window_state()
        self.controller.quit()
        self.tray.destroy()
        self.after(100, self.destroy)

    def _get_font_preset(self):
        return self.controller.app_state.get("font_preset", "常规")

    def _change_font_preset(self, value):
        if value not in FONT_PRESET_TABLE_SIZE:
            return
        self.controller.save_font_preset(value)
        self._apply_adaptive_table_style()
        self.hotkey_tab.refresh_native_menu_style()
        self.mouse_tab.refresh_native_menu_style()

