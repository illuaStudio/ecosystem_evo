"""ゲーム層: 種別スポーンプロファイル定義の読み込み（適用は command_builder 経由）。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROFILES_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "game" / "spawn_profiles.json"
)


def load_spawn_profiles() -> dict[str, dict[str, Any]]:
    if not _PROFILES_PATH.exists():
        return {}
    with open(_PROFILES_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return {str(k): dict(v) for k, v in data.items()}


class SpawnProfileLoader:
    """種名 → ゲーム層スポーン設定（隠れ・繁殖プロファイル等）。"""

    def __init__(self, profiles: dict[str, dict[str, Any]] | None = None) -> None:
        self._profiles = profiles if profiles is not None else load_spawn_profiles()

    def get(self, species_name: str) -> dict[str, Any] | None:
        profile = self._profiles.get(species_name)
        return dict(profile) if profile else None
