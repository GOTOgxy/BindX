# -*- coding: utf-8 -*-

import copy
import json
import os
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
CONFIG_FILE = ROOT_DIR / "bindx_config.json"
LEGACY_HOTKEY_FILE = ROOT_DIR / "app_hotkey_manager" / "app_hotkey_config.json"
LEGACY_MOUSE_FILE = ROOT_DIR / "mouse_click" / "config.json"

DEFAULT_APP_STATE = {
    "hotkey_running": True,
    "mouse_running": True,
    "window_size": None,
    "window_zoomed": False,
    "font_preset": "常规",
    "autostart_enabled": False,
}

DEFAULT_HOTKEY_CONFIG = {
    "display_name": "App Hotkey Manager",
    "mutex_name": "Global\\AppHotkeyManager",
    "entries": [],
}

DEFAULT_MOUSE_CONFIG = {
    "mappings": [],
    "mouse_mappings": [],
}

DEFAULT_ROOT_CONFIG = {
    "app": DEFAULT_APP_STATE,
    "hotkeys": DEFAULT_HOTKEY_CONFIG,
    "mouse": DEFAULT_MOUSE_CONFIG,
}

VALID_FONT_PRESETS = {"紧凑", "稍小", "常规", "特大", "超大"}
LEGACY_FONT_MAP = {
    "标准": "常规",
    "大": "特大",
    "特大": "超大",
}


def _clone(value):
    return copy.deepcopy(value)


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, data):
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_path, path)


def _normalize_app_state(raw):
    state = dict(DEFAULT_APP_STATE)
    if not isinstance(raw, dict):
        return state

    state["hotkey_running"] = bool(raw.get("hotkey_running", state["hotkey_running"]))
    state["mouse_running"] = bool(raw.get("mouse_running", state["mouse_running"]))

    size = raw.get("window_size")
    if not (isinstance(size, str) and size):
        legacy_geometry = raw.get("window_geometry")
        if isinstance(legacy_geometry, str) and "x" in legacy_geometry:
            size = legacy_geometry.split("+", 1)[0]
    state["window_size"] = size if isinstance(size, str) and size else None

    state["window_zoomed"] = bool(raw.get("window_zoomed", state["window_zoomed"]))

    font_preset = LEGACY_FONT_MAP.get(raw.get("font_preset", state["font_preset"]), raw.get("font_preset", state["font_preset"]))
    if font_preset not in VALID_FONT_PRESETS:
        font_preset = DEFAULT_APP_STATE["font_preset"]
    state["font_preset"] = font_preset

    state["autostart_enabled"] = bool(raw.get("autostart_enabled", state["autostart_enabled"]))
    return state


def _normalize_hotkey_config(raw):
    config = dict(DEFAULT_HOTKEY_CONFIG)
    if isinstance(raw, dict):
        config["display_name"] = raw.get("display_name") or DEFAULT_HOTKEY_CONFIG["display_name"]
        config["mutex_name"] = raw.get("mutex_name") or DEFAULT_HOTKEY_CONFIG["mutex_name"]
        entries = raw.get("entries")
        config["entries"] = [_normalize_hotkey_entry(entry) for entry in entries] if isinstance(entries, list) else []
    return config


def _normalize_hotkey_entry(raw):
    if not isinstance(raw, dict):
        return {}
    entry = dict(raw)
    if entry.get("app") == "hot_key_manager" and entry.get("name") in {None, "", "Hot Key Manager"}:
        entry["name"] = "BindX"
    runtime_profile = raw.get("_runtime_profile")
    entry["_runtime_profile"] = _normalize_runtime_profile(runtime_profile)
    return entry


def _normalize_runtime_profile(raw):
    if not isinstance(raw, dict):
        return {}

    profile = {}
    str_keys = {"show_behavior", "hide_behavior"}
    for key in str_keys:
        value = raw.get(key)
        if isinstance(value, str) and value:
            profile[key] = value

    return profile


def _normalize_mouse_config(raw):
    config = dict(DEFAULT_MOUSE_CONFIG)
    if isinstance(raw, dict):
        mappings = raw.get("mappings")
        mouse_mappings = raw.get("mouse_mappings")
        config["mappings"] = mappings if isinstance(mappings, list) else []
        config["mouse_mappings"] = mouse_mappings if isinstance(mouse_mappings, list) else []
    return config


def _normalize_root_config(raw):
    raw = raw if isinstance(raw, dict) else {}
    return {
        "app": _normalize_app_state(raw.get("app")),
        "hotkeys": _normalize_hotkey_config(raw.get("hotkeys")),
        "mouse": _normalize_mouse_config(raw.get("mouse")),
    }


def _looks_like_centralized_config(raw):
    return isinstance(raw, dict) and any(key in raw for key in ("app", "hotkeys", "mouse"))


def _migrate_legacy_config():
    root_raw = _read_json(CONFIG_FILE)
    if _looks_like_centralized_config(root_raw):
        return _normalize_root_config(root_raw), False

    hotkey_raw = _read_json(LEGACY_HOTKEY_FILE)
    mouse_raw = _read_json(LEGACY_MOUSE_FILE)

    migrated = {
        "app": _normalize_app_state(root_raw),
        "hotkeys": _normalize_hotkey_config(hotkey_raw),
        "mouse": _normalize_mouse_config(mouse_raw),
    }
    should_write = root_raw is not None or hotkey_raw is not None or mouse_raw is not None
    return migrated, should_write


def load_root_config():
    raw = _read_json(CONFIG_FILE)
    if _looks_like_centralized_config(raw):
        normalized = _normalize_root_config(raw)
        if raw != normalized:
            _write_json(CONFIG_FILE, normalized)
        return normalized

    migrated, should_write = _migrate_legacy_config()
    if should_write or not CONFIG_FILE.exists():
        _write_json(CONFIG_FILE, migrated)
    return migrated


def save_root_config(config):
    normalized = _normalize_root_config(config)
    _write_json(CONFIG_FILE, normalized)


def load_app_state():
    return _clone(load_root_config()["app"])


def save_app_state(state):
    root = load_root_config()
    root["app"] = _normalize_app_state(state)
    save_root_config(root)


def load_hotkey_config():
    return _clone(load_root_config()["hotkeys"])


def save_hotkey_config(config):
    root = load_root_config()
    root["hotkeys"] = _normalize_hotkey_config(config)
    save_root_config(root)


def load_mouse_config():
    return _clone(load_root_config()["mouse"])


def save_mouse_config(config):
    root = load_root_config()
    root["mouse"] = _normalize_mouse_config(config)
    save_root_config(root)
