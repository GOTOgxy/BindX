# -*- coding: utf-8 -*-
"""BindX UI: 主应用入口（BindXApp）。"""

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
        hook_state = "运行中" if self.controller.trigger_engine.running else "未运行"
        self.sidebar_status.configure(
            text=f"Hook: {hook_state}\n热键: {'开' if self.controller.hk_running else '关'}\n鼠标: {'开' if self.controller.mc_running else '关'}"
        )
        self.after(500, self._refresh_status_loop)

    def _show_tray_menu(self):
        current_menu_font = menu_font(self)
        menu = tk.Menu(self, tearoff=0, font=current_menu_font)
        menu.configure(font=current_menu_font)
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
        menu.add_command(label="重置窗口大小", command=self._reset_window_layout)
        menu.add_command(label="重新安装 Hook", command=self._tray_reinstall_hooks)
        menu.add_command(label="导出配置", command=lambda: self.overview_tab.export_config())
        menu.add_command(label="导入配置", command=lambda: self.overview_tab.import_config())
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

