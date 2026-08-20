# -*- coding: utf-8 -*-

import copy
import json
import os
import shutil
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CONFIG_FILE = DATA_DIR / "bindx_config.json"
LEGACY_HOTKEY_FILE = PROJECT_DIR / "hotkeys" / "app_hotkey_config.json"
LEGACY_MOUSE_FILE = PROJECT_DIR / "remap" / "config.json"

DEFAULT_APP_STATE = {
    "hotkey_running": True,
    "mouse_running": True,
    "window_size": None,
    "window_zoomed": False,
    "font_preset": "常规",
    "autostart_enabled": False,
    "output_delay_ms": 20,
    "restore_held_modifiers": True,
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


LOAD_ERRORS = []


def _record_load_error(path: Path, error: Exception):
    LOAD_ERRORS.append(str(error))
    print("[BindX] config read failed, existing file kept: %s: %s" % (path, error), file=sys.stderr)


def _read_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        _record_load_error(path, error)
        return None


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    if path.exists():
        try:
            shutil.copy2(path, str(path) + ".bak")
        except OSError:
            pass
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

    try:
        output_delay_ms = int(raw.get("output_delay_ms", DEFAULT_APP_STATE["output_delay_ms"]))
    except (TypeError, ValueError):
        output_delay_ms = DEFAULT_APP_STATE["output_delay_ms"]
    if output_delay_ms < 0:
        output_delay_ms = DEFAULT_APP_STATE["output_delay_ms"]
    state["output_delay_ms"] = min(output_delay_ms, 500)

    state["restore_held_modifiers"] = bool(raw.get("restore_held_modifiers", DEFAULT_APP_STATE["restore_held_modifiers"]))
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


def _merge_legacy_sections(root_config):
    merged = _normalize_root_config(root_config)
    changed = False

    legacy_hotkey = _normalize_hotkey_config(_read_json(LEGACY_HOTKEY_FILE))
    if not merged["hotkeys"].get("entries") and legacy_hotkey.get("entries"):
        merged["hotkeys"] = legacy_hotkey
        changed = True

    legacy_mouse = _normalize_mouse_config(_read_json(LEGACY_MOUSE_FILE))
    merged_mouse = merged["mouse"]
    if (
        not merged_mouse.get("mappings")
        and not merged_mouse.get("mouse_mappings")
        and (legacy_mouse.get("mappings") or legacy_mouse.get("mouse_mappings"))
    ):
        merged["mouse"] = legacy_mouse
        changed = True

    return merged, changed


def load_root_config():
    raw = _read_json(CONFIG_FILE)
    if _looks_like_centralized_config(raw):
        normalized, merged_legacy = _merge_legacy_sections(raw)
        if raw != normalized or merged_legacy:
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
