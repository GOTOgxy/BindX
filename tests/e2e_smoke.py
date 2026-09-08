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

import ctypes

user32 = ctypes.windll.user32

from core.controller import BindXController

ctrl = None
try:
    # ---------- (a) controller 初始化：子进程起来，原生热键注册 ----------
    ctrl = BindXController()
    time.sleep(1.0)
    fe = ctrl.trigger_engine
    assert fe.running is False, f"expected child idle, got running=True: {fe.get_status() if hasattr(fe,'get_status') else ''}"
    assert fe._active_kb is False and fe._active_mouse is False
    em = entries_by_hotkey(ctrl.hotkey_manager)
    for hk in ("CTRL+ALT+B", "CTRL+ALT+V", "CTRL+ALT+K"):
        wait_for(lambda: em[hk].get("registered") is True, 10.0, f"native register {hk}")
    assert em["CTRL+ALT+J"].get("registered") in (False, None), "disabled entry must not register"
    ctrl.process_hotkeys()
    print("[e2e] (a) controller init OK", flush=True)

    # ---------- (b) 进程内真实 TriggerEngine：键盘/鼠标钩子装/卸 ----------
    from core import config_proxy
    from core.trigger_engine import TriggerEngine
    hk = config_proxy.hk_module()
    eng_cfg = hk.load_config()
    mgr = hk.HotkeyManager(eng_cfg)
    kb_mapping = {"trigger": ["ctrl", "alt", "g"], "output": ["ctrl", "alt", "g"], "enabled": True}
    eng = TriggerEngine(mgr, {"mappings": [kb_mapping], "mouse_mappings": []})
    try:
        eng.set_enabled(keyboard_enabled=True)
        wait_for(lambda: eng.running and eng._active_kb, 10.0, "kb hook installed")
        assert not eng._active_mouse
        print("[e2e] (b1-b2) kb hook up OK", flush=True)

        eng.update_mouse_config({"mappings": [], "mouse_mappings": []})
        eng.set_enabled(keyboard_enabled=False)
        wait_for(lambda: not eng.running, 10.0, "kb hook uninstalled")
        print("[e2e] (b3) kb hook down OK", flush=True)

        eng.update_mouse_config({
            "mappings": [],
            "mouse_mappings": [{"button": "x1", "output": ["ctrl", "w"], "enabled": True}],
        })
        eng.set_enabled(mouse_enabled=True)
        wait_for(lambda: eng._active_mouse and not eng._active_kb, 10.0, "mouse hook up")
        print("[e2e] (b4) mouse hook OK", flush=True)
    finally:
        eng.shutdown()
        wait_for(lambda: not eng.running, 10.0, "engine stopped")

    # ---------- (c) 原生 RegisterHotKey 往返（独立 manager + 轮询线程） ----------
    mgr2 = hk.HotkeyManager(hk.load_config())
    mgr2.start_polling_thread(register_enabled=False)
    try:
        wait_for(lambda: mgr2._hwnd is not None, 5.0, "mgr2 msg window")
        time.sleep(0.15)
        e2 = mgr2.add_entry("generic", "CTRL+ALT+G", enabled=True, name="e2e-c")
        wait_for(lambda: e2.get("registered") is True, 10.0, "e2e-c registered")
        mgr2.remove_entry(e2["id"])
        wait_for(lambda: e2["id"] not in mgr2.entry_map, 5.0, "entry removed")

        def _probe_free(mods, vk):
            # remove_entry 先清 entry_map，轮询线程稍后才真正 UnregisterHotKey；
            # 用“同组合临时注册成功”来验证系统层热键确实已释放。
            ctypes.set_last_error(0)
            ok = user32.RegisterHotKey(None, 31337, mods, vk)
            if ok:
                user32.UnregisterHotKey(None, 31337)
            return bool(ok)

        wait_for(lambda: _probe_free(e2["modifiers"], e2["virtual_key"]), 10.0, "hotkey released")
    finally:
        mgr2.stop_polling_thread()
    print("[e2e] (c) native roundtrip OK", flush=True)

    # ---------- (d) start/stop/reload 走门面推送到子进程 ----------
    em = entries_by_hotkey(ctrl.hotkey_manager)
    ctrl.start_hotkey(persist=False)
    for hkkey in ("CTRL+ALT+B", "CTRL+ALT+V", "CTRL+ALT+K"):
        wait_for(lambda: em[hkkey].get("registered") is True, 10.0, f"start: {hkkey}")
    assert fe.running is False
    ctrl.stop_hotkey(persist=False)
    for hkkey in ("CTRL+ALT+B", "CTRL+ALT+V", "CTRL+ALT+K"):
        wait_for(lambda: em[hkkey].get("registered") in (False, None), 10.0, f"stop: {hkkey}")
    ctrl.start_hotkey(persist=False)
    for hkkey in ("CTRL+ALT+B", "CTRL+ALT+V", "CTRL+ALT+K"):
        wait_for(lambda: em[hkkey].get("registered") is True, 10.0, f"start2: {hkkey}")
    print("[e2e] (d1) start/stop/start OK", flush=True)

    old_mgr = ctrl.hotkey_manager
    ctrl.reload_all_config()
    wait_for(lambda: ctrl.hotkey_manager is not old_mgr, 5.0, "manager swapped")
    em = entries_by_hotkey(ctrl.hotkey_manager)
    for hkkey in ("CTRL+ALT+B", "CTRL+ALT+V", "CTRL+ALT+K"):
        wait_for(lambda: em[hkkey].get("registered") is True, 10.0, f"reload: {hkkey}")
    assert fe.running is False
    ctrl.process_hotkeys()
    print("[e2e] (d2) reload_all_config OK", flush=True)

    # ---------- (e) 键位重映射 → 子进程真装 LL 键盘钩子；崩溃自愈 ----------
    kb_up = {
        "mappings": [{"trigger": ["ctrl", "alt", "g"], "output": ["ctrl", "alt", "g"], "enabled": True}],
        "mouse_mappings": [],
    }
    kb_down = {"mappings": [], "mouse_mappings": []}
    ctrl.trigger_engine.update_mouse_config(kb_up)
    wait_for(lambda: fe._active_kb is True, 8.0, "child kb hook active")
    assert fe.running is True
    print("[e2e] (e1) child kb hook up OK", flush=True)

    ctrl.trigger_engine.update_mouse_config(kb_down)
    wait_for(lambda: fe._active_kb is False, 8.0, "child kb hook down")
    print("[e2e] (e2) child kb hook down OK", flush=True)

    proc = ctrl._hook_host._proc
    assert proc is not None
    proc.kill()
    try:
        proc.wait(timeout=5.0)
    except Exception:
        pass
    wait_for(
        lambda: ctrl._hook_host._proc is not None
        and ctrl._hook_host._proc is not proc
        and ctrl._hook_host._proc.poll() is None,
        10.0,
        "hookd respawn after crash",
    )
    print("[e2e] (e3) crash respawn OK", flush=True)

    # ---------- (f) 收尾 ----------
    ctrl.process_hotkeys()
    print("[e2e] (f) process_hotkeys OK", flush=True)
    ctrl.quit()
    time.sleep(0.5)
    print("SMOKE ALL OK", flush=True)
finally:
    if ctrl is not None:
        try:
            ctrl.quit()
        except Exception:
            pass
    time.sleep(0.2)
