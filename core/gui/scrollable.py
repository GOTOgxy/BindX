# -*- coding: utf-8 -*-
"""内容页容器：内容超过窗口高度时自动垂直滚动；放得下时自动隐藏滚动条，
并把内容拉伸填满整个视口（页面布局可用 grid 行权重分配富余高度）。"""

import tkinter as tk

import customtkinter as ctk

from .theme import suppress_draw_flush


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """CTkScrollableFrame 增强版：

    - 右侧滚动条按需显示/隐藏；
    - 内容比视口短时，把内容拉伸到视口高度填满界面，
      页面内 grid 中带权重的行（如概览页的两排卡片）会自动获得富余高度。
    """

    def __init__(self, master, fg_color=None, **kwargs):
        super().__init__(master, fg_color=fg_color, **kwargs)
        # (是否溢出, 目标高度) 缓存：拖动窗口时 <Configure> 每秒会触发上百次，
        # 只有尺寸真的变了才去 grid()/itemconfigure()，否则反复触发重排 -> 卡顿。
        self._sync_state = None        # 已应用的 (是否溢出, 目标高度)
        self._probe_state = None       # 上一轮复检量到的值（判断是否收敛）
        self._stable_rounds = 0        # 连续几轮没变化
        self._recheck_rounds = 0       # 本轮复检链已跑几次（保险丝）
        self._recheck_after_id = None
        # add=True，且注册在基类 <Configure> 处理器之后：画布尺寸变化时，
        # 本处理器在基类「窗口项宽度=画布宽度」之后运行，负责高度方向；
        # 内容尺寸变化时，在基类更新 scrollregion 之后运行。
        self.bind("<Configure>", self._sync_scrollbar, add=True)
        self._parent_canvas.bind("<Configure>", self._sync_scrollbar, add=True)
        self._install_fast_scrollbar()

    def _install_fast_scrollbar(self):
        """消除滚动条在窗口缩放时的「重绘 -> 整树重排 -> 重绘」嵌套风暴。

        CTkScrollbar._draw() 结尾有一句 `self._canvas.update_idletasks()`，
        它会同步冲刷整棵窗口树的待处理几何事件。而画布的 yscrollcommand 每次
        scrollregion 变化都会被调用一次 set() -> _draw()，于是重排里再套重排：
        实测拖动窗口时单次 set() 就要 400ms+，是 resize 卡顿的主因。

        这里做两件事：
        1) 重绘期间临时屏蔽那句 update_idletasks()——重绘只是被推迟到事件循环
           的正常空档执行，最终画面完全一致；
        2) set() 的数值没变时直接跳过，不再触发任何重绘。
        """
        sb = self._scrollbar
        suppress_draw_flush(sb)

        def _set_if_changed(start_value, end_value):
            try:
                start_value = float(start_value)
                end_value = float(end_value)
            except (TypeError, ValueError):
                return
            if sb._start_value == start_value and sb._end_value == end_value:
                return
            sb.set(start_value, end_value)

        self._parent_canvas.configure(yscrollcommand=_set_if_changed)

    def _create_grid(self):
        # 基类在换肤/换缩放时会重新 grid 滚动条，缓存随之失效
        super()._create_grid()
        self._sync_state = None
        self._probe_state = None
        self._stable_rounds = 0

    def _measure(self):
        """量一次 (是否溢出, 内容目标高度)；还没量出有效几何时返回 None。"""
        try:
            view_height = self._parent_canvas.winfo_height()
            natural_height = self.winfo_reqheight()
        except tk.TclError:
            return None
        if view_height <= 0 or natural_height < 4:
            # 启动初期内容高度尚未测量的几何事件，跳过
            return None
        overflow = natural_height > view_height + 2
        return (overflow, natural_height if overflow else view_height)

    def _sync_scrollbar(self, event=None):
        measured = self._measure()
        if measured is None or measured == self._sync_state:
            return
        self._apply_sync(measured)

    def _apply_sync(self, measured):
        overflow, target = measured
        self._sync_state = measured
        self._probe_state = measured
        self._stable_rounds = 0
        if overflow:
            # 内容超出视口：显示滚动条，内容保持自然高度
            self._scrollbar.grid()
        else:
            # 内容放得下：隐藏滚动条，把内容拉伸填满视口
            self._scrollbar.grid_remove()
        self._parent_canvas.itemconfigure(self._create_window_id, height=target)
        self._kick_recheck()

    def invalidate_natural_height(self):
        """内容自然高度可能变了：立刻重量一次，不对就纠正。

        为什么必须显式调用：内容高度被画布窗口项钉死，页面里子控件重排
        （卡片并排/堆叠、按钮横排/竖排、标签换行）只会改变内容的
        **请求**高度，不会给本控件发 <Configure>。只靠事件驱动就永远慢一档：
        窗口缩小后底部内容被裁掉、放大后底部空一大片。
        """
        measured = self._measure()
        if measured is None:
            return
        if measured != self._sync_state:
            self._apply_sync(measured)
        else:
            self._kick_recheck()

    # 复检：内容自然高度总是慢一拍，量一次不够，要连着量到稳定为止。
    # 但必须收敛后立刻停手 —— 之前写成「每轮都强制重算并再排一轮」，
    # 结果变成常驻的 after(1) 死循环（实测每秒上千次重排整页几何），
    # 窗口缩放、按钮反馈都跟着发涩。
    STABLE_ROUNDS = 2      # 连续几轮量到的值不变 = 收敛
    MAX_ROUNDS = 60        # 保险丝：极端情况下也不会变成常驻循环

    def _kick_recheck(self):
        if self._recheck_after_id is None:
            self._recheck_rounds = 0
            self._stable_rounds = 0
            self._recheck_after_id = self.after(1, self._recheck_sync)

    def _recheck_sync(self):
        self._recheck_after_id = None
        measured = self._measure()
        if measured is None:
            return
        if measured != self._sync_state:
            self._apply_sync(measured)     # 内部会再排一轮
            return
        if measured == self._probe_state:
            self._stable_rounds += 1
        else:
            self._probe_state = measured
            self._stable_rounds = 0
        if self._stable_rounds >= self.STABLE_ROUNDS:
            return                         # 收敛，停手
        self._recheck_rounds += 1
        if self._recheck_rounds > self.MAX_ROUNDS:
            return                         # 保险丝
        self._recheck_after_id = self.after(1, self._recheck_sync)
