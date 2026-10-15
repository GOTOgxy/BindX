# -*- coding: utf-8 -*-
"""BindX 代码 Git 同步（整个代码仓库的 main 分支）。

与 config_sync 只同步单个配置文件不同，这里同步的是整个代码仓库：

- 上传代码：``git add -A`` → 有改动则自动提交 → ``git pull --rebase`` →
  ``git push origin main``。被 .gitignore 忽略的文件（本地配置、日志等）
  永远不会进入提交。
- 下载代码：要求工作区干净（有未提交改动时请先按「上传代码」），
  然后 ``git pull --rebase`` 把本地更新到远端最新。
- code_status()：查询本地与远端 main 的领先/落后状态，供界面显示。

任何 rebase 冲突都会先执行 ``rebase --abort``，保证仓库回到可用状态。
"""

import socket
from datetime import datetime
from pathlib import Path

from .config_sync import (
    DEFAULT_REPO_ROOT,
    ConfigSyncError,
    _is_rejected_push,
    _require_repo,
    _run_git,
)

REMOTE_REF = "refs/remotes/origin/main"
MAX_PUSH_ATTEMPTS = 3


class CodeSyncError(ConfigSyncError):
    """代码同步失败，信息可直接展示给用户。"""


def _fetch_main(cwd):
    _run_git(["fetch", "origin", "main", "--quiet"], cwd)


def _rev_count(cwd, a, b):
    out = _run_git(["rev-list", "--count", "%s..%s" % (a, b)], cwd)
    return int(out.strip() or "0")


def _abort_rebase_safe(cwd):
    try:
        _run_git(["rebase", "--abort"], cwd)
    except ConfigSyncError:
        pass


def _require_main_branch(cwd):
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()
    if branch != "main":
        raise CodeSyncError("本地当前分支是 %s，代码同步只支持 main 分支。" % branch)


def _remote_main_exists(cwd):
    out = _run_git(["ls-remote", "--heads", "origin", "main"], cwd)
    return any(line.strip() for line in out.splitlines())


def code_status(repo_root=None):
    """查询本地 main 与远端 main 的领先/落后状态。

    返回 {"local_sha", "remote_sha", "ahead", "behind"}；
    远端没有 main 分支时返回 None；网络/仓库错误抛 CodeSyncError。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    if not _remote_main_exists(cwd):
        return None
    _fetch_main(cwd)
    local_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    remote_sha = _run_git(["rev-parse", "--verify", REMOTE_REF], cwd).strip()
    return {
        "local_sha": local_sha,
        "remote_sha": remote_sha,
        "ahead": _rev_count(cwd, REMOTE_REF, "HEAD"),
        "behind": _rev_count(cwd, "HEAD", REMOTE_REF),
    }


def _dirty_lines(cwd):
    out = _run_git(["status", "--porcelain"], cwd)
    return [line for line in out.splitlines() if line.strip()]


def _commit_identity_args(cwd):
    """兜底身份：机器上没配 git user.name/email 时仍然可以提交。

    rebase 生成新提交时同样需要身份，所以 pull --rebase 也带上这些参数
    （身份已配置时返回空列表，不覆盖用户自己的身份）。
    """
    args = []
    for key, fallback in (("user.name", "BindX"), ("user.email", "bindx@localhost")):
        try:
            value = _run_git(["config", "--get", key], cwd).strip()
        except ConfigSyncError:
            value = ""
        if not value:
            args += ["-c", "%s=%s" % (key, fallback)]
    return args


def _pull_rebase_args(cwd):
    return _commit_identity_args(cwd) + ["pull", "--rebase", "origin", "main", "--quiet"]


def pull_code(repo_root=None):
    """下载代码：把本地 main 更新到远端最新。

    要求工作区没有未提交改动（避免覆盖/丢失本地修改）。
    返回 {"updated": bool, "sha": str, "files": [str, ...]}。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    _require_main_branch(cwd)

    dirty = _dirty_lines(cwd)
    if dirty:
        preview = "\n".join(dirty[:8])
        if len(dirty) > 8:
            preview += "\n（另有 %d 个文件）" % (len(dirty) - 8)
        raise CodeSyncError(
            "本地有未提交的改动，为安全起见不能直接下载：\n%s\n"
            "如果想保留这些改动，请先按「上传代码」提交，然后再下载。" % preview
        )

    if not _remote_main_exists(cwd):
        raise CodeSyncError("远端还没有 main 分支，请先在一台机器上按「上传代码」。")

    old_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    _fetch_main(cwd)
    remote_sha = _run_git(["rev-parse", "--verify", REMOTE_REF], cwd).strip()
    if old_sha == remote_sha:
        return {"updated": False, "sha": old_sha, "files": []}

    try:
        _run_git(_pull_rebase_args(cwd), cwd)
    except ConfigSyncError as exc:
        _abort_rebase_safe(cwd)
        raise CodeSyncError(
            "同步代码失败（本地提交与远端提交有冲突，仓库已恢复原状）：%s" % str(exc)[:160]
        )
    new_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    files = [
        line
        for line in _run_git(["diff", "--name-only", old_sha, new_sha], cwd).splitlines()
        if line.strip()
    ]
    return {"updated": True, "sha": new_sha, "files": files}


def push_code(repo_root=None):
    """上传代码：提交所有本地改动（被忽略的文件除外）并推送到远端 main。

    返回 {"committed": bool, "sha": str|None, "files": [str, ...], "message": str}。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    _require_main_branch(cwd)

    _run_git(["add", "-A"], cwd)
    try:
        _run_git(["diff", "--cached", "--quiet"], cwd)
    except ConfigSyncError:
        pass  # 有已暂存改动 → 继续提交
    else:
        return {"committed": False, "sha": None, "files": [], "message": ""}

    files = [
        line
        for line in _run_git(["diff", "--cached", "--name-only"], cwd).splitlines()
        if line.strip()
    ]
    message = "sync: %s @ %s" % (
        socket.gethostname(),
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    _run_git(_commit_identity_args(cwd) + ["commit", "-m", message], cwd)

    for _ in range(MAX_PUSH_ATTEMPTS):
        _fetch_main(cwd)
        try:
            _run_git(_pull_rebase_args(cwd), cwd)
        except ConfigSyncError as exc:
            _abort_rebase_safe(cwd)
            raise CodeSyncError(
                "远端有新提交且与你的改动有冲突；本次提交已保留在本地 main，"
                "请手动查看差异后处理：%s" % str(exc)[:160]
            )
        try:
            _run_git(["push", "origin", "main"], cwd)
            break
        except ConfigSyncError as exc:
            if not _is_rejected_push(str(exc)):
                raise
    else:
        raise CodeSyncError("上传失败：远端分支在推送期间被持续修改，请稍后重试。")
    new_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    return {"committed": True, "sha": new_sha, "files": files, "message": message}