# -*- coding: utf-8 -*-
"""BindX UI: 主应用入口（BindXApp）。"""

import os
import queue
import threading
import time
import tkinter as tk

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from .tabs import HotKeyTab, MouseTab, OverviewTab
from .scrollable import AutoHideScrollableFrame
from customtkinter.windows.widgets.scaling.scaling_tracker import \
    ScalingTracker

from .theme import (FONT_PRESET_TABLE_SIZE, _clamp, _compute_ui_scale,
                    _force_toplevel_foreground, _parse_window_size, menu_font,
                    scaled, set_label_text, ui_font)
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
        self._apply_window_bounds()
        self._app_fg_color = ("#f4f4f5", "#18181b")
        self.configure(fg_color=self._app_fg_color)
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
        # 页面宿主用原生 tk.Frame：窗口拖动时只有它（1 个 HWND）跟着变尺寸，
        # 里面的页面保持固定尺寸、拖动结束后才一次性跟随 -> resize 跟手。
        self.page_host = tk.Frame(
            self.content, bg=self._apply_appearance_mode(self._app_fg_color)
        )
        self.page_host.grid(row=0, column=0, sticky="nsew")
        self.page_host.grid_propagate(False)
        self.page_host.grid_columnconfigure(0, weight=1)
        self.page_host.grid_rowconfigure(0, weight=1)
        self._page_sizes = {}
        self._sidebar_tier = None
        self._current_page = "overview"
        # 缩放窗口的「防卡」状态机：见 _on_host_configure
        self._curtain_page = None
        self._curtain_canvas = None
        self._curtain_image = None
        self._cfg_burst = 0
        self._last_cfg_at = 0.0
        self._settle_timer = None
        self._settling = False
        # 幕布「武装」开关：启动阶段页面还没画到屏幕上，这时截图会拍到空白，
        # 所以首次铺完页面后延迟一会儿才允许升幕布（见 _settle_layout 收尾）。
        self._curtain_armed = False
        self._curtain_arm_timer = None
        self._host_size = (0, 0)
        self.page_host.bind("<Configure>", self._on_host_configure)

        self.page_containers = []
        self.overview_tab = OverviewTab(self._make_scrollable_page(), controller, self)
        self.hotkey_tab = HotKeyTab(self._make_scrollable_page(), controller)
        self.mouse_tab = MouseTab(self._make_scrollable_page(), controller)
        self.pages = {
            "overview": (self.page_containers[0], self.overview_tab),
            "hotkey": (self.page_containers[1], self.hotkey_tab),
            "mouse": (self.page_containers[2], self.mouse_tab),
        }
        for _, tab in self.pages.values():
            tab.grid(row=0, column=0, sticky="nsew")
        self._show_page("overview")

        self.tray = TrayIcon(on_show=self._show_window, on_menu=self._show_tray_menu)

        self.controller.set_hotkey_self_callback(self.toggle_ui)

        self._poll_tray()
        self._poll_hotkeys()
        self._refresh_status_loop()
        self._poll_ui_queue()
        self._window_state_after_id = None
        self._last_persisted_state = None
        self.bind("<Configure>", self._on_window_configure)

    def _window_scaling_factor(self):
        """CTk 的「逻辑 -> 物理」窗口缩放系数（系统 DPI 缩放 × set_window_scaling）。"""
        try:
            factor = ScalingTracker.get_window_scaling(self)
        except Exception:
            factor = 1.0
        return factor or 1.0

    def _apply_window_bounds(self):
        """按「物理像素」定好窗口的默认/最小/最大尺寸，再换算成 CTk 的逻辑值下发。

        本项目内部一律用 winfo_*() 的物理像素做布局计算，而 CTk 的
        geometry()/minsize()/maxsize() 收的是「逻辑值」，内部还会再乘一次窗口
        缩放系数。之前直接把物理像素当逻辑值传进去，高 DPI（200%）下窗口被
        整整放大一倍：1920x1080 的屏幕上开出 2764x1554 的窗口——
          - 超出屏幕，重绘面积翻了两番，拖动缩放自然又慢又卡；
          - 最小宽度被顶到 1360 物理像素，窗口根本压不下去。
        """
        screen_w = max(1, self.winfo_screenwidth())
        screen_h = max(1, self.winfo_screenheight())
        factor = self._window_scaling_factor()

        def to_ctk(px):
            return max(1, int(round(px / factor)))

        # 默认约占屏幕 72%；最小允许压到 ~28%（不低于 480x420 物理像素）。
        # 总览页会按可用宽度自动折行、卡片在窄窗口下自动改成单列堆叠，
        # 所以压到很窄也不会挤坏布局。
        default_w_px = max(1, min(int(screen_w * 0.72), screen_w - 40))
        default_h_px = max(1, min(int(screen_h * 0.74), screen_h - 60))
        min_w_px = max(480, int(screen_w * 0.28))
        min_h_px = max(420, min(int(screen_h * 0.45), 560))

        self._window_min_w = to_ctk(min_w_px)
        self._window_min_h = to_ctk(min_h_px)
        # 下面这两个只用于「恢复上次窗口尺寸」时的钳制，不是 Tk 的 maxsize
        self._window_max_w = to_ctk(int(screen_w * 0.92))
        self._window_max_h = to_ctk(int(screen_h * 0.88))
        self._default_geometry = "%dx%d" % (to_ctk(default_w_px), to_ctk(default_h_px))
        self.geometry(self._default_geometry)
        self.minsize(self._window_min_w, self._window_min_h)
        # maxsize 必须显式设置：CTk 在 DPI/缩放变化时会临时把 min=max=当前尺寸，
        # 1 秒后用 _set_scaled_min_max() 还原，而它只在 _max_width 非 None 时才
        # 还原 maxsize —— 不设的话窗口会被永久锁死在当时的尺寸上。
        self.maxsize(to_ctk(screen_w + 120), to_ctk(screen_h + 120))

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
        if (font_size, rowheight) == getattr(self, "_table_style_signature", None):
            return  # 样式没变：重复 configure 会让所有表格重新计算字体
        self._table_style_signature = (font_size, rowheight)
        style = ttk.Style(self)
        style.configure("Treeview", font=("Microsoft YaHei UI", font_size), rowheight=rowheight)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", font_size + scaled(self, 1), "bold"))

    def _on_window_configure(self, event):
        if event.widget is not self:
            return
        # 拖动窗口时每秒会有上百个 <Configure>：这里只保留一个防抖的
        # 「记住窗口尺寸」任务，不再做任何样式重算，resize 才跟手。
        if self._window_state_after_id is not None:
            self.after_cancel(self._window_state_after_id)
        self._window_state_after_id = self.after(400, self._persist_window_state)

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
        signature = (size, zoomed)
        if signature == self._last_persisted_state:
            return
        self._last_persisted_state = signature
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

    def _make_scrollable_page(self):
        """创建可滚动内容页：内容过高自动滚动，放得下时隐藏滚动条。

        页面不参与宿主的 grid（grid 会按「期望尺寸」反过来撑大窗口，
        而且拖动窗口时每一步都要重排整页）。改由 _place_page() 用 place
        钉成固定像素，尺寸只在缩放停手后更新一次。
        """
        page = AutoHideScrollableFrame(self.page_host, fg_color=self._app_fg_color)
        page.grid_columnconfigure(0, weight=1)
        page.grid_rowconfigure(0, weight=1)
        self.page_containers.append(page)
        return page

    # ---------------- 窗口缩放：拖动时冻结页面，停手后一次性跟随 ----------------
    # CTk 控件重绘一次约 3ms（圆角要用 PIL 画好再转 PhotoImage），总览页里有
    # 上百个控件：边拖边重排实测 ~950ms/帧，窗口跟着鼠标走一步卡一秒。
    # 现在的做法是
    #   1) 页面用 place 钉在宿主里，拖动全程尺寸不变、完全不参与重排（~110ms/帧）；
    #   2) 判定为「交互式拖动」后把页面取消映射，换上它的「定格截图」当幕布：
    #      重绘成本降到 ~45ms/帧，鼠标走到哪窗口跟到哪，而且画面看着还在，
    #      不会像纯色幕布那样让人以为软件白屏卡死；
    #   3) 停手 HOST_SETTLE_MS 后落幕布，一次性铺满新尺寸并重排（只卡这一下）。
    # 停止缩放多久算「拖完了」。必须明显大于一帧的耗时：拖动时每个
    # <Configure> 都会把这个定时器往后推，一旦某一帧比它慢（升起幕布要
    # 拍一张 ~120ms 的截图），定时器就会在拖动途中到点，触发一次整页
    # 重排（~500ms）—— 用户看到的就是「拖着拖着猛卡一下」。
    HOST_SETTLE_MS = 240
    # 第 1 个尺寸变化就升幕布。之前要连击 2 次才升，结果拖动的头两帧仍然
    # 带着真页面重排：实测 174ms + 233ms，鼠标已经动了窗口内容还跟不上，
    # 这就是「一开始特别卡」的手感来源。现在头一帧只花一次截图（~95ms），
    # 之后每帧 ~40ms，整个拖动过程都跟手。
    # 误判（非拖动的单次尺寸变化，如最大化）也没有副作用：幕布就是页面
    # 自己的定格截图，看着跟真页面一样，HOST_SETTLE_MS 后自动落下。
    DRAG_BURST = 1

    def _on_host_configure(self, event):
        w, h = event.width, event.height
        if w < 4 or h < 4:
            return                      # 启动初期/最小化时的无效尺寸
        if self._host_size == (w, h):
            return                      # 只是移动窗口，尺寸没变
        self._host_size = (w, h)
        if self._settling:
            # _settle_layout 自己（换侧栏档位 / 铺页面）引发的尺寸变化：
            # 一律忽略，交给它收尾。若在这里计入连击，就会「落幕布 -> 铺页面
            # -> 又落幕布」地来回闪。
            return
        page = self._current_page_widget()
        if self._curtain_page is None and not page._parent_frame.winfo_ismapped():
            # 启动 / 切页后页面还没铺上：立刻铺满，别留下 HOST_SETTLE_MS 的白屏
            self._place_page(page, force=True)
        now = time.monotonic()
        # 连击窗口 0.45s：真拖动时 <Configure> 每帧（~16ms）就来一个，
        # 两下就判定为拖动；窗口取宽一点是为了防止「偶发一帧特别慢 ->
        # 连击计数被清零 -> 幕布升不起来 -> 每帧都慢」的死循环。
        self._cfg_burst = self._cfg_burst + 1 if now - self._last_cfg_at < 0.45 else 1
        self._last_cfg_at = now
        if self._curtain_armed and self._cfg_burst >= self.DRAG_BURST:
            self._raise_curtain()
        if self._settle_timer is not None:
            self.after_cancel(self._settle_timer)
        self._settle_timer = self.after(self.HOST_SETTLE_MS, self._settle_layout)

    def _current_page_widget(self):
        return self.pages[self._current_page][0]

    def _raise_curtain(self):
        """交互式拖动缩放时把当前页面收起来，换成一张「定格截图」。"""
        if self._curtain_page is not None:
            return
        page = self._current_page_widget()
        self._curtain_page = page
        try:
            # 必须在 place_forget 之前截图，否则拍到的是空白宿主
            self._grab_curtain_snapshot()
        except Exception:
            self._hide_curtain()      # 拍不到就退回「纯色幕布」，流程照常走完
        tk.Frame.place_forget(page._parent_frame)

    def _grab_curtain_snapshot(self):
        """给页面拍一张静态截图当幕布。

        真页面在拖动期间必须取消映射（上百个 CTk 控件每帧重绘 ~170ms，
        窗口根本跟不上鼠标），但只留一块纯色背景会让人以为软件白屏卡死。
        抓一张图顶在上面：拖动全程零重绘、画面「定格」，停手后再无缝换回
        真页面。截图只在拖动开始时拍一次（~15ms），拍失败就退回纯色幕布。
        """
        host = self.page_host
        canvas = self._curtain_canvas
        if canvas is None:
            canvas = tk.Canvas(
                host, highlightthickness=0, borderwidth=0, bg=host.cget("bg")
            )
            self._curtain_canvas = canvas
        canvas.delete("shot")
        self._curtain_image = None
        w, h = self._host_size
        try:
            if w > 8 and h > 8:
                from PIL import ImageGrab, ImageTk
                x, y = host.winfo_rootx(), host.winfo_rooty()
                shot = ImageGrab.grab((x, y, x + w, y + h))
                self._curtain_image = ImageTk.PhotoImage(shot, master=self)
                canvas.create_image(0, 0, image=self._curtain_image,
                                    anchor="nw", tags="shot")
        except Exception:
            self._curtain_image = None
        # 原生 tk 的 place 收物理像素；relwidth/relheight=1 让它跟着宿主铺满，
        # 窗口拉大时截图之外的部分露出宿主背景色。
        canvas.place(x=0, y=0, relwidth=1.0, relheight=1.0)
        # 注意不能用 canvas.lift()/canvas.tkraise()：tkinter.Canvas 把这两个
        # 名字都重绑成了 tag_raise（抬画布里的图元），会直接报 wrong # args。
        # 要把画布本身抬到页面之上，只能直接调 Tcl 的 raise 命令。
        canvas.tk.call("raise", canvas._w)

    def _hide_curtain(self):
        """落幕布：真页面已按新尺寸重排完毕，收掉截图并释放它占的内存。"""
        canvas = self._curtain_canvas
        if canvas is None:
            return
        canvas.place_forget()
        canvas.delete("shot")
        self._curtain_image = None

    def _place_page(self, page, force=False):
        """把页面用 place 钉满宿主（收物理像素），尺寸没变就什么都不做。"""
        w, h = self._host_size
        if w < 4 or h < 4:
            w, h = self.page_host.winfo_width(), self.page_host.winfo_height()
            if w < 4 or h < 4:
                return False            # 宿主还没量出尺寸：等下一次 <Configure>
        key = page.winfo_id()
        if not force and self._page_sizes.get(key) == (w, h):
            return False
        self._page_sizes[key] = (w, h)
        # CTkScrollableFrame.place() 转发给 CTkFrame.place()，而后者禁止传
        # width/height；这里直接调 tk.Frame.place，收的就是原生物理像素。
        tk.Frame.place(page._parent_frame, x=0, y=0, width=w, height=h)
        return True

    def _settle_layout(self):
        """缩放停手后一次性跟随新尺寸：侧栏档位 -> 页面铺满 -> 重排 -> 折行。"""
        self._settle_timer = None
        self._settling = True
        try:
            self._cfg_burst = 0
            # 只有侧栏真的换了档才需要冲刷一次几何：换档会改变宿主尺寸，
            # 必须等它稳定才能量到最终值。没换档时这一下 update_idletasks
            # 纯属白等 —— 实测 70~120ms（整棵窗口树的挂起几何都在这里结算），
            # 是「松手后卡一下」的一大块。
            if self._sync_sidebar_tier():
                self.update_idletasks()
            self._host_size = (self.page_host.winfo_width(), self.page_host.winfo_height())
            page = self._current_page_widget()
            curtained = self._curtain_page is not None
            self._curtain_page = None
            changed = self._place_page(page, force=True)
            if not changed and not curtained:
                return
            tab = self.pages[self._current_page][1]
            self.update_idletasks()
            relayout = getattr(tab, "relayout_now", None)
            if relayout is not None:
                relayout()
                self.update_idletasks()
        finally:
            # 页面已按新尺寸铺满并重排完，此刻才收掉定格截图：
            # 用户看到的是「定格画面 -> 新布局」的一次切换，中间没有空白帧。
            self._hide_curtain()
            self._settling = False
            # 这次重排自己产生的几何事件不能算进「下一次拖动」的连击计数
            self._cfg_burst = 0
            self._last_cfg_at = time.monotonic()
            if not self._curtain_armed and self._curtain_arm_timer is None:
                self._curtain_arm_timer = self.after(400, self._arm_curtain)

    def _arm_curtain(self):
        """页面已经真正画到屏幕上，从此允许用「定格截图」代替真页面。"""
        self._curtain_arm_timer = None
        self._curtain_armed = True

    def _sync_sidebar_tier(self):
        """窗口越窄侧栏越窄，把横向空间尽量让给内容区。

        返回是否真的换了档：调用方据此决定要不要等一次几何冲刷。
        """
        width = self.winfo_width()
        tier = 0 if width >= 1240 else (1 if width >= 1000 else (2 if width >= 780 else 3))
        if tier == self._sidebar_tier:
            return False
        self._sidebar_tier = tier
        self.sidebar.configure(width=scaled(self, (190, 162, 140, 120)[tier]))
        return True

    def _set_appearance_mode(self, mode_string):
        """系统深/浅色切换时，原生宿主框的背景色也要跟着换。"""
        super()._set_appearance_mode(mode_string)
        try:
            self.page_host.configure(bg=self._apply_appearance_mode(self._app_fg_color))
        except Exception:
            pass

    def _show_page(self, name):
        # 只让当前页参与布局：其余两页 place_forget（取消映射、不占几何）。
        # 三个页原本叠在同一个宿主里，缩放窗口时每次都要重排三页
        # （含两个表格页），这是 resize 卡顿的主要原因。
        self._current_page = name
        self._curtain_page = None
        self._hide_curtain()
        for key, (page, _tab) in self.pages.items():
            if key == name:
                self._place_page(page, force=True)
                page._parent_frame.lift()
            else:
                self._page_sizes.pop(page.winfo_id(), None)
                tk.Frame.place_forget(page._parent_frame)
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
        set_label_text(
            self.sidebar_status,
            f"Hook: {hook_state}\n热键: {'开' if self.controller.hk_running else '关'}\n鼠标: {'开' if self.controller.mc_running else '关'}",
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

    def _set_git_busy(self, busy):
        """四个 Git 按钮共用一把锁。

        配置同步走 config 分支、代码同步走 main 分支，但它们操作的是同一个
        本地仓库（同一份 index / refs / 对象库）。同时点「上传配置」和
        「上传代码」会让两个 git 进程互相踩 index.lock，必须互斥。
        """
        self._git_busy = busy
        tab = self.overview_tab
        tab.set_sync_buttons_busy(busy)
        tab.set_code_buttons_busy(busy)

    def _start_config_sync(self, action):
        if getattr(self, "_git_busy", False):
            return
        self._config_sync_busy = True
        self._set_git_busy(True)
        tab = self.overview_tab
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
        self._set_git_busy(False)
        tab = self.overview_tab
        label = "上传配置" if action == "upload" else "拉取配置"
        if error is not None:
            tab.set_sync_status_text("同步状态：%s失败（原因见弹窗）" % label)
            messagebox.showerror(label, "操作失败：\n%s" % error, parent=self)
            return
        if action == "download":
            try:
                tab.apply_config_reload()
            except Exception as exc:
                messagebox.showerror(label, "配置文件已更新，但引擎重载失败：\n%s" % exc, parent=self)
                return
        # 同步结果里已经带了远端 sha 和提交时间，直接写回状态文字即可：
        # 旧实现在这里还要再 fetch 一次远端，等于每次点击两次网络往返（慢一倍）。
        result = result or {}
        if result.get("sha"):
            tab.apply_sync_info({"sha": result["sha"], "time": result.get("time", "")})
        else:
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
        if getattr(self, "_git_busy", False):
            return
        self._code_sync_busy = True
        self._set_git_busy(True)
        tab = self.overview_tab
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
        self._set_git_busy(False)
        tab = self.overview_tab
        label = "下载代码" if action == "pull" else "上传代码"
        if error is not None:
            tab.set_code_status_text("代码状态：%s失败（原因见弹窗）" % label)
            messagebox.showerror(label, "操作失败：\n%s" % error, parent=self)
            return
        # pull/push 完成后本地就已经知道与远端的领先/落后关系（远端跟踪引用
        # 刚被更新过），直接算出来写回状态，省掉一次 fetch。
        status = (result or {}).get("status")
        if status:
            tab.apply_code_info(status)
        else:
            tab.refresh_code_status(force=True)
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

