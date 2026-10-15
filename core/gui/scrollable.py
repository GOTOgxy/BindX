# -*- coding: utf-8 -*-
"""内容页容器：内容超过窗口高度时自动垂直滚动；放得下时自动隐藏滚动条，
并把内容拉伸填满整个视口（页面布局可用 grid 行权重分配富余高度）。"""

import tkinter as tk

import customtkinter as ctk


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """CTkScrollableFrame 增强版：

    - 右侧滚动条按需显示/隐藏；
    - 内容比视口短时，把内容拉伸到视口高度填满界面，
      页面内 grid 中带权重的行（如概览页的两排卡片）会自动获得富余高度。
    """

    def __init__(self, master, fg_color=None, **kwargs):
        super().__init__(master, fg_color=fg_color, **kwargs)
        # add=True，且注册在基类 <Configure> 处理器之后：画布尺寸变化时，
        # 本处理器在基类「窗口项宽度=画布宽度」之后运行，负责高度方向；
        # 内容尺寸变化时，在基类更新 scrollregion 之后运行。
        self.bind("<Configure>", self._sync_scrollbar, add=True)
        self._parent_canvas.bind("<Configure>", self._sync_scrollbar, add=True)

    def _sync_scrollbar(self, event=None):
        try:
            view_height = self._parent_canvas.winfo_height()
            natural_height = self.winfo_reqheight()
        except tk.TclError:
            return
        if view_height <= 0 or natural_height < 4:
            # 启动初期内容高度尚未测量的几何事件，跳过
            return
        if natural_height > view_height + 2:
            # 内容超出视口：显示滚动条，内容保持自然高度
            self._scrollbar.grid()
            self._parent_canvas.itemconfigure(
                self._create_window_id, height=natural_height
            )
        else:
            # 内容放得下：隐藏滚动条，把内容拉伸填满视口
            self._scrollbar.grid_remove()
            self._parent_canvas.itemconfigure(
                self._create_window_id, height=view_height
            )