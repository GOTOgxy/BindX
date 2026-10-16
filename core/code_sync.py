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
    _run_git(["fetch", "origin", "main", "--no-tags", "--quiet"], cwd)


def _missing_remote_ref(error_text):
    return "couldn't find remote ref" in (error_text or "").lower()


def _fetch_main_or_none(cwd):
    """fetch 远端 main；远端还没有 main 分支时返回 False。"""
    try:
        _fetch_main(cwd)
    except ConfigSyncError as exc:
        if _missing_remote_ref(str(exc)):
            return False
        raise
    return True


def _abort_rebase_safe(cwd):
    try:
        _run_git(["rebase", "--abort"], cwd)
    except ConfigSyncError:
        pass


def _require_main_branch(cwd):
    branch = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd).strip()
    if branch != "main":
        raise CodeSyncError("本地当前分支是 %s，代码同步只支持 main 分支。" % branch)


def code_status(repo_root=None, refresh=True):
    """查询本地 main 与远端 main 的领先/落后状态。

    refresh=False 时完全不联网，只读本地已知的 origin/main（配合
    config_sync.fetch_all_refs() 一次刷新两块状态时用）。

    返回 {"local_sha", "remote_sha", "ahead", "behind"}；
    本地还不知道远端 main（远端没建分支）时返回 None；
    网络/仓库错误抛 CodeSyncError。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    if refresh and not _fetch_main_or_none(cwd):
        return None
    # _local_status 拿不到 refs/remotes/origin/main 时返回 None，
    # 正好就是「远端还没有 main 分支」的语义，不必再单独 rev-parse --verify。
    return _local_status(cwd)


def _local_status(cwd, sha=None):
    """纯本地（无网络）算出 ahead/behind，供界面同步完成后直接刷新状态。

    pull/push 结束时远端跟踪引用 refs/remotes/origin/main 已经是最新的，
    所以不必再发一次 fetch 去查状态（少一次网络往返，按钮响应快一倍）。
    sha 已知时（pull/push 刚算过 HEAD）连那一次 rev-parse 也省掉。
    拿不到远端引用时返回 None，由调用方回退到联网查询。
    """
    try:
        remote = _run_git(["rev-parse", REMOTE_REF], cwd).strip()
        counts = _run_git(
            ["rev-list", "--left-right", "--count", "HEAD..." + REMOTE_REF], cwd
        ).split()
        ahead, behind = int(counts[0]), int(counts[1])
    except (ConfigSyncError, IndexError, ValueError):
        return None
    local = (sha or "").strip()
    if not local:
        try:
            local = _run_git(["rev-parse", "HEAD"], cwd).strip()
        except ConfigSyncError:
            return None     # 空仓库（还没有任何提交）
    return {"local_sha": local, "remote_sha": remote, "ahead": ahead, "behind": behind}


def _dirty_lines(cwd):
    """未提交改动清单。

    --ignore-submodules=dirty：子模块（app_hotkey_manager / mouse_click）里
    的临时文件、编译产物不应该把「下载代码」整个挡死；子模块指针真的变了
    仍然会报出来。
    """
    out = _run_git(["status", "--porcelain", "--ignore-submodules=dirty"], cwd)
    return [line for line in out.splitlines() if line.strip()]


_IDENTITY_CACHE = {}


def _commit_identity_args(cwd):
    """兜底身份：机器上没配 git user.name/email 时仍然可以提交。

    rebase 生成新提交时同样需要身份，所以 pull --rebase 也带上这些参数
    （身份已配置时返回空列表，不覆盖用户自己的身份）。

    结果按仓库缓存：push_code 一次点击里要问两遍（commit + pull --rebase），
    而 git 配置在运行期间不会变，每问一遍就是 ~60ms 的子进程启动开销。
    """
    key = str(Path(cwd).resolve())
    cached = _IDENTITY_CACHE.get(key)
    if cached is not None:
        return list(cached)
    try:
        out = _run_git(["config", "--get-regexp", r"^user\.(name|email)$"], cwd)
    except ConfigSyncError:
        out = ""  # 一个都没配（git 在没有匹配项时返回非 0）
    configured = {}
    for line in out.splitlines():
        name, _, value = line.partition(" ")
        if value.strip():
            configured[name.strip()] = value.strip()
    args = []
    for name, fallback in (("user.name", "BindX"), ("user.email", "bindx@localhost")):
        if name not in configured:
            args += ["-c", "%s=%s" % (name, fallback)]
    _IDENTITY_CACHE[key] = args
    return list(args)


def _pull_rebase_args(cwd):
    return _commit_identity_args(cwd) + ["pull", "--rebase", "origin", "main", "--quiet"]


def pull_code(repo_root=None):
    """下载代码：把本地 main 更新到远端最新。

    要求工作区没有未提交改动（避免覆盖/丢失本地修改）。
    返回 {"updated": bool, "sha": str, "files": [str, ...], "status": dict|None}。
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

    old_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    try:
        _run_git(_pull_rebase_args(cwd), cwd)
    except ConfigSyncError as exc:
        if _missing_remote_ref(str(exc)):
            raise CodeSyncError("远端还没有 main 分支，请先在一台机器上按「上传代码」。")
        _abort_rebase_safe(cwd)
        raise CodeSyncError(
            "同步代码失败（本地提交与远端提交有冲突，仓库已恢复原状）：%s" % str(exc)[:160]
        )
    new_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    if new_sha == old_sha:
        return {"updated": False, "sha": new_sha, "files": [],
                "status": _local_status(cwd, new_sha)}
    files = [
        line
        for line in _run_git(["diff", "--name-only", old_sha, new_sha], cwd).splitlines()
        if line.strip()
    ]
    return {"updated": True, "sha": new_sha, "files": files,
            "status": _local_status(cwd, new_sha)}


def push_code(repo_root=None):
    """上传代码：提交所有本地改动（被忽略的文件除外）并推送到远端 main。

    返回 {"committed": bool, "sha": str|None, "files": [str, ...], "message": str,
    "status": dict|None}。
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
        head = _run_git(["rev-parse", "HEAD"], cwd).strip()
        return {"committed": False, "sha": None, "files": [], "message": "",
                "status": _local_status(cwd, head)}

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

    # 先直接推：单人多机场景下远端绝大多数时候没有新提交，
    # 一次网络往返即可完成（旧实现每次都先 pull --rebase 再 push，等于两次往返）。
    # 被拒说明远端已前进 -> 这时才 rebase 到远端最新，再推一次。
    for attempt in range(MAX_PUSH_ATTEMPTS):
        try:
            _run_git(["push", "origin", "main"], cwd)
            break
        except ConfigSyncError as exc:
            if not _is_rejected_push(str(exc)):
                raise
            if attempt == MAX_PUSH_ATTEMPTS - 1:
                raise CodeSyncError("上传失败：远端分支在推送期间被持续修改，请稍后重试。")
            try:
                _run_git(_pull_rebase_args(cwd), cwd)
            except ConfigSyncError as rebase_exc:
                if _missing_remote_ref(str(rebase_exc)):
                    pass  # 远端还没有 main 分支（首次上传）：直接再推一次
                else:
                    _abort_rebase_safe(cwd)
                    raise CodeSyncError(
                        "远端有新提交且与你的改动有冲突；本次提交已保留在本地 main，"
                        "请手动查看差异后处理：%s" % str(rebase_exc)[:160]
                    )
    else:
        raise CodeSyncError("上传失败：远端分支在推送期间被持续修改，请稍后重试。")
    new_sha = _run_git(["rev-parse", "HEAD"], cwd).strip()
    return {"committed": True, "sha": new_sha, "files": files, "message": message,
            "status": _local_status(cwd, new_sha)}