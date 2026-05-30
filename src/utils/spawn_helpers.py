"""個体生成直後の初期状態（隠れ・繁殖プロファイル等）。"""
from __future__ import annotations

from src.config import config


def apply_creature_spawn_state(creature) -> None:
    """種 JSON / ゲーム設定に基づき、add_creature 直後の状態を適用する。"""
    species_data = config.get_species(creature.species.name) or {}
    colony_cfg = species_data.get("colony", {})

    if colony_cfg.get("starts_sheltered"):
        _enter_nest_shelter(creature)

    profile_id = (species_data.get("game") or {}).get("reproduction_profile")
    if profile_id:
        from src.game.mind_policy import MindPolicy

        MindPolicy().apply_profile(creature, profile_id)


def _enter_nest_shelter(creature) -> None:
    from src.shelter.helpers import enter_creature_shelter, resolve_nest_shelter

    ref = resolve_nest_shelter(creature)
    if ref is None:
        return

    creature.position.x = ref.x
    creature.position.y = ref.y
    creature.pos[0] = ref.x
    creature.pos[1] = ref.y
    enter_creature_shelter(creature, ref)
