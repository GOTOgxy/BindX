# -*- coding: utf-8 -*-

"""hookd 主进程侧：子进程生命周期管理 + TriggerEngine 接口门面。

- HookHost：拉起 core.hookd 子进程，维护心跳监控；子进程崩溃/挂死
  时自动拉起并重放配置。子进程挂死时 Windows 会自动卸载其钩子
  （fail-open），用户输入不中断。
- HookEngineFacade：给 controller/GUI 一个与 TriggerEngine 同接口的
  门面：配置变更全量推送子进程，状态属性镜像子进程回报。
"""

import json
import os
import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
STDERR_LOG = PROJECT_DIR / "data" / "bindx_hookd_stderr.log"

DEFAULT_HB_TIMEOUT = 8.0
DEFAULT_MONITOR_INTERVAL = 1.0
MAX_BACKOFF = 15.0
START_GRACE = 15.0
CREATE_NO_WINDOW = 0x08000000
HOST_LOG = PROJECT_DIR / "data" / "bindx_hook_host.log"
FAIL_WINDOW = 120.0
FAIL_LIMIT = 5


class HookHost:
    """hookd 子进程生命周期管理（拉起/心跳/自动重启/配置重放）。"""

    def __init__(self, start_cmd=None, cwd=None, hb_timeout=DEFAULT_HB_TIMEOUT,
                 monitor_interval=DEFAULT_MONITOR_INTERVAL,
                 stderr_path=STDERR_LOG, host_log=None):
        self._start_cmd = start_cmd or [sys.executable, "-m", "core.hookd"]
        self._cwd = str(cwd or PROJECT_DIR)
        self._hb_timeout = float(hb_timeout)
        self._monitor_interval = float(monitor_interval)
        self._stderr_path = Path(stderr_path)
        # 宿主日志默认与 stderr 日志同目录（测试注入 tmp stderr_path 时
        # 自动隔离到 tmp，不会污染 data/）
        self._host_log_path = (
            Path(host_log)
            if host_log is not None
            else self._stderr_path.parent / "bindx_hook_host.log"
        )

        self._proc = None
        self._proc_lock = threading.RLock()
        self._spawn_time = 0.0
        self._stopping = False
        self._ready = threading.Event()
        self._last_hb = 0.0
        self._backoff = 0.2
        self._fail_window = []

        self._config = None
        self._force = False
        self._config_lock = threading.Lock()

        self._events = []
        self._events_lock = threading.Lock()

        self._status = {
            "running": False, "active_kb": False, "active_mouse": False,
            "last_error": None, "last_event": "无",
        }
        self._status_lock = threading.Lock()

        self._log_result = None
        self._log_wait = threading.Event()
        self._log_lock = threading.Lock()

        self._monitor = None
        self._reader = None

    # ---------- 公共接口 ----------

    def start(self):
        if self._monitor is not None and self._monitor.is_alive():
            return
        self._stopping = False
        with self._proc_lock:
            if self._proc is None:
                self._spawn()
        self._monitor = threading.Thread(
            target=self._monitor_loop, daemon=True, name="hookd-monitor"
        )
        self._monitor.start()

    def apply_config(self, payload, force=False):
        with self._config_lock:
            self._config = payload
            self._force = force
            ready = self._ready.is_set()
        if ready:
            self._send({"type": "config", "payload": payload, "force": force})

    def pop_hotkey_events(self):
        with self._events_lock:
            events = list(self._events)
            self._events.clear()
        return events

    def get_status(self):
        with self._status_lock:
            return dict(self._status)

    def request_log(self, timeout=2.0):
        with self._log_lock:
            self._log_wait.clear()
            self._send({"type": "req_log"})
            if self._log_wait.wait(timeout):
                return self._log_result or []
            return self._log_result or []

    def shutdown(self, timeout=3.0):
        self._stopping = True
        with self._proc_lock:
            proc = self._proc
            self._proc = None
        self._ready.clear()
        if proc is not None and proc.poll() is None:
            self._send_to(proc, {"type": "quit"})
            try:
                proc.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    proc.kill()
                except Exception:
                    pass
                try:
                    proc.wait(timeout=2.0)
                except Exception:
                    pass

    # ---------- 内部实现 ----------

    def _host_log(self, message):
        # 宿主侧生命周期日志：旧版 reader/monitor 全部 except: pass，
        # 重启循环完全不可见
        try:
            self._host_log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._host_log_path, "a", encoding="utf-8") as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n")
        except Exception:
            pass

    def _fail_storm(self):
        # 重启风暴保护：FAIL_WINDOW 秒内子进程失败超过 FAIL_LIMIT 次即
        # 停止自动重启并暴露错误（此前子进程反复死 → 反复拉起，
        # 进程churn 在桌面上表现为沙漏光标无限循环出现/消失）。
        now = time.monotonic()
        self._fail_window = [
            t for t in self._fail_window if now - t < FAIL_WINDOW
        ]
        self._fail_window.append(now)
        if len(self._fail_window) <= FAIL_LIMIT:
            return False
        self._host_log(
            f"hookd failed {len(self._fail_window)} times within "
            f"{FAIL_WINDOW:.0f}s; auto-respawn stopped"
        )
        with self._status_lock:
            self._status["running"] = False
            self._status["last_error"] = (
                f"hookd 子进程 {FAIL_WINDOW:.0f}s 内失败 "
                f"{len(self._fail_window)} 次，已停止自动重启，"
                "详见 data/bindx_hook_host.log"
            )
        self._ready.clear()
        self._stopping = True
        return True

    def _spawn(self):
        if self._stopping:
            return
        self._ready.clear()
        self._spawn_time = time.monotonic()
        stderr_file = subprocess.DEVNULL
        try:
            self._stderr_path.parent.mkdir(parents=True, exist_ok=True)
            stderr_file = open(self._stderr_path, "ab")
        except OSError:
            stderr_file = subprocess.DEVNULL
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        creationflags = CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            proc = subprocess.Popen(
                self._start_cmd,
                cwd=self._cwd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=stderr_file,
                env=env,
                creationflags=creationflags,
                close_fds=True,
            )
        except Exception:
            if stderr_file is not subprocess.DEVNULL:
                try:
                    stderr_file.close()
                except Exception:
                    pass
            return
        if stderr_file is not subprocess.DEVNULL:
            # 子进程已继承句柄，父进程侧关闭
            try:
                stderr_file.close()
            except Exception:
                pass
        with self._proc_lock:
            self._proc = proc
        self._reader = threading.Thread(
            target=self._reader_loop, args=(proc,), daemon=True,
            name="hookd-reader",
        )
        self._reader.start()

    def _kill_proc(self):
        with self._proc_lock:
            proc = self._proc
            self._proc = None
        self._ready.clear()
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except Exception:
                pass
            try:
                proc.wait(timeout=2.0)
            except Exception:
                pass
        if proc is not None:
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except Exception:
                    pass

    def _send(self, obj):
        with self._proc_lock:
            proc = self._proc
        self._send_to(proc, obj)

    @staticmethod
    def _send_to(proc, obj):
        if proc is None or proc.poll() is not None or proc.stdin is None:
            return
        try:
            proc.stdin.write(
                (json.dumps(obj, ensure_ascii=False) + "\n").encode("utf-8")
            )
            proc.stdin.flush()
        except Exception:
            pass

    def _reader_loop(self, proc):
        reader_error = None
        try:
            for raw in proc.stdout:
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    msg = json.loads(raw.decode("utf-8"))
                except Exception:
                    continue
                try:
                    self._on_message(msg)
                except Exception as exc:
                    self._host_log(f"hookd message handling error: {exc!r}")
        except Exception:
            reader_error = traceback.format_exc()
        try:
            child_dead = proc.poll() is not None
        except Exception:
            child_dead = True
        if reader_error is not None:
            self._host_log(
                f"hookd reader loop exited (pid={proc.pid}, child_dead={child_dead}):\n"
                f"{reader_error}"
            )
        if child_dead:
            # 子进程已退出：摘除引用，由监控循环负责重启
            with self._proc_lock:
                if self._proc is proc:
                    self._proc = None
            self._ready.clear()
            for stream in (proc.stdin, proc.stdout, proc.stderr):
                try:
                    if stream is not None:
                        stream.close()
                except Exception:
                    pass
        # 子进程仍存活但 reader 线程异常退出：绝不能关 proc.stdin
        # （旧版无条件关 stdin → 子进程收 EOF → 静默 exit 0 → 监控再拉起
        # → 无限重启循环）。此情形下留给监控循环的心跳超时自愈。

    def _on_message(self, msg):
        mtype = msg.get("type")
        if mtype == "ready":
            self._backoff = 0.2
            with self._config_lock:
                cfg = self._config
                force = self._force
            if cfg is not None:
                self._send({"type": "config", "payload": cfg, "force": force})
            self._ready.set()
        elif mtype == "hb":
            self._last_hb = time.monotonic()
            self._backoff = 0.2
        elif mtype == "status":
            payload = msg.get("payload") or {}
            with self._status_lock:
                self._status = {
                    "running": bool(payload.get("running")),
                    "active_kb": bool(payload.get("active_kb")),
                    "active_mouse": bool(payload.get("active_mouse")),
                    "last_error": payload.get("last_error"),
                    "last_event": payload.get("last_event", "无"),
                }
        elif mtype == "event":
            entry_id = (msg.get("payload") or {}).get("entry_id")
            if isinstance(entry_id, int):
                with self._events_lock:
                    self._events.append(entry_id)
        elif mtype == "log":
            with self._log_lock:
                self._log_result = msg.get("payload") or []
                self._log_wait.set()
        elif mtype == "exit":
            pass

    def _monitor_loop(self):
        while True:
            if self._stopping:
                return
            time.sleep(self._monitor_interval)
            if self._stopping:
                return
            with self._proc_lock:
                proc = self._proc
            if proc is None:
                self._spawn()
                continue
            if proc.poll() is not None:
                was_ready = self._ready.is_set()
                alive = time.monotonic() - self._spawn_time
                self._host_log(
                    f"hookd exited: code={proc.returncode}, "
                    f"alive={alive:.1f}s, was_ready={was_ready}"
                )
                self._kill_proc()
                if self._stopping:
                    return
                if self._fail_storm():
                    return
                delay = 0.2 if was_ready else self._backoff
                time.sleep(delay)
                self._backoff = min(self._backoff * 2.0, MAX_BACKOFF)
                self._spawn()
                continue
            if self._ready.is_set():
                if (self._last_hb
                        and time.monotonic() - self._last_hb > self._hb_timeout):
                    # 心跳超时（子进程挂死）：杀掉重启；
                    # Windows 已自动卸载挂死进程的钩子（fail-open）
                    self._host_log(
                        f"hookd heartbeat timeout >"
                        f"{self._hb_timeout:.0f}s; kill & respawn"
                    )
                    self._kill_proc()
                    if self._stopping:
                        return
                    if self._fail_storm():
                        return
                    time.sleep(self._backoff)
                    self._backoff = min(self._backoff * 2.0, MAX_BACKOFF)
                    self._spawn()
            elif time.monotonic() - self._spawn_time > START_GRACE:
                # 迟迟收不到 ready（启动失败/卡死）：杀掉重启
                self._host_log(
                    "hookd not ready within grace period; kill & respawn"
                )
                self._kill_proc()
                if not self._stopping and not self._fail_storm():
                    self._spawn()


class HookEngineFacade:
    """TriggerEngine 的进程隔离门面（controller/GUI 直接替换用）。

    所有配置变更全量推送 hookd 子进程；状态属性实时镜像
    子进程回报。子进程内才是真正的 TriggerEngine。
    """

    def __init__(self, host):
        self._host = host
        self._hotkey_manager = None
        self._kb_enabled = False
        self._mouse_enabled = False
        self._mouse_config = {"mappings": [], "mouse_mappings": []}
        self._delay_ms = 20
        self._restore = True

    # ---------- 状态镜像 ----------

    @property
    def running(self):
        return self._host.get_status()["running"]

    @property
    def last_error(self):
        return self._host.get_status()["last_error"]

    @property
    def last_event(self):
        return self._host.get_status()["last_event"]

    @property
    def _active_kb(self):
        return self._host.get_status()["active_kb"]

    @property
    def _active_mouse(self):
        return self._host.get_status()["active_mouse"]

    @property
    def heartbeat(self):
        return self._host._last_hb

    # ---------- 配置推送 ----------

    @property
    def hotkey_manager(self):
        return self._hotkey_manager

    @hotkey_manager.setter
    def hotkey_manager(self, manager):
        self._hotkey_manager = manager
        self._push()

    def _payload(self):
        hotkeys = []
        if self._hotkey_manager is not None:
            for entry in self._hotkey_manager.entries:
                hotkeys.append({
                    "id": entry.get("id"),
                    "hotkey": entry.get("hotkey", ""),
                    "modifiers": entry.get("modifiers", 0),
                    "virtual_key": entry.get("virtual_key", 0),
                    "enabled": entry.get("enabled", True),
                })
        return {
            "keyboard_enabled": self._kb_enabled,
            "mouse_enabled": self._mouse_enabled,
            "output_delay_ms": self._delay_ms,
            "restore_held_modifiers": self._restore,
            "hotkeys": hotkeys,
            "mouse_config": self._mouse_config,
        }

    def _push(self, force=False):
        self._host.apply_config(self._payload(), force=force)

    # ---------- TriggerEngine 同接口方法 ----------

    def set_enabled(self, keyboard_enabled=None, mouse_enabled=None):
        if keyboard_enabled is not None:
            self._kb_enabled = bool(keyboard_enabled)
        if mouse_enabled is not None:
            self._mouse_enabled = bool(mouse_enabled)
        self._push()

    def update_mouse_config(self, config):
        self._mouse_config = config or {"mappings": [], "mouse_mappings": []}
        self._push()

    def set_output_options(self, delay_ms=None, restore_held_modifiers=None):
        if delay_ms is not None:
            try:
                self._delay_ms = int(delay_ms)
            except (TypeError, ValueError):
                self._delay_ms = 20
        if restore_held_modifiers is not None:
            self._restore = bool(restore_held_modifiers)
        self._push()

    def notify_hotkeys_changed(self):
        self._push()

    def reinstall_hooks(self):
        self._push(force=True)

    def pop_hotkey_events(self):
        return self._host.pop_hotkey_events()

    def export_event_log(self):
        return self._host.request_log()

    def shutdown(self):
        self._host.shutdown()
