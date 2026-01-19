# -*- coding: utf-8 -*-
"""
Unified Path Configuration
Loads paths from paths.json in the project root.
"""
import json
import os
import sys
from pathlib import Path

# Project Root (where this file is located)
PROJECT_ROOT = Path(__file__).resolve().parent

CONFIG_FILE = PROJECT_ROOT / "paths.json"

if not CONFIG_FILE.exists():
    raise FileNotFoundError(
        f"Configuration file not found: {CONFIG_FILE}\n"
        f"Please copy 'paths.json.example' to 'paths.json' and configure it."
    )

try:
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        _config = json.load(f)
except json.JSONDecodeError as e:
    raise ValueError(f"Invalid JSON in {CONFIG_FILE}: {e}")

def _get_path(key):
    val = _config.get(key)
    if not val:
        raise KeyError(f"Missing key '{key}' in {CONFIG_FILE}")

    path = Path(val)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path

# Exposed Paths
# Exposed Paths
SRC_GML = _get_path("src_gml")
DATA_META = _get_path("data_meta")
DATA_TABLES = _get_path("data_tables")
