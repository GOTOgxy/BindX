# -*- coding: utf-8 -*-

import sys
import tempfile
import time
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from core.hook_host import HookHost


def _make_host(tmp, **kw):
    defaults = dict(
        start_cmd=[sys.executable, str(HERE / "_fake_hookd.py")],
        cwd=str(HERE),
        hb_timeout=1.5,
        monitor_interval=0.2,
        stderr_path=str(Path(tmp) / "_fake_hookd_stderr.log"),
    )
    defaults.update(kw)
    return HookHost(**defaults)


def wait_for(pred, timeout=6.0, what="condition"):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return
        time.sleep(0.05)
    raise AssertionError("timeout waiting for: " + what)


class HookHostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="bindx_hookhost_")

    def test_ready_status_mirror(self):
        h = _make_host(self.tmp)
        self.addCleanup(h.shutdown)
        h.start()
        wait_for(lambda: h.get_status()["running"] is True, what="fake hookd running status")
        self.assertTrue(h._ready.is_set())

    def test_crash_auto_restart_and_config_replay(self):
        h = _make_host(self.tmp)
        self.addCleanup(h.shutdown)
        h.start()
        wait_for(lambda: h.get_status()["running"] is True, what="first start running")
        h.apply_config({"keyboard_enabled": True, "mouse_enabled": False})
        wait_for(lambda: h.get_status()["active_kb"] is True, what="kb active after config")
        proc = h._proc
        self.assertIsNotNone(proc)
        proc.kill()
        try:
            proc.wait(timeout=5.0)
        except Exception:
            pass
        wait_for(
            lambda: h._proc is not None and h._proc is not proc and h._proc.poll() is None,
            timeout=10.0,
            what="respawn after crash",
        )
        # ready 时自动重放缓存配置 → 状态恢复
        wait_for(lambda: h.get_status()["active_kb"] is True, timeout=10.0, what="kb active after replay")

    def test_hang_kill_and_restart(self):
        h = _make_host(self.tmp)
        self.addCleanup(h.shutdown)
        h.start()
        wait_for(lambda: h.get_status()["running"] is True, what="first start running")
        proc1 = h._proc
        # nohb: 子进程收到 config 后停止心跳 → 挂死 → 被监控线程 kill 重启
        h.apply_config({"keyboard_enabled": True, "mouse_enabled": False, "nohb": True})
        wait_for(lambda: h.get_status()["active_kb"] is True, what="kb active (pre-hang)")
        wait_for(
            lambda: h._proc is not None and h._proc is not proc1 and h._proc.poll() is None,
            timeout=20.0,
            what="respawn after hang-kill",
        )
        try:
            proc1.wait(timeout=5.0)
        except Exception:
            pass


if __name__ == "__main__":
    unittest.main()
