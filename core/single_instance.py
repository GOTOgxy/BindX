# -*- coding: utf-8 -*-
"""BindX 单实例互斥体：创建与释放（启动和重启流程共用）。"""

import ctypes

ERROR_ALREADY_EXISTS = 183
MUTEX_NAME = "Global\\BindX"

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
_kernel32.CreateMutexW.restype = ctypes.c_void_p

_handle = None


def acquire():
    """创建单实例互斥体；已有其他实例持有时返回 False。"""
    global _handle
    _handle = _kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not _handle:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        release()
        return False
    return True


def release():
    """释放互斥体（重启前调用，让新实例能拿到）。"""
    global _handle
    if _handle:
        _kernel32.CloseHandle(_handle)
        _handle = None