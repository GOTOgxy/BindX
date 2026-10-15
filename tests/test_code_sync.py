# -*- coding: utf-8 -*-
"""code_sync 代码整仓 Git 同步测试（依赖 git；无 git 时跳过）。

临时目录内搭建 bare origin + clone，验证：
- 上传代码会提交工作区改动并推送到远端 main；
- 被 .gitignore 忽略的配置文件永远不会进入提交，本地文件也不被改动；
- 没有改动时不产生空提交；
- 下载代码把本地更新到远端最新；已最新时 updated=False；
- 本地有未提交改动时拒绝下载（防止丢失），本地内容保留；
- 远端有新提交（无冲突）时，上传能自动 rebase 后推送成功；
- code_status 正确报告领先/落后。
"""

import os
import shutil
import subprocess
import tempfile
import unittest

from core import code_sync


def _git(cwd, *args, check=True):
    proc = subprocess.run(
        ["git"] + list(args),
        cwd=str(cwd),
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


def _clone_second(tmp_dir, origin, name="clone2"):
    second = os.path.join(tmp_dir, name)
    _git(tmp_dir, "clone", origin, second)
    return second


@unittest.skipIf(shutil.which("git") is None, "git not available")
class CodeSyncTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="bindx-code-test-")
        self.origin = os.path.join(self._tmp.name, "origin.git")
        self.repo = os.path.join(self._tmp.name, "clone")
        _git(self._tmp.name, "init", "--bare", self.origin)
        _git(self._tmp.name, "clone", self.origin, self.repo)
        data = os.path.join(self.repo, "data")
        os.makedirs(data, exist_ok=True)
        with open(os.path.join(self.repo, ".gitignore"), "w", encoding="utf-8") as f:
            f.write(
                "__pycache__/\n*.pyc\ndata/bindx_config.json\n"
                "data/bindx_config.json.bak\n"
            )
        self.cfg_path = os.path.join(data, "bindx_config.json")
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write('{"hotkeys": []}\n')
        self.code_path = os.path.join(self.repo, "code.txt")
        with open(self.code_path, "w", encoding="utf-8") as f:
            f.write("v1\n")
        _git(self.repo, "add", "-A")
        _git_commit(self.repo, "commit", "-m", "init")
        _git(self.repo, "push", "origin", "HEAD:main")
        _git(self.origin, "symbolic-ref", "HEAD", "refs/heads/main")
        _git(self.repo, "checkout", "-B", "main")

    def tearDown(self):
        self._tmp.cleanup()

    def _remote_file(self, name="code.txt"):
        return _git(self.repo, "show", "origin/main:" + name).stdout.decode("utf-8")

    def _push_from_second(self, filename, content):
        second = _clone_second(self._tmp.name, self.origin)
        path = os.path.join(second, filename)
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        _git(second, "add", "-A")
        _git_commit(second, "commit", "-m", "other machine")
        _git(second, "push", "origin", "main")

    def test_push_commits_and_pushes(self):
        with open(self.code_path, "a", encoding="utf-8") as f:
            f.write("v2\n")
        new_file = os.path.join(self.repo, "new_module.py")
        with open(new_file, "w", encoding="utf-8") as f:
            f.write("print('hi')\n")
        result = code_sync.push_code(repo_root=self.repo)
        self.assertTrue(result["committed"])
        self.assertTrue(result["sha"])
        self.assertIn("code.txt", result["files"])
        self.assertIn("new_module.py", result["files"])
        self.assertEqual(self._remote_file(), "v1\nv2\n")
        self.assertEqual(self._remote_file("new_module.py"), "print('hi')\n")

    def test_push_never_commits_ignored_config(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write('{"hotkeys": [{"k": "changed"}]}\n')
        with open(self.code_path, "a", encoding="utf-8") as f:
            f.write("x\n")
        result = code_sync.push_code(repo_root=self.repo)
        self.assertTrue(result["committed"])
        for name in result["files"]:
            self.assertNotIn("bindx_config", name)
        files = _git(
            self.repo, "ls-tree", "-r", "--name-only", "origin/main"
        ).stdout.decode().splitlines()
        self.assertNotIn("data/bindx_config.json", files)
        with open(self.cfg_path, "r", encoding="utf-8") as f:
            self.assertIn("changed", f.read())

    def test_push_only_config_changed_is_noop(self):
        with open(self.cfg_path, "w", encoding="utf-8") as f:
            f.write('{"hotkeys": [{"k": "changed"}]}\n')
        head_before = _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip()
        result = code_sync.push_code(repo_root=self.repo)
        self.assertFalse(result["committed"])
        self.assertEqual(
            _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip(), head_before
        )

    def test_push_noop_when_clean(self):
        head_before = _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip()
        result = code_sync.push_code(repo_root=self.repo)
        self.assertFalse(result["committed"])
        self.assertEqual(
            _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip(), head_before
        )

    def test_pull_updates_to_remote(self):
        self._push_from_second("code.txt", "from-other-machine\n")
        result = code_sync.pull_code(repo_root=self.repo)
        self.assertTrue(result["updated"])
        with open(self.code_path, "r", encoding="utf-8") as f:
            self.assertIn("from-other-machine", f.read())
        self.assertEqual(
            _git(self.repo, "rev-parse", "HEAD").stdout.decode().strip(),
            _git(self.repo, "rev-parse", "origin/main").stdout.decode().strip(),
        )

    def test_pull_up_to_date(self):
        result = code_sync.pull_code(repo_root=self.repo)
        self.assertFalse(result["updated"])

    def test_pull_refuses_dirty_worktree(self):
        self._push_from_second("code.txt", "remote-change\n")
        with open(self.code_path, "a", encoding="utf-8") as f:
            f.write("local-unsaved\n")
        with self.assertRaises(code_sync.CodeSyncError):
            code_sync.pull_code(repo_root=self.repo)
        with open(self.code_path, "r", encoding="utf-8") as f:
            self.assertIn("local-unsaved", f.read())

    def test_push_rebases_over_remote_changes(self):
        self._push_from_second("other.txt", "remote-only\n")
        with open(self.code_path, "a", encoding="utf-8") as f:
            f.write("local-change\n")
        result = code_sync.push_code(repo_root=self.repo)
        self.assertTrue(result["committed"])
        self.assertEqual(self._remote_file("other.txt"), "remote-only\n")
        self.assertIn("local-change", self._remote_file())

    def test_code_status_ahead_behind(self):
        info = code_sync.code_status(repo_root=self.repo)
        self.assertIsNotNone(info)
        self.assertEqual(info["ahead"], 0)
        self.assertEqual(info["behind"], 0)
        self._push_from_second("other.txt", "x\n")
        info = code_sync.code_status(repo_root=self.repo)
        self.assertEqual(info["ahead"], 0)
        self.assertEqual(info["behind"], 1)


if __name__ == "__main__":
    unittest.main()