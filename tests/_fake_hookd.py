# -*- coding: utf-8 -*-
"""假 hookd：供 test_hook_host.py 验证 HookHost 的监控/重启/重放逻辑。

与 core/hookd.py 相同协议（JSON Lines over stdin/stdout）：
  ready -> status(初始) -> hb(每 0.2s)
  收 config 回 status；payload 含 "nohb": True 时收到 config 后停止心跳（模拟挂死）；
  收 quit 回 exit 并退出。
"""
import json
import sys
import threading

_send_lock = threading.Lock()


def send(obj):
    with _send_lock:
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
        sys.stdout.flush()


def main():
    sys.stdout.reconfigure(line_buffering=True)
    stop = threading.Event()
    nohb = threading.Event()

    send({"type": "ready"})
    send({"type": "status", "payload": {
        "running": True,
        "active_kb": False,
        "active_mouse": False,
        "last_error": None,
        "last_event": "启动",
    }})

    def stdin_loop():
        for raw in sys.stdin:
            raw = raw.strip()
            if not raw:
                continue
            try:
                msg = json.loads(raw)
            except Exception:
                continue
            mtype = msg.get("type")
            if mtype == "config":
                payload = msg.get("payload") or {}
                if payload.get("nohb"):
                    nohb.set()
                send({"type": "status", "payload": {
                    "running": True,
                    "active_kb": bool(payload.get("keyboard_enabled")),
                    "active_mouse": bool(payload.get("mouse_enabled")),
                    "last_error": None,
                    "last_event": "config",
                }})
            elif mtype == "quit":
                send({"type": "exit"})
                stop.set()
                break

    def hb_loop():
        while not stop.is_set():
            if nohb.is_set():
                stop.wait(1.0)
                continue
            stop.wait(0.2)
            if stop.is_set():
                break
            send({"type": "hb"})

    t1 = threading.Thread(target=stdin_loop, daemon=True)
    t2 = threading.Thread(target=hb_loop, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    stop.set()


if __name__ == "__main__":
    main()
