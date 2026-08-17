# -*- coding: utf-8 -*-

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core import config_store


def load_config():
    config = config_store.load_mouse_config()
    config.setdefault("mappings", [])
    config.setdefault("mouse_mappings", [])
    return config


def save_config(config):
    config_store.save_mouse_config(config)
