# -*- coding: utf-8 -*-
"""BindX UI: 主窗口页签（总览 / Hot Key / Mouse）。"""

import json
import threading
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from .. import shortcut_manager
from .entry_dialogs import AddMappingDialog, EntryDialog
from .inspector import InputInspectorWindow
from customtkinter.windows.widgets.core_widget_classes import CTkBaseClass

from .theme import (BUTTON_DEFAULT_FG, BUTTON_DEFAULT_HOVER, menu_font,
                    rescaled, scaled, set_label_text, suppress_draw_flush,
                    ui_font, unscaled)

def _auto_wrap_label(label, initial_wraplength=None):
    """标签自动换行：宽度不足时文本折行显示，而不是被截断。

    initial_wraplength: 初始换行宽度（逻辑像素）。用于约束标签的布局请求宽度，
    避免很长的状态文字撑大所在 grid 列、导致同一行的两张卡片宽窄不一；
    控件实际布局完成后，换行宽度会随实际宽度实时更新。

    注意：CTkLabel 的 wraplength 收「逻辑值」，内部会再乘一次 ui_scale；
    而 winfo_width() 是物理像素，必须先用 unscaled() 换算回去，
    否则高 DPI 下换行宽度被放大两次，长文本永远不折行。
    """
    if initial_wraplength:
        label.configure(wraplength=initial_wraplength)

    state = {"wrap": initial_wraplength}

    def _on_configure(event):
        width = unscaled(label, label.winfo_width()) - 4
        if width > 60 and width != state["wrap"]:
            # 只有换行宽度真的变了才 configure：否则每次 resize 都重排文本 -> 卡顿
            state["wrap"] = width
            label.configure(wraplength=width)

    label.bind("<Configure>", _on_configure)
    return label

class OverviewTab(ctk.CTkFrame):
    def __init__(self, parent, controller, app):
        super().__init__(parent, fg_color="transparent")
        self.controller = controller
        self.app = app

        # 布局规则（纯 grid/pack，无 <Configure> 强制宽度逻辑，resize 不卡）：
        # - 横向：两列容器用 uniform 永远等宽，随窗口宽度自然伸缩，可压缩；
        # - 纵向：两排卡片行（第 1、3 行）以 weight=1 吸收富余高度，
        #   全局动作行保持自然高度；
        # - 卡片内部：标题/状态在上，按钮行沉底，中间空行吸收富余高度；
        # - 全局动作的设置行按可用宽度自动换行（仅跨阈值时重排）。
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        self.grid_rowconfigure(3, weight=1)
        ctk.CTkLabel(self, text="引擎总览", font=ui_font(self, 20, "bold")).grid(row=0, column=0, sticky=tk.W, pady=(0, scaled(self, 16)))

        self.cards = ctk.CTkFrame(self, fg_color="transparent")
        self.cards.grid(row=1, column=0, sticky=tk.NSEW)
        self.cards.columnconfigure(0, weight=1, uniform="half")
        self.cards.columnconfigure(1, weight=1, uniform="half")
        self.cards.grid_rowconfigure(0, weight=1)

        self.hk_card, self.hk_status, btns_hk = self._build_card(self.cards, 0, "热键引擎")
        self._card_button(btns_hk, "启动", self._start_hk)
        self._card_button(btns_hk, "停止", self._stop_hk, last=True,
                          fg_color="#52525b", hover_color="#3f3f46")

        self.mc_card, self.mc_status, btns_mc = self._build_card(self.cards, 1, "鼠标映射")
        self._card_button(btns_mc, "启动", self._start_mc)
        self._card_button(btns_mc, "停止", self._stop_mc, last=True,
                          fg_color="#52525b", hover_color="#3f3f46")

        # 全局动作块：两行内容（动作按钮 / 设置项）共用同一套「等分流式网格」。
        # 每行都等宽铺满整行 -> 视觉重心居中、不再偏左；窗口变窄时自动折成 2~3 行。
        # 全局动作：动作按钮与设置项共用同一套「流式行」网格。
        # 每一行都横向铺满整块区域（行内格子等宽、按钮拉伸填满），所以无论
        # 窗口宽窄，各行长度始终一致、整体重心居中，不会再出现长短不一、
        # 偏左的观感；窗口变窄时自动折成多行，折行阈值由实测宽度决定。
        self.actions_frame = ctk.CTkFrame(self, corner_radius=10)
        self.actions_frame.grid(row=2, column=0, sticky=tk.NSEW, pady=(scaled(self, 16), 0))
        ctk.CTkLabel(
            self.actions_frame, text="全局动作", font=ui_font(self, 15, "bold"),
        ).pack(anchor=tk.W, padx=scaled(self, 16), pady=(scaled(self, 14), scaled(self, 10)))

        self.actions_body = ctk.CTkFrame(self.actions_frame, fg_color="transparent")
        self.actions_body.pack(fill=tk.X, padx=scaled(self, 16), pady=(0, scaled(self, 14)))
        # 动作 / 设置两组各占一个 30 列网格（uniform 组必须唯一，不能共用容器）
        self.action_grid = ctk.CTkFrame(self.actions_body, fg_color="transparent")
        self.action_grid.pack(fill=tk.X)
        self.setting_grid = ctk.CTkFrame(self.actions_body, fg_color="transparent")
        self.setting_grid.pack(fill=tk.X, pady=(self.GROUP_GAP, 0))

        self._action_cells = []
        for text, command, fg in (
            ("全部启动", self._start_all, None),
            ("全部停止", self._stop_all, "#52525b"),
            ("重置窗口", self.app._reset_window_layout, "#52525b"),
            ("导出配置", self.export_config, "#52525b"),
            ("导入配置", self.import_config, "#52525b"),
            ("重新启动", self._restart_app, "#52525b"),
        ):
            cell = self._flow_cell(self.action_grid)
            kwargs = {} if fg is None else {"fg_color": fg, "hover_color": "#3f3f46"}
            ctk.CTkButton(cell, text=text, command=command, font=ui_font(self, 14),
                          **kwargs).pack(fill=tk.X, expand=True)
            self._action_cells.append(cell)

        font_cell = self._flow_cell(self.setting_grid)
        font_inner = ctk.CTkFrame(font_cell, fg_color="transparent")
        font_inner.pack(fill=tk.X, expand=True)
        ctk.CTkLabel(font_inner, text="字体大小", font=ui_font(self, 13)).pack(
            side=tk.LEFT, padx=(0, scaled(self, 6))
        )
        self.font_preset_menu = ctk.CTkOptionMenu(
            font_inner,
            values=["紧凑", "稍小", "常规", "特大", "超大"],
            command=self.app._change_font_preset,
            width=64,
            font=ui_font(self, 13),
            dropdown_font=ui_font(self, 13),
        )
        # CTkOptionMenu._draw() 结尾有一句 canvas.update_idletasks()，
        # 会把整棵窗口树的几何事件同步冲刷一遍（重排里再套重排）；
        # 缩放窗口时它是卡顿源之一，重绘期间临时屏蔽即可，画面完全一致。
        suppress_draw_flush(self.font_preset_menu)
        self.font_preset_menu.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.font_preset_menu.set(self.app._get_font_preset())

        autostart_cell = self._flow_cell(self.setting_grid)
        self.autostart_var = tk.BooleanVar(value=self.controller.get_autostart_enabled())
        self.autostart_switch = ctk.CTkSwitch(
            autostart_cell,
            text="开机自启",
            variable=self.autostart_var,
            onvalue=True,
            offvalue=False,
            command=self._toggle_autostart,
            font=ui_font(self, 13),
        )
        self.autostart_switch.pack(fill=tk.X, expand=True)

        desktop_cell = self._flow_cell(self.setting_grid)
        self.desktop_shortcut_btn = ctk.CTkButton(
            desktop_cell, text="创建桌面图标", command=self._toggle_desktop_shortcut,
            font=ui_font(self, 14),
        )
        self.desktop_shortcut_btn.pack(fill=tk.X, expand=True)

        start_menu_cell = self._flow_cell(self.setting_grid)
        self.start_menu_shortcut_btn = ctk.CTkButton(
            start_menu_cell,
            text="创建开始菜单",
            command=self._toggle_start_menu_shortcut,
            font=ui_font(self, 14),
        )
        self.start_menu_shortcut_btn.pack(fill=tk.X, expand=True)

        quit_cell = self._flow_cell(self.setting_grid)
        ctk.CTkButton(
            quit_cell, text="退出 BindX", command=self.app._quit_app,
            fg_color="#991b1b", hover_color="#7f1d1d", font=ui_font(self, 14),
        ).pack(fill=tk.X, expand=True)

        self._settings_cells = [font_cell, autostart_cell, desktop_cell, start_menu_cell, quit_cell]
        self._flow_state = {}
        self._flow_timer = None
        self._flow_row_pool = {}
        self._flow_col_count = {}
        self._cards_single = None
        self._card_btn_vertical = {}
        # 注意：CTkFrame.bind 实际绑在内部 canvas 上，<Configure> 的 event.widget
        # 是 canvas 而不是 frame；旧代码按 frame 过滤，导致启动后折行逻辑再没跑过。
        self.actions_body.bind("<Configure>", self._on_actions_configure)
        self.sync_cards = ctk.CTkFrame(self, fg_color="transparent")
        self.sync_cards.grid(row=3, column=0, sticky=tk.NSEW, pady=(16, 0))
        self.sync_cards.columnconfigure(0, weight=1, uniform="half")
        self.sync_cards.columnconfigure(1, weight=1, uniform="half")
        self.sync_cards.grid_rowconfigure(0, weight=1)

        self.sync_card, self.sync_status, sync_btn_row = self._build_card(
            self.sync_cards, 0, "配置云同步（Git）",
            status_font=ui_font(self, 12), status_color="#71717a", status_wrap=150,
        )
        self.upload_sync_btn = self._card_button(sync_btn_row, "上传配置", self._upload_sync)
        self.download_sync_btn = self._card_button(
            sync_btn_row, "拉取配置", self._download_sync, last=True,
            fg_color="#52525b", hover_color="#3f3f46")
        self._sync_status_querying = False
        self._last_sync_info = None

        self.code_card, self.code_status, code_btn_row = self._build_card(
            self.sync_cards, 1, "代码同步（Git）",
            status_font=ui_font(self, 12), status_color="#71717a", status_wrap=150,
        )
        self.pull_code_btn = self._card_button(code_btn_row, "下载代码", self._pull_code)
        self.push_code_btn = self._card_button(code_btn_row, "上传代码", self._push_code, last=True)
        self._code_status_querying = False
        self._last_code_info = None
        self._layout_flows()
        self.refresh_shortcut_buttons()
        self.refresh_status()
        self.refresh_git_status()

    def _build_card(self, parent, column, title, status_font=None, status_color=None, status_wrap=None):
        """标准卡片：标题/状态在上，按钮行沉底，中间空行吸收富余高度。"""
        card = ctk.CTkFrame(parent, corner_radius=10)
        card.grid(row=0, column=column, sticky=tk.NSEW,
                  padx=(max(1, self.FLOW_GAP // 2),) * 2)
        card.columnconfigure(0, weight=1)
        card.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(card, text=title, font=ui_font(self, 15, "bold")).grid(
            row=0, column=0, sticky=tk.W,
            padx=scaled(self, 16), pady=(scaled(self, 14), scaled(self, 6)),
        )
        status = ctk.CTkLabel(
            card, text="", anchor="w",
            text_color=status_color,
            font=status_font if status_font else ui_font(self, 13),
        )
        if status_wrap:
            status = _auto_wrap_label(status, initial_wraplength=status_wrap)
        status.grid(row=1, column=0, sticky=tk.EW, padx=scaled(self, 16), pady=(0, scaled(self, 8)))
        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.grid(row=3, column=0, sticky=tk.EW,
                  padx=scaled(self, 16), pady=(0, scaled(self, 16)))
        return card, status, btns

    # 卡片底部按钮的宽度下限（逻辑像素）。真正的显示宽度由
    # pack(fill=X, expand=True) 决定 —— 同一行按钮永远等分整行、有富余就
    # 一起拉伸，所以卡片再宽也不会出现「按钮挤在左边、右边空一块」。
    # 「请求宽度」则决定卡片并排/堆叠的折行阈值：写死一个偏大的值会把
    # 阈值顶高（窗口稍窄就全部堆成一列），偏小又会在极窄窗口下被 pack
    # 压成一条缝。所以按文字实测宽度动态取，任何字体档位/DPI 都刚好。
    CARD_BTN_MIN = 44

    def _card_button(self, row, text, command, last=False, **kwargs):
        btn = ctk.CTkButton(row, text=text, command=command,
                            width=self.CARD_BTN_MIN, **kwargs)
        btn.pack(side=tk.LEFT, fill=tk.X, expand=True,
                 padx=(0, 0 if last else self.FLOW_GAP))
        need = self._min_width_of(btn) + rescaled(self, 4)
        btn.configure(width=max(self.CARD_BTN_MIN, unscaled(self, need)))
        return btn

    # -------- 流式网格（全局动作） --------
    # 每组（动作 / 设置）拆成「一行一个 row 容器」，行内格子严格等宽：
    #   - 满行 N 格 -> N 列 weight=1 + uniform -> Tk 保证等宽；
    #   - 不满一行时两侧各补一列 weight=(ref-N) 的空列 -> 格子宽度仍等于
    #     满行时的 1/ref，整行居中，上下行列边界完全对齐；
    #   - 宽度全由 grid 权重驱动，缩放窗口时零 Python 参与，不卡；
    #     只有「折行方案」真的变了才重排一次。
    # 注意：CTk 的 grid()/pack() 会把 padx/pady 再乘一次 DPI 缩放，
    # 所以传进去的一律是「逻辑像素」（与 winfo_* 的物理像素差一倍）。
    FLOW_GAP = 8    # 逻辑像素：格子左右留白（相邻格间距 = 2 倍）/ 行间距
    GROUP_GAP = 16  # 逻辑像素：动作组与设置组之间的间距

    def _flow_cell(self, master):
        """全局动作里的一格：透明容器，按钮拉伸铺满、开关/下拉居中。"""
        return ctk.CTkFrame(master, fg_color="transparent")

    def _on_actions_configure(self, event=None):
        """全局动作区宽度变化 -> 防抖重排（折行方案没变就什么都不做）。"""
        if self._flow_timer:
            self.after_cancel(self._flow_timer)
        self._flow_timer = self.after(90, self._layout_flows)

    def _layout_flows(self):
        """按当前实测宽度重排：全局动作折行 + 卡片并排/堆叠。

        只有「折行方案」或「卡片列数」真的变了才会去动 grid，
        所以窗口缩放期间被反复调用也几乎零成本。
        """
        self._flow_timer = None
        available = self.actions_body.winfo_width()
        gap = rescaled(self, self.FLOW_GAP)
        groups = (
            (self.action_grid, self._action_cells, "actions"),
            (self.setting_grid, self._settings_cells, "settings"),
        )
        # 两组共用同一个 ref（满行格数）：列宽一致，上下两组的格子才能
        # 在竖直方向对齐，看起来是一整块规整的网格，而不是两截错位的行。
        parts, ref = self._flow_partition([cells for _c, cells, _k in groups],
                                          available, gap)
        for (container, cells, key), part in zip(groups, parts):
            self._flow_layout(container, cells, part, key, ref)
        self._apply_card_columns()
        self._apply_card_buttons()
        self._notify_height()

    def _notify_height(self):
        """告诉滚动页「内容自然高度可能变了，请重量一次」。

        卡片并排/堆叠、按钮横排/竖排、状态文字换行都只改变内容的**请求**
        高度；页面高度被画布窗口项钉死，这些变化不会给滚动容器发
        <Configure>，不显式通知就会「慢一档」：窗口缩小后底部被裁掉、
        放大后底部空一大片。
        """
        invalidate = getattr(self.master, "invalidate_natural_height", None)
        if invalidate is None:
            return
        try:
            invalidate()
        except tk.TclError:
            pass

    def relayout_now(self):
        """窗口缩放停手后由 app 调用：立刻按新宽度重排，不等防抖。"""
        if self._flow_timer:
            self.after_cancel(self._flow_timer)
        # 新宽度要穿过「页面画布 -> 画布窗口项 -> 内层 frame -> 本页 -> 各容器」
        # 好几层几何才传得到 actions_body / cards 上，单次 update_idletasks
        # 量到的还是旧宽度，折行与卡片并排的判定就会慢半拍（要靠 90ms 后的
        # 防抖再补一次，用户会看到布局「跳一下」）。这里冲刷到宽度稳定为止。
        last = None
        for _ in range(3):
            self.update_idletasks()
            now = (self.actions_body.winfo_width(), self.cards.winfo_width())
            if now == last:
                break
            last = now
        self._layout_flows()

    # -------- 真实最小宽度 --------
    # CTkButton / CTkOptionMenu 的 winfo_reqwidth() 会被它们写死的默认 width
    # （140 / 64 逻辑像素）顶上去，并不是真实下限；拿它去折行，宽窗口下
    # 永远排不出 3 列——这正是「全局动作总是两列、长短不一」的根因。
    # 下面按控件内部结构算真实下限：文字实测宽度 + 内部固定留白。
    def _min_width_of(self, widget):
        if isinstance(widget, ctk.CTkFrame):
            return self._cell_min_width(widget)
        if isinstance(widget, ctk.CTkButton):
            label = getattr(widget, "_text_label", None)
            text = label.winfo_reqwidth() if label is not None else 0
            pad = max(getattr(widget, "_corner_radius", 0),
                      getattr(widget, "_border_width", 0) + 1,
                      getattr(widget, "_border_spacing", 0))
            return text + 2 * rescaled(self, pad)
        if isinstance(widget, ctk.CTkOptionMenu):
            # 内部 tk.Label 自带左右 padx（右侧那块留给下拉箭头）就是真实下限
            label = getattr(widget, "_text_label", None)
            if label is not None:
                return label.winfo_reqwidth()
        if isinstance(widget, ctk.CTkLabel):
            label = getattr(widget, "_label", None)
            if label is not None:
                return label.winfo_reqwidth() + rescaled(self, 2)
        return widget.winfo_reqwidth()

    def _cell_min_width(self, frame):
        """容器（格子 / 内层 frame）的最小宽度 = 子控件最小宽度之和 + 间距。"""
        try:
            kids = [k for k in frame.winfo_children() if isinstance(k, CTkBaseClass)]
        except tk.TclError:
            return 1
        total = 0
        for kid in kids:
            total += self._min_width_of(kid) + self._pack_pad(kid, "padx")
        return max(total, 1)

    @staticmethod
    def _pack_pad(widget, key):
        """读 pack 的 padx/pady（可能是 8、'0 8' 或元组），返回两侧总像素。"""
        try:
            raw = widget.pack_info().get(key, 0)
        except (tk.TclError, AttributeError):
            return 0
        parts = raw if isinstance(raw, (tuple, list)) else str(raw).split()
        try:
            values = [abs(int(float(part))) for part in parts]
        except ValueError:
            return 0
        if not values:
            return 0
        return values[0] * 2 if len(values) == 1 else sum(values[:2])

    def _flow_partition(self, cell_groups, available, gap):
        """定下每组分几行、每行几格（行数越少越好）。

        格宽 = 可用宽度 / ref - gap（每格左右各留 gap/2），只要它 >=
        本组最宽格子的真实最小宽度就不会截断文字。全程用实测物理像素
        比较，不写死任何魔法阈值，DPI 缩放、字体变化都能自动适配。
        """
        counts = [len(cells) for cells in cell_groups]
        max_rows = max(counts) if counts else 1

        if available <= 1:
            # 启动瞬间还没量出宽度：先按「每行 3 格」铺开。常见窗口宽度下
            # 这就是最终结果，量出宽度后若不同会自动纠正，不会看到明显跳变。
            parts = [self._balanced_rows(count, min(3, count)) for count in counts]
            return parts, max(max(part) for part in parts)
        needs = []
        for cells in cell_groups:
            try:
                needs.append(max([self._cell_min_width(cell) for cell in cells] or [1]))
            except tk.TclError:
                needs.append(1)
        if max(needs) <= 1:
            parts = [self._balanced_rows(count, min(3, count)) for count in counts]
            return parts, max(max(part) for part in parts)
        for rows in range(1, max_rows + 1):
            parts = [self._balanced_rows(count, min(rows, count)) for count in counts]
            ref = max(max(part) for part in parts)
            cell_w = available / float(ref) - gap
            if all(cell_w + 0.5 >= need for need in needs):
                return parts, ref
        # 窗口窄到连一格都放不下：每格一行，交给滚动条
        return [[1] * count for count in counts], 1

    @staticmethod
    def _balanced_rows(count, rows):
        """把 count 个格子尽量均分成 rows 行（靠前的行多一个），避免末行落单。"""
        base, extra = divmod(count, rows)
        return [base + (1 if i < extra else 0) for i in range(rows)]

    def _flow_row_frames(self, key, container, count):
        """行容器池：只在行数变多时新建，不反复创建/销毁控件。"""
        rows = self._flow_row_pool.setdefault(key, [])
        while len(rows) < count:
            rows.append(ctk.CTkFrame(container, fg_color="transparent"))
        return rows

    def _flow_layout(self, container, cells, part, key, ref):
        """按 part（每行几格）铺网格：行内等宽、不满行居中、上下对齐。

        格子本身是 container 的子控件（永不重建），用 grid(in_=row)
        交给行容器管理；行内列权重只有两种：格子列 2、两侧留白列
        (ref - size)，同属一个 uniform 组 -> Tk 严格按权重比例分宽度：
        格宽恒为 ref 分之一，不满一行时自动居中。
        折行方案没变时直接返回，缩放期间不碰 grid，不会卡。
        """
        state = (tuple(part), ref)
        if self._flow_state.get(key) == state:
            return
        self._flow_state[key] = state
        rows = self._flow_row_frames(key, container, len(part))
        pad = max(1, self.FLOW_GAP // 2)      # 逻辑像素：CTk 会自己乘 DPI 缩放
        index = 0
        for ri, size in enumerate(part):
            row = rows[ri]
            extra = ref - size
            weights = ([extra] if extra else []) + [2] * size + ([extra] if extra else [])
            done = self._flow_col_count.get(row, 0)
            for ci in range(max(done, len(weights))):
                if ci < len(weights):
                    row.grid_columnconfigure(ci, weight=weights[ci], uniform=key + str(ri))
                else:
                    row.grid_columnconfigure(ci, weight=0, uniform="")
            self._flow_col_count[row] = len(weights)
            for ci in range(size):
                cells[index].grid(in_=row, row=0, column=(1 if extra else 0) + ci,
                                  sticky=tk.NSEW, padx=(pad, pad))
                index += 1
            row.pack(fill=tk.X, pady=(0 if ri == 0 else self.FLOW_GAP, 0))
        for row in rows[len(part):]:
            row.pack_forget()

    # -------- 卡片：宽窗口左右并排，窄窗口自动上下堆叠 --------
    def _row_need_width(self, row):
        """一行子控件「横排」所需宽度（与它当前是横排还是竖排无关）。

        必须用这个稳定量去判定卡片并排/堆叠：如果直接读按钮行自身的
        winfo_reqwidth()，竖排时它会塌成「最宽那一个按钮」的宽度，
        于是「并排」判定通过 -> 按钮改横排 -> 需要宽度暴涨 -> 本该改回
        堆叠却因为状态没变而提前 return，窗口 1100~1200 时就会出现
        两张卡片挤在一起、按钮文字被裁掉的现象。
        """
        try:
            kids = row.winfo_children()
        except tk.TclError:
            return 1
        gap = rescaled(self, self.FLOW_GAP)
        return sum(k.winfo_reqwidth() for k in kids) + gap * max(0, len(kids) - 1)

    def _card_need_width(self, card):
        """一张卡片放得下标题 + 按钮行所需的最小物理宽度。

        只看标题和按钮行（宽度固定），不看状态标签：后者会随实际
        宽度自动改 wraplength，算进去会让「并排/堆叠」来回振荡。
        """
        widest = 1
        for row in (0, 3):
            slaves = card.grid_slaves(row=row, column=0)
            if not slaves:
                continue
            if row == 3:
                widest = max(widest, self._row_need_width(slaves[0]))
            else:
                widest = max(widest, slaves[0].winfo_reqwidth())
        inner = 2 * rescaled(self, 16)                     # 卡片内左右留白
        outer = rescaled(self, self.FLOW_GAP)              # 卡片在容器里的左右 padx
        return widest + inner + outer

    def _apply_card_columns(self):
        """容器宽度不够放两张卡片时，自动改成单列上下堆叠。"""
        width = self.cards.winfo_width()
        if width <= 1:
            return
        pairs = ((self.hk_card, self.mc_card), (self.sync_card, self.code_card))
        try:
            need = max(sum(self._card_need_width(card) for card in pair) for pair in pairs)
        except tk.TclError:
            return
        single = width < need
        if single == self._cards_single:
            return
        self._cards_single = single
        pad = max(1, self.FLOW_GAP // 2)
        for container, pair in (
            (self.cards, pairs[0]),
            (self.sync_cards, pairs[1]),
        ):
            for index, card in enumerate(pair):
                if single:
                    card.grid(row=index, column=0, columnspan=2, sticky=tk.NSEW,
                              padx=(pad, pad),
                              pady=(0, self.FLOW_GAP) if index == 0 else (0, 0))
                else:
                    card.grid(row=0, column=index, columnspan=1, sticky=tk.NSEW,
                              padx=(pad, pad), pady=0)
                container.grid_rowconfigure(index, weight=1 if (single or index == 0) else 0)

    def _apply_card_buttons(self):
        """卡片窄到放不下按钮行时，把按钮改成竖排。

        内容页是纵向 CTkScrollableFrame：横向没有滚动条，放不下的部分会被
        直接裁掉（pack 在空间不足时只挤压后放的控件，最后一个按钮会被压成
        一条缝）。改成竖排后每个按钮都是整行宽，再窄的窗口也能点得到。

        判定用「横排所需宽度」（各按钮请求宽度之和 + 间距），它跟当前是横排
        还是竖排无关，所以不会来回抖动。
        """
        for card in (self.hk_card, self.mc_card, self.sync_card, self.code_card):
            slaves = card.grid_slaves(row=3, column=0)
            if not slaves:
                continue
            row = slaves[0]
            width = row.winfo_width()
            if width <= 1:
                continue
            kids = row.winfo_children()
            vertical = width < self._row_need_width(row)
            if vertical == self._card_btn_vertical.get(card):
                continue
            self._card_btn_vertical[card] = vertical
            for index, btn in enumerate(kids):
                # 这里的 gap 是「pack 用的逻辑像素」，跟上面判定用的物理像素
                # 同名会互相覆盖（曾经把 need 里的间距算成 0，导致该竖排时
                # 仍横排、按钮被裁），务必用独立变量名。
                pad = 0 if index == len(kids) - 1 else self.FLOW_GAP
                # padx / pady 必须两个都显式给：pack() 只覆盖传进去的选项，
                # 竖排时留下的 pady 会在切回横排后继续生效，按钮行凭空高出一截。
                if vertical:
                    btn.pack(side=tk.TOP, fill=tk.X, padx=0, pady=(0, pad))
                else:
                    btn.pack(side=tk.LEFT, fill=tk.X, expand=True,
                             padx=(0, pad), pady=0)

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
            text="删除开始菜单" if start_menu_exists else "创建开始菜单",
            fg_color=BUTTON_DEFAULT_FG if start_menu_exists else "#52525b",
            hover_color=BUTTON_DEFAULT_HOVER if start_menu_exists else "#3f3f46",
        )
        self._layout_flows()  # 文案变化会影响实测宽度，顺手校正折行

    def refresh_status(self):
        current_autostart = bool(self.controller.app_state.get("autostart_enabled", False))
        if self.autostart_var.get() != current_autostart:
            self.autostart_var.set(current_autostart)
        # 这里 500ms 被调用一次：文字没变就不要 configure，
        # 否则每次都会重绘 canvas 并把窗口标脏，拖动窗口时叠加成额外重绘。
        if self.controller.hk_running:
            enabled_entries = [e for e in self.controller.hotkey_manager.entries if e.get("enabled", True)]
            registered = sum(1 for e in enabled_entries if e.get("registered"))
            failed = sum(1 for e in enabled_entries if e.get("last_error"))
            suffix = f"（{registered}/{len(enabled_entries)} 已注册"
            if failed:
                suffix += f"，{failed} 失败"
            suffix += "）"
            set_label_text(self.hk_status, f"运行中 {suffix}")
        else:
            set_label_text(self.hk_status, "已停止")

        if self.controller.mc_running:
            if self.controller.trigger_engine._active_mouse:
                set_label_text(self.mc_status, "运行中")
            elif self.controller.trigger_engine.last_error:
                set_label_text(self.mc_status, f"启动失败 {self.controller.trigger_engine.last_error}")
            else:
                set_label_text(self.mc_status, "运行中(无启用的鼠标映射)")
        else:
            set_label_text(self.mc_status, "已停止")
        # 500ms 一次的心跳：顺带兜底校正内容高度（状态文字变长/变短会换行，
        # 只改请求高度、不发 <Configure>，见 _notify_height）
        self._notify_height()

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
            self.apply_config_reload()
        except Exception as e:
            messagebox.showerror("导入失败", str(e), parent=self)
            return
        messagebox.showinfo("导入成功", "配置已导入，热键与鼠标映射已重新加载。", parent=self)



    def _upload_sync(self):
        self.app._upload_config_to_git()

    def _download_sync(self):
        self.app._download_config_from_git()

    def set_sync_buttons_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.upload_sync_btn.configure(state=state)
        self.download_sync_btn.configure(state=state)

    def set_sync_status_text(self, text):
        self.sync_status.configure(text=text)
        self._notify_height()

    def refresh_git_status(self):
        """启动时一次性刷新两块 Git 状态：全程只发一次 fetch。

        「配置云同步」看 config 分支、「代码同步」看 main 分支，但它们在
        同一个远端仓库。分开查要连两次 GitHub —— 实测 SSH 单次握手就要
        4~5 秒，两个线程还会被全局 git 锁串起来，启动后白等十来秒。
        改成 fetch_all_refs() 一次把所有分支拉下来，两块状态各自只读
        本地引用（零网络）。
        """
        if self._sync_status_querying or self._code_status_querying:
            return
        self._sync_status_querying = True
        self._code_status_querying = True

        def worker():
            from .. import code_sync, config_sync
            net_err = None
            try:
                config_sync.fetch_all_refs()
            except Exception as exc:
                net_err = str(exc)
            queries = (
                ("config_sync_status",
                 lambda: config_sync.remote_status(refresh=False)),
                ("code_sync_status", lambda: code_sync.code_status(refresh=False)),
            )
            for tag, query in queries:
                try:
                    info = query()
                except Exception as exc:
                    self.app._ui_queue.put((tag, None, str(exc)))
                    continue
                # 联网失败但本地还留着上次的远端引用时，先按本地信息展示；
                # 只有本地也一无所知（info is None）才把网络错误报出来。
                self.app._ui_queue.put((tag, info, None if info else net_err))

        threading.Thread(target=worker, daemon=True).start()

    def refresh_sync_status(self, force=False):
        if self._sync_status_querying and not force:
            return
        self._sync_status_querying = True

        def worker():
            from .. import config_sync
            try:
                info = config_sync.remote_status()
            except Exception as exc:
                self.app._ui_queue.put(("config_sync_status", None, str(exc)))
            else:
                self.app._ui_queue.put(("config_sync_status", info, None))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def _pretty_time(value):
        return (value or "").replace("T", " ")[:16]

    def apply_sync_info(self, info):
        """用已知的同步结果直接刷新状态文字（不再发网络请求）。"""
        self._last_sync_info = info
        if info is None:
            self.sync_status.configure(text="同步状态：远端还没有配置，按「上传配置」即可创建")
        else:
            self.sync_status.configure(
                text="远端最近同步：%s（%s）" % (self._pretty_time(info.get("time")), info["sha"][:7])
            )

    def _finish_sync_status(self, info, error):
        self._sync_status_querying = False
        if error:
            self.sync_status.configure(text="同步状态：查询失败（%s）" % str(error)[:50])
        else:
            self.apply_sync_info(info)
        self._notify_height()


    def _pull_code(self):
        self.app._pull_code_from_git()

    def _push_code(self):
        self.app._push_code_to_git()

    def _restart_app(self):
        self.app._restart_app()

    def set_code_buttons_busy(self, busy):
        state = "disabled" if busy else "normal"
        self.pull_code_btn.configure(state=state)
        self.push_code_btn.configure(state=state)

    def set_code_status_text(self, text):
        self.code_status.configure(text=text)
        self._notify_height()

    def refresh_code_status(self, force=False):
        if self._code_status_querying and not force:
            return
        self._code_status_querying = True

        def worker():
            from .. import code_sync
            try:
                info = code_sync.code_status()
            except Exception as exc:
                self.app._ui_queue.put(("code_sync_status", None, str(exc)))
            else:
                self.app._ui_queue.put(("code_sync_status", info, None))

        threading.Thread(target=worker, daemon=True).start()

    def apply_code_info(self, info):
        """用已知的代码同步结果直接刷新状态文字（不再发网络请求）。"""
        self._last_code_info = info
        if info is None:
            self.code_status.configure(text="代码状态：远端还没有 main 分支，先按「上传代码」")
        elif info["ahead"] == 0 and info["behind"] == 0:
            self.code_status.configure(text="代码状态：与远端一致（%s）" % info["local_sha"][:7])
        else:
            parts = []
            if info["ahead"]:
                parts.append("本地领先 %d 个提交（未推送）" % info["ahead"])
            if info["behind"]:
                parts.append("落后远端 %d 个提交" % info["behind"])
            self.code_status.configure(
                text="代码状态：%s（本地 %s / 远端 %s）"
                % ("，".join(parts), info["local_sha"][:7], info["remote_sha"][:7])
            )

    def _finish_code_status(self, info, error):
        self._code_status_querying = False
        if error:
            self.code_status.configure(text="代码状态：查询失败（%s）" % str(error)[:50])
        else:
            self.apply_code_info(info)
        self._notify_height()

    def apply_config_reload(self):
        """配置文件落盘后（导入/拉取）重载引擎并刷新界面。"""
        self.controller.reload_all_config()
        # reload 后 hotkey_manager 是新实例，同步引用，
        # 避免标签页继续操作旧实例
        self.app.hotkey_tab.manager = self.controller.hotkey_manager
        self.refresh_status()
        self.app.hotkey_tab._refresh_list()
        self.app.mouse_tab.reload_config()



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
            elif not entry.get("modifiers") and not self.controller.trigger_engine.running:
                # 无修饰键热键由钩子负责注册；钩子没跑等于没注册
                registered = "引擎停止"
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


