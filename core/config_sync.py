# -*- coding: utf-8 -*-
"""BindX 配置 Git 云同步。

只同步 data/bindx_config.json 这一个文件，不触碰软件的其他任何内容：

- 上传：在远端同步分支（``config``）的 tip 之上构造一个只包含配置
  文件的提交并 push。全程使用 git 底层命令（hash-object / 临时索引 /
  commit-tree / update-ref），不 checkout、不 pull、不 merge、不改动
  工作区与 main 分支。
- 拉取：fetch 同步分支，取出其中唯一的配置文件，原子替换本地文件
  （替换前保留 .bak），随后由 UI 层重载引擎使新配置立即生效。

远端不存在同步分支时，首次上传会自动创建。冲突语义为「后写覆盖先写」。
"""

import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path

BRANCH = "config"
CONFIG_PATH = "data/bindx_config.json"
DEFAULT_REPO_ROOT = Path(__file__).resolve().parent.parent
GIT_TIMEOUT = 120
MAX_PUSH_ATTEMPTS = 3


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
    try:
        proc = subprocess.run(
            ["git", "-c", "color.ui=never"] + list(args),
            cwd=str(cwd),
            env=env if env is not None else _base_env(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_TIMEOUT,
        )
    except FileNotFoundError:
        raise ConfigSyncError("未找到 git 命令行工具，请先安装 git。")
    except subprocess.TimeoutExpired:
        raise ConfigSyncError("git 操作超时（超过 %d 秒）。" % GIT_TIMEOUT)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise ConfigSyncError(_friendly(detail) or (detail or "git 命令失败。"))
    return proc.stdout.decode("utf-8", "replace")


def _require_repo(cwd):
    out = _run_git(["rev-parse", "--is-inside-work-tree"], cwd)
    if out.strip() != "true":
        raise ConfigSyncError("该目录不是 git 仓库：%s" % cwd)
    try:
        _run_git(["remote", "get-url", "origin"], cwd)
    except ConfigSyncError:
        raise ConfigSyncError("仓库未配置 origin 远端，无法同步。")


def _remote_branch_tip(cwd):
    """返回远端同步分支的 sha；分支尚不存在时返回 None。"""
    out = _run_git(["ls-remote", "--heads", "origin", BRANCH], cwd)
    lines = [line for line in out.splitlines() if line.strip()]
    if not lines:
        return None
    return lines[0].split()[0]


def _fetch_sync_branch(cwd):
    _run_git(["fetch", "origin", BRANCH, "--quiet"], cwd)
    return _run_git(["rev-parse", "--verify", "refs/remotes/origin/" + BRANCH], cwd).strip()


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

    for _ in range(MAX_PUSH_ATTEMPTS):
        base_tip = None
        if _remote_branch_tip(cwd) is not None:
            # 远端分支已存在：先 fetch，新提交的父提交取远端最新 tip，
            # 保证 push 是 fast-forward，不会覆盖别人刚推的配置。
            _fetch_sync_branch(cwd)
            base_tip = _run_git(
                ["rev-parse", "--verify", "refs/remotes/origin/" + BRANCH], cwd
            ).strip()
        commit = _build_config_commit(cwd, blob, base_tip, stamp)
        _run_git(["update-ref", "refs/heads/" + BRANCH, commit], cwd)
        try:
            _run_git(["push", "origin", BRANCH], cwd)
            return {"sha": commit}
        except ConfigSyncError as exc:
            if not _is_rejected_push(str(exc)):
                raise
            # 远端 tip 在我们 push 前又前进了：回到循环顶部基于最新 tip 重建
    raise ConfigSyncError("上传失败：远端分支有并发更新，请再试一次。")


def download_config(repo_root=None):
    """从远端同步分支拉取配置文件到本地，返回 {"sha": ...}。"""
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    cfg = cwd / CONFIG_PATH
    _require_repo(cwd)
    if _remote_branch_tip(cwd) is None:
        raise ConfigSyncError("远端还没有配置分支，请先在本机按「上传配置」推送一次。")
    _fetch_sync_branch(cwd)
    sha = _run_git(["rev-parse", "--verify", "refs/remotes/origin/" + BRANCH], cwd).strip()
    content = _run_git(["show", "refs/remotes/origin/" + BRANCH + ":" + CONFIG_PATH], cwd)
    try:
        parsed = json.loads(content)
    except ValueError:
        raise ConfigSyncError("远端配置不是合法 JSON，已放弃写入，本地文件未改动。")
    if not isinstance(parsed, dict):
        raise ConfigSyncError("远端配置格式无效（不是 JSON 对象），本地文件未改动。")
    if cfg.exists():
        try:
            shutil.copy2(cfg, str(cfg) + ".bak")
        except OSError:
            pass
    tmp = cfg.with_name(cfg.name + ".tmp")
    tmp.write_bytes(content.encode("utf-8"))
    os.replace(tmp, cfg)
    return {"sha": sha}


def remote_status(repo_root=None):
    """查询远端同步分支状态，用于界面展示。

    返回 {"sha": ..., "time": ...}；分支尚不存在时返回 None；
    网络/仓库错误抛出 ConfigSyncError。
    """
    cwd = Path(repo_root) if repo_root else DEFAULT_REPO_ROOT
    _require_repo(cwd)
    tip = _remote_branch_tip(cwd)
    if tip is None:
        return None
    _run_git(["fetch", "origin", BRANCH, "--quiet"], cwd)
    time_str = _run_git(
        ["log", "-1", "--format=%cI", "refs/remotes/origin/" + BRANCH], cwd
    ).strip()
    return {"sha": tip, "time": time_str}