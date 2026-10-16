# -*- coding: utf-8 -*-
"""BindX 配置 Git 云同步。

只同步 data/bindx_config.json 这一个文件，不触碰软件的其他任何内容：

- 上传：在远端同步分支（``config``）的 tip 之上构造一个只包含配置
  文件的提交并 push。全程使用 git 底层命令（hash-object / 临时索引 /
  commit-tree / update-ref），不 checkout、不 pull、不 merge、不改动
  工作区与 main 分支。
- 拉取：fetch 同步分支，取出其中唯一的配置文件，原子替换本地文件，
  随后由 UI 层重载引擎使新配置立即生效。

远端不存在同步分支时，首次上传会自动创建。冲突语义为「后写覆盖先写」。
"""

import json
import os
import subprocess
import tempfile
import threading
from datetime import datetime
from pathlib import Path

BRANCH = "config"
SYNC_REF = "refs/remotes/origin/" + BRANCH
CONFIG_PATH = "data/bindx_config.json"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
GIT_TIMEOUT = 120
MAX_PUSH_ATTEMPTS = 3

# 全局 git 互斥锁：整台机器只有一个仓库（同一份 index / refs / 对象库）。
# 「配置云同步」和「代码同步」各自在后台线程里跑 git，并发时两个 fetch 会
# 互相踩 FETCH_HEAD 与 packed-refs.lock，偶发报错甚至写坏引用。
# 所有 git 调用一律串行化（RLock：同一线程内嵌套调用也安全）。
_GIT_LOCK = threading.RLock()


class ConfigSyncError(Exception):
    """同步失败，消息可直接展示给用户。"""


def _base_env():
    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def _friendly(stderr_text):
    text = (stderr_text or "").lower()
    if (
        "could not resolve hostname" in text
        or "unable to access" in text
        or "could not read from remote repository" in text
        or "connection" in text
    ):
        return "无法连接远端仓库，请检查网络或远端地址。"
    if (
        "permission denied" in text
        or "authentication failed" in text
        or "terminal prompts disabled" in text
        or "could not read username" in text
        or "access denied" in text
    ):
        return "远端仓库认证失败，请检查 git 凭据（SSH 密钥或访问令牌）。"
    if "not a git repository" in text:
        return "该目录不是 git 仓库。"
    if "does not exist" in text or "pathspec" in text:
        return "远端同步分支中找不到配置文件。"
    return None


def _run_git(args, cwd, env=None):
    kwargs = {}
    if os.name == "nt":
        # 以 pythonw（无控制台）运行时，每个控制台子进程默认会弹一个
        # 黑窗口；CREATE_NO_WINDOW 使其完全在后台运行。
        kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
    try:
        with _GIT_LOCK:
            proc = subprocess.run(
                ["git", "-c", "color.ui=never"] + list(args),
                cwd=str(cwd),
                env=env if env is not None else _base_env(),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=GIT_TIMEOUT,
                **kwargs,
            )
    except FileNotFoundError:
        raise ConfigSyncError("未找到 git 命令行工具，请先安装 git。")
    except subprocess.TimeoutExpired:
        raise ConfigSyncError("git 操作超时（超过 %d 秒）。" % GIT_TIMEOUT)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise ConfigSyncError(_friendly(detail) or (detail or "git 命令失败。"))
    return proc.stdout.decode("utf-8", "replace")


def _commit_info(cwd, ref):
    """一次本地 git 调用取 (sha, 提交时间 ISO8601)。"""
    out = _run_git(["log", "-1", "--format=%H %cI", ref], cwd).strip()
    sha, _, time_str = out.partition(" ")
    return sha, time_str


_VERIFIED_REPOS = set()


def _require_repo(cwd):
    """一次 git 调用同时确认「是仓库」和「配了 origin」（少一次进程启动）。

    结果按仓库路径缓存：origin 不会在运行期间凭空消失，而 Windows 上每
    启动一个 git 子进程约 60ms，四个同步按钮每点一次都能省掉这一趟。
    """
    key = str(Path(cwd).resolve())
    if key in _VERIFIED_REPOS:
        return
    try:
        _run_git(["remote", "get-url", "origin"], cwd)
    except ConfigSyncError as exc:
        text = str(exc).lower()
        if "不是 git 仓库" in str(exc) or "not a git repository" in text:
            raise ConfigSyncError("该目录不是 git 仓库：%s" % cwd)
        raise ConfigSyncError("仓库未配置 origin 远端，无法同步。")
    _VERIFIED_REPOS.add(key)


def _missing_remote_ref(error_text):
    return "couldn't find remote ref" in (error_text or "").lower()


def _fetch_sync_branch(cwd):
    """fetch 远端同步分支；分支还不存在时返回 False。

    只发一次网络请求（旧实现是 ls-remote + fetch 两次）。fetch 成功后
    git 会顺带更新 refs/remotes/origin/config，所以不需要再 rev-parse 一次。
    """
    try:
        _run_git(["fetch", "origin", BRANCH, "--no-tags", "--quiet"], cwd)
    except ConfigSyncError as exc:
        if _missing_remote_ref(str(exc)):
            return False
        raise
    return True


def fetch_all_refs(repo_root=None):
    """一次网络往返把所有远端分支引用（main + config）同步到本地。

    界面上「配置云同步」和「代码同步」两块状态过去各自 fetch 一次；
    SSH 连 GitHub 光握手就要 4~5 秒，启动时等于白等两轮，而且两个
    线程还会被全局 git 锁串起来。改成用默认 refspec 一次拉全部分支，
    之后两块状态都只读本地引用（零网络）。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    _run_git(["fetch", "origin", "--no-tags", "--quiet"], cwd)


def _local_sync_tip(cwd):
    """本地已知的远端同步分支 tip（纯本地，无网络）；不知道时返回 None。"""
    try:
        return _run_git(["rev-parse", "--verify", "--quiet", SYNC_REF], cwd).strip() or None
    except ConfigSyncError:
        return None


def _build_config_commit(cwd, blob, base_tip, stamp):
    """用临时索引构造一个只包含配置文件的提交，不触碰工作区。"""
    fd, idx_path = tempfile.mkstemp(prefix="bindx-sync-idx-", suffix=".idx")
    os.close(fd)
    os.unlink(idx_path)  # git requires the index path to not pre-exist
    env = _base_env()
    env["GIT_INDEX_FILE"] = idx_path
    try:
        if base_tip:
            _run_git(["read-tree", base_tip], cwd, env=env)
        _run_git(
            ["update-index", "--add", "--cacheinfo", "100644,%s,%s" % (blob, CONFIG_PATH)],
            cwd,
            env=env,
        )
        tree = _run_git(["write-tree"], cwd, env=env).strip()
        parent = ["-p", base_tip] if base_tip else []
        commit = _run_git(
            [
                "-c", "user.name=BindX Config Sync",
                "-c", "user.email=bindx-config-sync@localhost",
                "commit-tree", tree,
            ]
            + parent
            + ["-m", "sync: bindx config @ %s" % stamp],
            cwd,
        ).strip()
    finally:
        try:
            os.unlink(idx_path)
        except OSError:
            pass
    return commit


def _is_rejected_push(message):
    text = (message or "").lower()
    return "non-fast-forward" in text or "rejected" in text


def upload_config(repo_root=None):
    """把本地配置文件推送到远端同步分支，返回 {"sha": ...}。"""
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    cfg = cwd / CONFIG_PATH
    if not cfg.exists():
        raise ConfigSyncError("找不到配置文件：%s" % cfg)
    _require_repo(cwd)

    blob = _run_git(["hash-object", "-w", CONFIG_PATH], cwd).strip()
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 直接基于「本地已知的远端 tip」造提交并 push。
    # 单人多机使用时远端极少被别人改动，这样一次网络往返就能上传完
    # （旧实现每次都要先 fetch 再 push，等于两次往返、慢一倍）。
    # push 被拒说明远端确实前进了：fetch 最新 tip 后重建提交再推。
    for attempt in range(MAX_PUSH_ATTEMPTS):
        commit = _build_config_commit(cwd, blob, _local_sync_tip(cwd), stamp)
        try:
            _run_git(["push", "origin", "%s:refs/heads/%s" % (commit, BRANCH)], cwd)
            # 提交是本地刚造出来的：sha 已知、时间就是 stamp，
            # 不必再启动一个 git log 子进程去问一遍。
            return {"sha": commit, "time": stamp}
        except ConfigSyncError as exc:
            if not _is_rejected_push(str(exc)):
                raise
            if attempt == MAX_PUSH_ATTEMPTS - 1:
                break
            _fetch_sync_branch(cwd)
    raise ConfigSyncError("上传失败：远端分支有并发更新，请再试一次。")


def download_config(repo_root=None):
    """从远端同步分支拉取配置文件到本地，返回 {"sha": ...}。"""
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    cfg = cwd / CONFIG_PATH
    _require_repo(cwd)
    if not _fetch_sync_branch(cwd):
        raise ConfigSyncError("远端还没有配置分支，请先在本机按「上传配置」推送一次。")
    content = _run_git(["show", SYNC_REF + ":" + CONFIG_PATH], cwd)
    try:
        parsed = json.loads(content)
    except ValueError:
        raise ConfigSyncError("远端配置不是合法 JSON，已放弃写入，本地文件未改动。")
    if not isinstance(parsed, dict):
        raise ConfigSyncError("远端配置格式无效（不是 JSON 对象），本地文件未改动。")
    tmp = cfg.with_name(cfg.name + ".tmp")
    tmp.write_bytes(content.encode("utf-8"))
    os.replace(tmp, cfg)
    sha, time_str = _commit_info(cwd, SYNC_REF)
    return {"sha": sha, "time": time_str}


def remote_status(repo_root=None, refresh=True):
    """查询远端同步分支状态，用于界面展示。

    refresh=False 时完全不联网，只读本地已知的远端引用——配合
    fetch_all_refs() 一次性刷新两块状态时用，避免第二次 SSH 往返。

    返回 {"sha": ..., "time": ...}；分支尚不存在时返回 None；
    网络/仓库错误抛出 ConfigSyncError。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    if refresh and not _fetch_sync_branch(cwd):
        return None
    if not _local_sync_tip(cwd):
        return None
    sha, time_str = _commit_info(cwd, SYNC_REF)
    return {"sha": sha, "time": time_str}