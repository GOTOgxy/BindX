# -*- coding: utf-8 -*-
"""内容页容器：内容超过窗口高度时自动垂直滚动，放得下时自动隐藏滚动条。"""

import tkinter as tk

import customtkinter as ctk


class AutoHideScrollableFrame(ctk.CTkScrollableFrame):
    """CTkScrollableFrame 增强版：右侧滚动条按需显示/隐藏。"""

    def __init__(self, master, fg_color=None, **kwargs):
        super().__init__(master, fg_color=fg_color, **kwargs)
        self.bind("<Configure>", self._sync_scrollbar, add=True)
        self._parent_canvas.bind("<Configure>", self._sync_scrollbar, add=True)

    def _sync_scrollbar(self, event=None):
        try:
            content_height = self.winfo_height()
            view_height = self._parent_canvas.winfo_height()
        except tk.TclError:
            return
        if content_height > view_height + 2:
            self._scrollbar.grid()
        else:
            self._scrollbar.grid_remove()