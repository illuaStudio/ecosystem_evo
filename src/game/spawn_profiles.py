"""ゲーム層: 種別スポーンプロファイル（シミュ JSON とは分離）。"""
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

    def apply_to_creature(self, creature) -> None:
        """スポーンプロファイルを個体に適用（ゲーム層のみ）。"""
        profile = self.get(creature.species.name)
        if not profile:
            return

        if profile.get("starts_sheltered"):
            self._enter_nest_shelter(creature)

        profile_id = profile.get("reproduction_profile")
        if profile_id:
            from src.game.mind_policy import MindPolicy

            MindPolicy().apply_profile(creature, str(profile_id))

    @staticmethod
    def _enter_nest_shelter(creature) -> None:
        from src.sim.shelter.helpers import enter_creature_shelter, resolve_nest_shelter

        ref = resolve_nest_shelter(creature)
        if ref is None:
            return

        creature.position.x = ref.x
        creature.position.y = ref.y
        creature.pos[0] = ref.x
        creature.pos[1] = ref.y
        enter_creature_shelter(creature, ref)
