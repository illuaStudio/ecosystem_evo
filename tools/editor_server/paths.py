"""エディタサーバー用パス。"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_GAME = PROJECT_ROOT / "config" / "game"
SPECIES_DIR = CONFIG_GAME / "species"
OBJECT_TYPES_DIR = CONFIG_GAME / "object_types"
EDITOR_WEB_DIR = Path(__file__).resolve().parent.parent / "editor_web"
SHARED_STATE_PATH = PROJECT_ROOT / ".editor_shared_state.json"
