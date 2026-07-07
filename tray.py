# -*- coding: utf-8 -*-

"""BindX 系统托盘图标。

仿照 app_hotkey_manager/gui.py 与 mouse_click/gui.py 的纯 ctypes 托盘实现，但合并为单个
BindX 图标。直接复用 hotkey_manager 模块中已加载并正确配置 argtypes 的 user32 /
kernel32 / shell32 / gdi32 及 WNDCLASS / NOTIFYICONDATAW 结构，避免重复定义导致
argtypes 互覆盖。

事件流（与子项目一致）：
  WndProc 把托盘消息的 lparam 存入 self._tray_event，gui 主循环通过 after() 周期性
  调用 poll() 消费该值，分发到 on_show / on_menu 回调。
"""

import ctypes
import queue
from ctypes import wintypes

import config_proxy

_hk = config_proxy.hk_module()
user32 = _hk.user32
kernel32 = _hk.kernel32
shell32 = _hk.shell32
gdi32 = _hk.gdi32
WNDCLASS = _hk.WNDCLASS
NOTIFYICONDATAW = _hk.NOTIFYICONDATAW

NIF_MESSAGE = _hk.NIF_MESSAGE
NIF_ICON = _hk.NIF_ICON
NIF_TIP = _hk.NIF_TIP
NIM_ADD = _hk.NIM_ADD
NIM_DELETE = _hk.NIM_DELETE
TRAY_ICON_ID = _hk.TRAY_ICON_ID

TRAY_CALLBACK_MSG = 0x0400
WM_LBUTTONUP = 0x0202
WM_LBUTTONDBLCLK = 0x0203
WM_RBUTTONUP = 0x0205
WM_NULL = 0x0000

TRAY_CLASS_NAME = "BindXTray"
TRAY_TIP = "BindX"


class TrayIcon:
    def __init__(self, on_show, on_menu):
        self.on_show = on_show
        self.on_menu = on_menu
        self.tray_hwnd = None
        self.tray_icon_id = TRAY_ICON_ID
        self._tray_queue = queue.Queue()
        self._tray_wndproc_ref = None
        self._create()

    def _create_icon(self):
        SIZE = 16
        hdc_screen = user32.GetDC(None)
        hdc_mem = gdi32.CreateCompatibleDC(hdc_screen)
        hbm = gdi32.CreateCompatibleBitmap(hdc_screen, SIZE, SIZE)
        old_bm = gdi32.SelectObject(hdc_mem, hbm)

        hbr_bg = gdi32.CreateSolidBrush(0x001F2937)
        rect = wintypes.RECT(0, 0, SIZE, SIZE)
        user32.FillRect(hdc_mem, ctypes.byref(rect), hbr_bg)
        gdi32.DeleteObject(hbr_bg)

        hbr_accent = gdi32.CreateSolidBrush(0x00EAB308)
        accent = wintypes.RECT(0, 0, 4, SIZE)
        user32.FillRect(hdc_mem, ctypes.byref(accent), hbr_accent)
        gdi32.DeleteObject(hbr_accent)

        gdi32.SetBkMode(hdc_mem, 1)
        hfont = gdi32.CreateFontW(12, 0, 0, 0, 800, 0, 0, 0, 0, 0, 0, 0, 0, "Segoe UI")
        old_font = gdi32.SelectObject(hdc_mem, hfont)
        gdi32.SetTextColor(hdc_mem, 0x00FFFFFF)
        gdi32.TextOutW(hdc_mem, 5, 1, "B", 1)
        gdi32.SelectObject(hdc_mem, old_font)
        gdi32.DeleteObject(hfont)

        mask_bm = gdi32.CreateBitmap(SIZE, SIZE, 1, 1, None)
        hdc_mask = gdi32.CreateCompatibleDC(None)
        gdi32.SelectObject(hdc_mask, mask_bm)
        rect_mask = wintypes.RECT(0, 0, SIZE, SIZE)
        hbr_white = gdi32.CreateSolidBrush(0x00FFFFFF)
        user32.FillRect(hdc_mask, ctypes.byref(rect_mask), hbr_white)
        gdi32.DeleteObject(hbr_white)

        class ICONINFO(ctypes.Structure):
            _fields_ = [
                ("fIcon", wintypes.BOOL),
                ("xHotspot", wintypes.DWORD),
                ("yHotspot", wintypes.DWORD),
                ("hbmMask", ctypes.c_void_p),
                ("hbmColor", ctypes.c_void_p),
            ]

        icon_info = ICONINFO()
        icon_info.fIcon = True
        icon_info.xHotspot = 0
        icon_info.yHotspot = 0
        icon_info.hbmMask = mask_bm
        icon_info.hbmColor = hbm
        h_icon = user32.CreateIconIndirect(ctypes.byref(icon_info))

        gdi32.SelectObject(hdc_mem, old_bm)
        gdi32.DeleteObject(mask_bm)
        gdi32.DeleteObject(hbm)
        gdi32.DeleteDC(hdc_mask)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(None, hdc_screen)
        return h_icon

    def _create(self):
        self._tray_wndproc_ref = ctypes.WINFUNCTYPE(
            ctypes.c_long, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
        )(self._wndproc_impl)

        wc = WNDCLASS()
        wc.lpfnWndProc = ctypes.cast(self._tray_wndproc_ref, ctypes.c_void_p)
        wc.lpszClassName = TRAY_CLASS_NAME
        wc.hInstance = kernel32.GetModuleHandleW(None)
        user32.RegisterClassW(ctypes.byref(wc))

        self.tray_hwnd = user32.CreateWindowExW(
            0, wc.lpszClassName, TRAY_CLASS_NAME,
            0, 0, 0, 0, 0, None, None, wc.hInstance, None
        )

        h_icon = self._create_icon()

        nid = NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
        nid.hWnd = self.tray_hwnd
        nid.uID = self.tray_icon_id
        nid.uFlags = NIF_MESSAGE | NIF_ICON | NIF_TIP
        nid.uCallbackMessage = TRAY_CALLBACK_MSG
        nid.hIcon = h_icon
        nid.szTip = TRAY_TIP
        shell32.Shell_NotifyIconW(NIM_ADD, ctypes.byref(nid))

    def _wndproc_impl(self, hwnd, msg, wparam, lparam):
        if msg == TRAY_CALLBACK_MSG:
            self._tray_queue.put(lparam)
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def poll(self):
        try:
            while True:
                ev = self._tray_queue.get_nowait()
                if ev == WM_RBUTTONUP:
                    if self.on_menu:
                        self.on_menu()
                elif ev == WM_LBUTTONUP or ev == WM_LBUTTONDBLCLK:
                    if self.on_show:
                        self.on_show()
        except queue.Empty:
            pass

    def show_menu_at_cursor(self, menu):
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        if self.tray_hwnd:
            user32.SetForegroundWindow(self.tray_hwnd)
        menu.tk_popup(pt.x, pt.y)
        menu.grab_release()
        if self.tray_hwnd:
            user32.PostMessageW(self.tray_hwnd, WM_NULL, 0, 0)

    def destroy(self):
        if self.tray_hwnd:
            nid = NOTIFYICONDATAW()
            nid.cbSize = ctypes.sizeof(NOTIFYICONDATAW)
            nid.hWnd = self.tray_hwnd
            nid.uID = self.tray_icon_id
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(nid))
            user32.DestroyWindow(self.tray_hwnd)
            self.tray_hwnd = None
