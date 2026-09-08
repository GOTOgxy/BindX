# -*- coding: utf-8 -*-

"""BindX hookd：钩子隔离子进程入口。

主进程（UI + 原生热键轮询）与低级钩子（WH_KEYBOARD_LL / WH_MOUSE_LL）
彻底分进程：

- 子进程内运行 TriggerEngine，仅在存在"无修饰键热键"或"启用的
  按键/鼠标映射"时才安装对应钩子。
- 子进程崩溃时，Windows 会自动卸载其钩子（fail-open，用户输入
  立即恢复）；主进程 HookHost 通过心跳检测并自动拉起、重放配置。
- 子进程不持有任何 UI 状态；诊断日志仍写 data/bindx_hook_error.log。

协议（stdin/stdout JSON Lines，UTF-8）：

    主 -> 子:  {"type": "config", "payload": {...}, "force": bool}
               {"type": "req_log"}
               {"type": "quit"}
    子 -> 主:  {"type": "ready"}
               {"type": "hb"}
               {"type": "status", "payload": {...}}
               {"type": "event", "payload": {"kind": "hotkey", "entry_id": N}}
               {"type": "log", "payload": [...]}
               {"type": "exit"}
"""

import json
import sys
import threading
import time

HB_INTERVAL = 2.0
EVENT_POLL_INTERVAL = 0.1


class _HookdManager:
    """TriggerEngine 所需 hotkey_manager 的最小替身。

    引擎只读 ``entries``、只写 ``external_trigger_active``；
    带修饰键热键的注册状态归主进程原生 RegisterHotKey 所有，
    子进程只关心无修饰键热键列表。
    """

    def __init__(self):
        self.entries = []
        self.external_trigger_active = False


def _build_entries(payload):
    entries = []
    for hk in payload.get("hotkeys", []) or []:
        try:
            entries.append({
                "id": int(hk["id"]),
                "hotkey": hk.get("hotkey", ""),
                "modifiers": int(hk.get("modifiers", 0)),
                "virtual_key": int(hk.get("virtual_key", 0)),
                "enabled": bool(hk.get("enabled", True)),
                "registered": False,
                "last_error": None,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return entries


def _status_payload(engine):
    if engine is None:
        return {
            "running": False, "active_kb": False, "active_mouse": False,
            "last_error": None, "last_event": "无",
        }
    return {
        "running": bool(engine.running),
        "active_kb": bool(engine._active_kb),
        "active_mouse": bool(engine._active_mouse),
        "last_error": engine.last_error,
        "last_event": engine.last_event,
    }


def main():
    from . import config_proxy
    from .trigger_engine import TriggerEngine

    config_proxy.init_subprojects()

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except Exception:
        pass

    send_lock = threading.Lock()

    def send(obj):
        line = json.dumps(obj, ensure_ascii=False)
        with send_lock:
            sys.stdout.write(line + "\n")
            sys.stdout.flush()

    send({"type": "ready"})

    manager = _HookdManager()
    engine = None
    stop = threading.Event()

    def heartbeat_loop():
        while not stop.wait(HB_INTERVAL):
            send({"type": "hb"})

    def event_loop():
        while not stop.wait(EVENT_POLL_INTERVAL):
            if engine is None:
                continue
            try:
                for entry_id in engine.pop_hotkey_events():
                    send({
                        "type": "event",
                        "payload": {"kind": "hotkey", "entry_id": entry_id},
                    })
            except Exception:
                pass

    last_status = None

    def status_loop():
        nonlocal last_status
        # 需要的钩子由 _run 线程异步安装，apply_config 里的状态
        # 回报可能比安装更早；这里持续观测引擎真实状态，变化即重报
        # （安装成功/失败/被看门狗卸载）。
        while not stop.wait(0.5):
            if engine is None:
                continue
            try:
                payload = _status_payload(engine)
            except Exception:
                continue
            if payload != last_status:
                last_status = payload
                send({"type": "status", "payload": payload})

    threading.Thread(target=heartbeat_loop, daemon=True).start()
    threading.Thread(target=event_loop, daemon=True).start()
    threading.Thread(target=status_loop, daemon=True).start()

    def apply_config(payload, force):
        nonlocal engine
        nonlocal last_status
        manager.entries = _build_entries(payload)
        mouse_config = payload.get("mouse_config") or {
            "mappings": [], "mouse_mappings": []
        }
        delay_ms = payload.get("output_delay_ms")
        restore = payload.get("restore_held_modifiers")
        if engine is None:
            engine = TriggerEngine(manager, mouse_config)
            if delay_ms is not None:
                engine.set_output_options(delay_ms=delay_ms)
            if restore is not None:
                engine.set_output_options(restore_held_modifiers=restore)
            engine.set_enabled(
                keyboard_enabled=payload.get("keyboard_enabled", False),
                mouse_enabled=payload.get("mouse_enabled", False),
            )
        else:
            if delay_ms is not None:
                engine.set_output_options(delay_ms=delay_ms)
            if restore is not None:
                engine.set_output_options(restore_held_modifiers=restore)
            engine.update_mouse_config(mouse_config)
            engine.set_enabled(
                keyboard_enabled=payload.get("keyboard_enabled"),
                mouse_enabled=payload.get("mouse_enabled"),
            )
            if force:
                engine.reinstall_hooks()
        _sp = _status_payload(engine)
        last_status = _sp
        send({"type": "status", "payload": _sp})

    for raw in sys.stdin.buffer:
        if stop.is_set():
            break
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw.decode("utf-8"))
        except Exception:
            continue
        mtype = msg.get("type")
        if mtype == "config":
            try:
                apply_config(msg.get("payload") or {}, bool(msg.get("force")))
            except Exception as exc:
                payload = _status_payload(None)
                payload["last_error"] = "hookd config failed: %r" % (exc,)
                send({"type": "status", "payload": payload})
        elif mtype == "req_log":
            payload = []
            if engine is not None:
                try:
                    payload = engine.export_event_log()
                except Exception:
                    payload = []
            send({"type": "log", "payload": payload})
        elif mtype == "quit":
            break

    stop.set()
    if engine is not None:
        try:
            engine.shutdown()
        except Exception:
            pass
    send({"type": "exit"})
    return 0


if __name__ == "__main__":
    sys.exit(main())
