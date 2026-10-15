# -*- coding: utf-8 -*-
"""config_sync 单文件 Git 同步测试（需要本机 git；无 git 时跳过）。

用临时目录构造「bare origin + clone」验证：
- 上传只在远端 config 分支上生成一个只含配置文件的提交；
- 上传不触碰工作区、不移动 main；
- 拉取把远端版本原子恢复到本地并保留 .bak；
- 远端无分支 / 远端内容非法时的错误路径。
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from core import config_sync


def _git(cwd, *args, check=True, input_bytes=None):
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd),
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(
            "git %s failed: %s" % (" ".join(args[:3]), proc.stderr.decode("utf-8", "replace"))
        )
    return proc


def _git_commit(cwd, *args):
    return _git(cwd, "-c", "user.name=Test", "-c", "user.email=test@example.com", *args)


@unittest.skipIf(shutil.which("git") is None, "git not available")
class ConfigSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="bindx-sync-test-")
        self.origin = os.path.join(self._tmp.name, "origin.git")
        self.repo = os.path.join(self._tmp.name, "clone")
        _git(self._tmp.name, "init", "--bare", self.origin)
        _git(self._tmp.name, "clone", self.origin, self.repo)
        data = os.path.join(self.repo, "data")
        os.makedirs(data, exist_ok=True)
        self.cfg_path = os.path.join(data, "bindx_config.json")
        self.cfg_v1 = {
            "app": {"hotkey_running": True, "mouse_running": True},
            "hotkeys": {"display_name": "v1", "mutex_name": "m", "entries": []},
            "mouse": {"mappings": [], "mouse_mappings": []},
        }
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            json.dump(self.cfg_v1, f, ensure_ascii=False)
        _git(self.repo, "add", "data/bindx_config.json")
        _git_commit(self.repo, "commit", "-m", "init")
        _git(self.repo, "push", "origin", "HEAD:main")

    def tearDown(self):
        self._tmp.cleanup()

    def _remote_config(self):
        out = _git(self.repo, "show", "origin/config:data/bindx_config.json").stdout.decode("utf-8")
        return json.loads(out)

    def _read_cfg(self):
        with open(self.cfg_path, "r", encoding="utf-8") as f:
            return f.read()

    def test_upload_creates_branch_with_only_config(self):
        self.assertIsNone(config_sync.remote_status(repo_root=self.repo))
        result = config_sync.upload_config(repo_root=self.repo)
        self.assertTrue(result["sha"])
        self.assertEqual(self._remote_config(), self.cfg_v1)
        files = _git(self.repo, "ls-tree", "-r", "--name-only", "origin/config").stdout.decode().split()
        self.assertEqual(files, ["data/bindx_config.json"])

    def test_upload_twice_is_fast_forward(self):
        first = config_sync.upload_config(repo_root=self.repo)["sha"]
        config_sync.upload_config(repo_root=self.repo)
        log = _git(self.repo, "log", "-2", "--format=%H %P", "origin/config").stdout.decode().splitlines()
        self.assertEqual(len(log), 2)
        self.assertEqual(log[1].split()[0], first)
        self.assertEqual(log[0].split()[1], log[1].split()[0])

    def test_upload_does_not_touch_working_tree_or_main(self):
        other = os.path.join(self.repo, "other.txt")
        with open(other, "w", encoding="utf-8") as f:
            f.write("dirty")
        head_before = _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip()
        config_sync.upload_config(repo_root=self.repo)
        with open(other, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "dirty")
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.decode().strip(), head_before)
        status = _git(self.repo, "status", "--porcelain").stdout.decode()
        self.assertIn("other.txt", status)

    def test_download_restores_remote_version_and_keeps_bak(self):
        config_sync.upload_config(repo_root=self.repo)
        original = self._read_cfg()
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write(original.replace("v1", "local-edit"))
        config_sync.download_config(repo_root=self.repo)
        self.assertEqual(self._read_cfg(), original)
        with open(self.cfg_path + ".bak", "r", encoding="utf-8") as f:
            self.assertIn("local-edit", f.read())

    def test_download_requires_remote_branch(self):
        with self.assertRaises(config_sync.ConfigSyncError):
            config_sync.download_config(repo_root=self.repo)

    def test_download_rejects_invalid_remote_content(self):
        config_sync.upload_config(repo_root=self.repo)
        blob = _git(
            self.repo, "hash-object", "-w", "--stdin", input_bytes=b"{ not valid json"
        ).stdout.decode().strip()
        base = _git(self.repo, "rev-parse", "origin/config").stdout.decode().strip()
        fd, idx = tempfile.mkstemp(suffix=".idx")
        os.close(fd)
        os.unlink(idx)  # git requires the index path to not pre-exist
        env = dict(os.environ, GIT_INDEX_FILE=idx)

        def g(*args):
            return subprocess.run(
                ["git"] + list(args), cwd=self.repo, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout.decode().strip()

        try:
            g("read-tree", base)
            g("update-index", "--add", "--cacheinfo", "100644,%s,data/bindx_config.json" % blob)
            tree = g("write-tree")
            commit = subprocess.run(
                ["git", "-c", "user.name=T", "-c", "user.email=t@t",
                 "commit-tree", tree, "-p", base, "-m", "bad"],
                cwd=self.repo, env=env,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            ).stdout.decode().strip()
        finally:
            os.unlink(idx)
        _git(self.repo, "update-ref", "refs/heads/config", commit)
        _git(self.repo, "push", "origin", "config")
        before = self._read_cfg()
        with self.assertRaises(config_sync.ConfigSyncError):
            config_sync.download_config(repo_root=self.repo)
        self.assertEqual(self._read_cfg(), before)


if __name__ == "__main__":
    unittest.main()