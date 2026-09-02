# -*- coding: utf-8 -*-

import ctypes
import unittest
from unittest.mock import patch

import hotkeys.hotkey_manager as hotkey_manager


class FakeUser32:
    def __init__(self):
        self.calls = []

    def GetWindowRect(self, hwnd, rect):
        target = ctypes.cast(rect, ctypes.POINTER(hotkey_manager.wintypes.RECT)).contents
        target.left, target.top = 10, 20
        target.right, target.bottom = 810, 620
        return True

    def GetWindowLongPtrW(self, hwnd, index):
        self.calls.append(("GetWindowLongPtrW", hwnd, index))
        return hotkey_manager.WS_EX_APPWINDOW

    def SetWindowLongPtrW(self, hwnd, index, style):
        self.calls.append(("SetWindowLongPtrW", hwnd, index, style))
        return 1

    def SetWindowPos(self, hwnd, after, x, y, width, height, flags):
        self.calls.append(("SetWindowPos", hwnd, x, y, width, height, flags))
        return True

    def ShowWindow(self, hwnd, command):
        self.calls.append(("ShowWindow", hwnd, command))
        return True

    def IsWindow(self, hwnd):
        return hwnd == 42


class WindowHideTests(unittest.TestCase):
    def test_taskbar_hidden_minimize_also_hides_minimized_window(self):
        controller = hotkey_manager.AppController(
            app_id="termius",
            exe_name="Termius.exe",
            simple_window_control=True,
            hide_from_taskbar=True,
            disable_window_memory=True,
        )
        fake = FakeUser32()
        with (
            patch.object(hotkey_manager, "user32", fake),
            patch.object(hotkey_manager, "get_window_pid", return_value=123),
        ):
            self.assertTrue(controller.hide_window(42))
            self.assertEqual(controller._get_remembered_window([123]), 42)

        show_commands = [call[2] for call in fake.calls if call[0] == "ShowWindow"]
        self.assertEqual(
            show_commands,
            [hotkey_manager.SW_MINIMIZE, hotkey_manager.SW_HIDE],
        )


if __name__ == "__main__":
    unittest.main()
