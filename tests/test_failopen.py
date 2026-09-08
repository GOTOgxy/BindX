# -*- coding: utf-8 -*-

import ctypes
import unittest

from core.trigger_engine import TriggerEngine


class FakeHotkeyManager:
    def __init__(self, entries=None):
        self.entries = entries or []


class SentinelUser32:
    """CallNextHookEx 返回哨兵值，用于断言事件被原样放行。"""

    def __init__(self, value=0xC0FFEE, raise_next=False):
        self.value = value
        self.raise_next = raise_next
        self.calls = 0

    def CallNextHookEx(self, *args):
        self.calls += 1
        if self.raise_next:
            raise RuntimeError("CallNextHookEx exploded")
        return self.value

    def GetAsyncKeyState(self, vk):
        return 0


def _boom(*args):
    raise RuntimeError("hook implementation exploded")


class FailOpenContractTests(unittest.TestCase):
    """契约测试：钩子回调内部任何异常都不得吞掉/扭曲用户输入，
    必须原样传给 CallNextHookEx；连它都失败时返回 0（放行语义），
    系统会按 LowLevelHooksTimeout 卸载钩子（fail-open）。"""

    def setUp(self):
        self.engine = TriggerEngine(FakeHotkeyManager(), {"mappings": []})
        self.engine.keyboard_enabled = True
        self.engine.mouse_enabled = True

    def _keyinfo(self, vk=ord("A"), down=True):
        info = self.engine.KBDLLHOOKSTRUCT()
        info.vkCode = vk
        info.flags = 0
        info.dwExtraInfo = 0
        msg = self.engine.WM_KEYDOWN if down else self.engine.WM_KEYUP
        return msg, ctypes.addressof(info)

    def test_keyboard_impl_exception_passes_through(self):
        u32 = SentinelUser32(value=0xC0FFEE)
        self.engine._user32 = u32
        self.engine._keyboard_proc_impl = _boom
        msg, addr = self._keyinfo()
        ret = self.engine._keyboard_proc(0, msg, addr)
        self.assertEqual(ret, 0xC0FFEE)
        self.assertEqual(u32.calls, 1)

    def test_mouse_impl_exception_passes_through(self):
        u32 = SentinelUser32(value=0xBEEF)
        self.engine._user32 = u32
        self.engine._mouse_proc_impl = _boom
        ret = self.engine._mouse_proc(0, self.engine.WM_XBUTTONDOWN, 0)
        self.assertEqual(ret, 0xBEEF)
        self.assertEqual(u32.calls, 1)

    def test_keyboard_exception_with_broken_diag_log_still_passes(self):
        # 日志路径（_diag_queue）也坏了时仍然放行
        u32 = SentinelUser32(value=0xDEAD)
        self.engine._user32 = u32
        self.engine._keyboard_proc_impl = _boom
        self.engine._diag_queue = None
        self.engine._diag_writer = None
        msg, addr = self._keyinfo()
        ret = self.engine._keyboard_proc(0, msg, addr)
        self.assertEqual(ret, 0xDEAD)
        self.assertEqual(u32.calls, 1)

    def test_keyboard_double_failure_returns_zero(self):
        u32 = SentinelUser32(raise_next=True)
        self.engine._user32 = u32
        self.engine._keyboard_proc_impl = _boom
        msg, addr = self._keyinfo()
        ret = self.engine._keyboard_proc(0, msg, addr)
        self.assertEqual(ret, 0)
        self.assertEqual(u32.calls, 1)

    def test_mouse_double_failure_returns_zero(self):
        u32 = SentinelUser32(raise_next=True)
        self.engine._user32 = u32
        self.engine._mouse_proc_impl = _boom
        ret = self.engine._mouse_proc(0, self.engine.WM_XBUTTONDOWN, 0)
        self.assertEqual(ret, 0)
        self.assertEqual(u32.calls, 1)


if __name__ == "__main__":
    unittest.main()
