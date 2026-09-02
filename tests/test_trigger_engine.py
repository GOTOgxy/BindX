# -*- coding: utf-8 -*-

import ctypes
import threading
import time
import unittest
from unittest.mock import patch

from core import trigger_engine as trigger_engine_module
from core.trigger_engine import BINDX_EXTRA_INFO, TriggerEngine


_hk = trigger_engine_module._hk


class FakeHotkeyManager:
    def __init__(self, entries=None):
        self.entries = entries or []


class FakeUser32:
    def __init__(self):
        self.down_vks = set()

    @staticmethod
    def CallNextHookEx(*args):
        return 0

    def GetAsyncKeyState(self, vk):
        if vk in self.down_vks:
            return 0x8000
        generic = {
            TriggerEngine.VK_CONTROL: TriggerEngine.CTRL_KEYS,
            TriggerEngine.VK_SHIFT: TriggerEngine.SHIFT_KEYS,
            TriggerEngine.VK_MENU: TriggerEngine.ALT_KEYS,
        }
        return 0x8000 if any(item in self.down_vks for item in generic.get(vk, set())) else 0


class TriggerEngineTests(unittest.TestCase):
    def setUp(self):
        self.engine = TriggerEngine(FakeHotkeyManager(), {"mappings": []})
        self.engine.keyboard_enabled = True
        self.engine._user32 = FakeUser32()
        self.injected = []

    def _key(self, vk, down=True, injected=False, from_bindx=False):
        if not injected:
            if down:
                self.engine._user32.down_vks.add(vk)
            else:
                self.engine._user32.down_vks.discard(vk)
        msg = self.engine.WM_KEYDOWN if down else self.engine.WM_KEYUP
        if vk in (self.engine.VK_MENU, self.engine.VK_LMENU, self.engine.VK_RMENU):
            msg = self.engine.WM_SYSKEYDOWN if down else self.engine.WM_SYSKEYUP
        info = self.engine.KBDLLHOOKSTRUCT()
        info.vkCode = vk
        info.flags = self.engine.LLKHF_INJECTED if injected else 0
        info.dwExtraInfo = BINDX_EXTRA_INFO if from_bindx else 0
        return self.engine._keyboard_proc_impl(0, msg, ctypes.addressof(info))

    def _ctrl_alt_q_entry(self):
        mods = _hk.MOD_CONTROL | _hk.MOD_ALT
        return {
            "id": 1,
            "hotkey": "CTRL+ALT+Q",
            "modifiers": mods,
            "virtual_key": ord("Q"),
            "enabled": True,
            "controller": None,
        }

    def test_unmatched_common_combinations_pass_through(self):
        cases = [
            (self.engine.VK_LCONTROL, ord("C")),
            (self.engine.VK_LCONTROL, ord("V")),
            (self.engine.VK_LSHIFT, ord("A")),
            (self.engine.VK_LMENU, ord("A")),
        ]
        for modifier, key in cases:
            with self.subTest(modifier=hex(modifier), key=chr(key)):
                self.assertEqual(self._key(modifier, True), 0)
                self.assertEqual(self._key(key, True), 0)
                self.assertEqual(self._key(key, False), 0)
                self.assertEqual(self._key(modifier, False), 0)
                self.assertEqual(self.engine.pop_hotkey_events(), [])

    def test_configured_hotkey_triggers_once_and_suppresses_keyup(self):
        self.engine.hotkey_manager.entries = [self._ctrl_alt_q_entry()]
        self.assertEqual(self._key(self.engine.VK_LCONTROL, True), 0)
        self.assertEqual(self._key(self.engine.VK_LMENU, True), 0)
        self.assertEqual(self._key(ord("Q"), True), 1)
        self.assertEqual(self._key(ord("Q"), True), 1)
        self.assertEqual(self._key(ord("Q"), False), 1)
        self.assertEqual(self.engine.pop_hotkey_events(), [1])
        self.assertEqual(self.engine.pop_hotkey_events(), [])

    def test_modifier_keyup_immediately_clears_physical_state(self):
        ctrl = _hk.MOD_CONTROL
        self.assertEqual(self._key(self.engine.VK_LCONTROL, True), 0)
        self.assertEqual(self.engine._current_modifiers(), ctrl)
        self.assertEqual(self._key(self.engine.VK_LCONTROL, False), 0)
        self.assertEqual(self.engine._current_modifiers(), 0)

    def test_ghost_modifier_state_does_not_trigger_hotkey(self):
        self.engine.hotkey_manager.entries = [self._ctrl_alt_q_entry()]
        self.engine._physical_modifiers.update(
            {self.engine.VK_LCONTROL, self.engine.VK_LMENU}
        )
        self.assertEqual(self._key(ord("Q"), True), 0)
        self.assertEqual(self.engine.pop_hotkey_events(), [])

    def test_ime_composition_blocks_hotkey(self):
        self.engine.hotkey_manager.entries = [self._ctrl_alt_q_entry()]
        self.engine._user32.down_vks.update(
            {self.engine.VK_LCONTROL, self.engine.VK_LMENU}
        )
        with patch.object(self.engine, "_ime_composition_active", return_value=True):
            self.assertEqual(self._key(ord("Q"), True), 0)
        self.assertEqual(self.engine.pop_hotkey_events(), [])

    def _capture_injection(self):
        def inject(name, down):
            self.injected.append((name, down))
            return True

        self.engine._inject_key = inject

    def test_release_during_output_delay_outputs_full_combination(self):
        self._capture_injection()
        self.engine.set_output_options(delay_ms=60)
        self.engine._physical_modifiers.add(self.engine.VK_LCONTROL)
        worker = threading.Thread(target=self.engine._do_output, args=(["ctrl", "c"],))
        worker.start()
        time.sleep(0.02)
        self.engine._physical_modifiers.discard(self.engine.VK_LCONTROL)
        worker.join(timeout=1.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(
            self.injected,
            [
                ("ctrl", True),
                ("c", True),
                ("c", False),
                ("ctrl", False),
            ],
        )

    def test_modifier_release_race_does_not_restore_stuck_modifier(self):
        self._capture_injection()
        self.engine.set_output_options(delay_ms=0)
        self.engine._physical_modifiers.add(self.engine.VK_LCONTROL)

        original = self.engine._inject_key

        def inject(name, down):
            result = original(name, down)
            if name == "c" and down:
                self.engine._physical_modifiers.discard(self.engine.VK_LCONTROL)
            return result

        self.engine._inject_key = inject
        self.engine._do_output(["c"])
        self.assertEqual(
            self.injected,
            [
                ("left ctrl", False),
                ("c", True),
                ("c", False),
            ],
        )

    def test_stop_event_cancels_in_flight_output(self):
        self._capture_injection()
        self.engine.set_output_options(delay_ms=80)
        worker = threading.Thread(target=self.engine._do_output, args=(["ctrl", "c"],))
        worker.start()
        time.sleep(0.02)
        self.engine._stop_event.set()
        worker.join(timeout=1.0)
        self.assertFalse(worker.is_alive())
        self.assertEqual(self.injected, [])


if __name__ == "__main__":
    unittest.main()
