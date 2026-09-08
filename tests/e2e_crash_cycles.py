# -*- coding: utf-8 -*-

import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

import core.config_store as config_store

TMP = Path(tempfile.mkdtemp(prefix="bindx_e2e_"))
config_store.CONFIG_FILE = TMP / "bindx_config.json"
config_store.LEGACY_HOTKEY_FILE = TMP / "no_such_legacy_hk.json"
config_store.LEGACY_MOUSE_FILE = TMP / "no_such_legacy_mouse.json"

import json

SYNTH_CONFIG = {
    "app": {
        "hotkey_running": True,
        "mouse_running": False,
        "window_size": "944x582",
        "window_zoomed": False,
        "font_preset": "常规",
        "autostart_enabled": False,
        "output_delay_ms": 20,
        "restore_held_modifiers": True,
    },
    "hotkeys": {
        "display_name": "App Hotkey Manager",
        "mutex_name": "Global\\AppHotkeyManagerE2E",
        "entries": [
            {
                "app": "cloudmusic",
                "hotkey": "CTRL+ALT+B",
                "launch_if_not_running": False,
                "install_path": "",
                "enabled": True,
                "_runtime_profile": {"hide_behavior": "tray", "show_behavior": "activate_window"},
            },
            {
                "app": "zotero",
                "hotkey": "CTRL+ALT+V",
                "launch_if_not_running": False,
                "install_path": "",
                "enabled": True,
                "_runtime_profile": {},
            },
            {
                "app": "termius",
                "hotkey": "CTRL+ALT+K",
                "launch_if_not_running": False,
                "install_path": "",
                "enabled": True,
                "_runtime_profile": {},
                "target_type": "builtin",
                "name": "Termius",
            },
            {
                "app": "hot_key_manager",
                "name": "BindX",
                "hotkey": "CTRL+ALT+J",
                "enabled": False,
                "_runtime_profile": {},
            },
        ],
    },
    "mouse": {"mappings": [], "mouse_mappings": []},
}
config_store.CONFIG_FILE.write_text(json.dumps(SYNTH_CONFIG, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"[e2e] temp config: {config_store.CONFIG_FILE}", flush=True)


def wait_for(pred, timeout=10.0, what="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError("timeout waiting for: " + what)


def entries_by_hotkey(manager):
    return {e["hotkey"].upper(): e for e in manager.entries}

from core.controller import BindXController

import math

cycles = int(os.environ.get("BINDX_E2E_CYCLES", "30"))
print(f"[e2e] crash cycles: {cycles}", flush=True)

for i in range(1, cycles + 1):
    ctrl = None
    try:
        ctrl = BindXController()
        em = entries_by_hotkey(ctrl.hotkey_manager)
        for hkkey in ("CTRL+ALT+B", "CTRL+ALT+V", "CTRL+ALT+K"):
            wait_for(lambda: em[hkkey].get("registered") is True, 10.0, f"init register {hkkey}")

        kb_up = {
            "mappings": [{"trigger": ["ctrl", "alt", "g"], "output": ["ctrl", "alt", "g"], "enabled": True}],
            "mouse_mappings": [],
        }
        kb_down = {"mappings": [], "mouse_mappings": []}
        ctrl.trigger_engine.update_mouse_config(kb_up)
        wait_for(lambda: ctrl.trigger_engine._active_kb is True, 8.0, f"cycle {i} kb up")

        ctrl.trigger_engine.update_mouse_config(kb_down)
        wait_for(lambda: ctrl.trigger_engine._active_kb is False, 8.0, f"cycle {i} kb down")

        ctrl.trigger_engine.update_mouse_config({
            "mappings": [],
            "mouse_mappings": [{"button": "x1", "output": ["ctrl", "w"], "enabled": True}],
        })
        ctrl.trigger_engine.set_enabled(mouse_enabled=True)
        wait_for(lambda: ctrl.trigger_engine._active_mouse is True, 8.0, f"cycle {i} mouse up")

        ctrl.trigger_engine.set_enabled(mouse_enabled=False)
        ctrl.trigger_engine.update_mouse_config(kb_down)
        wait_for(lambda: ctrl.trigger_engine._active_mouse is False, 8.0, f"cycle {i} mouse down")

        ctrl.quit()
        print(f"[e2e] cycle {i}/{cycles} OK", flush=True)
    finally:
        if ctrl is not None:
            try:
                ctrl.quit()
            except Exception:
                pass
        time.sleep(0.2)

print("CYCLES ALL OK", flush=True)
