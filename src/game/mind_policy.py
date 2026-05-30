"""ゲーム層: 個体の mind.actions を実行時に差し替える。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROFILES: dict[str, dict[str, Any]] | None = None


def _profiles_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "game" / "reproduction_profiles.json"


def load_reproduction_profiles() -> dict[str, dict[str, Any]]:
    global _PROFILES
    if _PROFILES is not None:
        return _PROFILES

    path = _profiles_path()
    if not path.exists():
        _PROFILES = {}
        return _PROFILES

    with open(path, encoding="utf-8") as f:
        _PROFILES = dict(json.load(f))
    return _PROFILES


def reload_reproduction_profiles() -> dict[str, dict[str, Any]]:
    global _PROFILES
    _PROFILES = None
    return load_reproduction_profiles()


class MindPolicy:
    """コロニー女王などの繁殖 AI プロファイルを適用する。"""

    def __init__(self, profiles: dict[str, dict[str, Any]] | None = None) -> None:
        self._profiles = profiles if profiles is not None else load_reproduction_profiles()

    def get_profile(self, profile_id: str) -> dict[str, Any] | None:
        return self._profiles.get(profile_id)

    def apply_profile(self, creature, profile_id: str) -> bool:
        profile = self.get_profile(profile_id)
        if profile is None:
            return False
        actions = profile.get("actions")
        if not actions:
            return False
        creature.mind.set_action_defs(actions)
        creature.current_action = None
        return True

    def reset_creature(self, creature) -> None:
        creature.mind.reset_to_base()
        creature.current_action = None
