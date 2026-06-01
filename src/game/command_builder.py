"""ゲーム設定から SimCommand を組み立てるヘルパー。"""
from __future__ import annotations

from typing import Any

from src.game.mind_policy import MindPolicy
from src.game.spawn_profiles import SpawnProfileLoader
from src.sim.bridge import SimBridge
from src.sim.commands import (
    EnterCreatureShelter,
    SetCreatureMind,
    SimCommand,
    SpawnCreature,
)


def spawn_creature(
    bridge: SimBridge,
    species: str,
    *,
    x: float | None = None,
    y: float | None = None,
    source: str = "game",
) -> Any | None:
    """指定座標、またはランダム座標へ種をスポーン。"""
    result = bridge.execute(
        SpawnCreature(species=species, x=x, y=y, source=source)  # type: ignore[arg-type]
    )
    return result.creature if result.ok else None


def apply_mind_profile(
    bridge: SimBridge,
    creature,
    profile_id: str,
    *,
    mode: str = "replace",
) -> bool:
    profile = MindPolicy().get_profile(profile_id)
    if profile is None:
        return False
    actions = tuple(profile.get("actions") or [])
    result = bridge.execute(
        SetCreatureMind(creature_id=id(creature), actions=actions, mode=mode)  # type: ignore[arg-type]
    )
    return result.ok


def apply_mind_profile_to_species(
    bridge: SimBridge,
    species_name: str,
    profile_id: str,
    *,
    affiliation_id: str | None = None,
    mode: str = "replace",
) -> int:
    from src.sim.commands import SetSpeciesMind

    profile = MindPolicy().get_profile(profile_id)
    if profile is None:
        return 0
    actions = tuple(profile.get("actions") or [])
    result = bridge.execute(
        SetSpeciesMind(
            species_name=species_name,
            actions=actions,
            affiliation_id=affiliation_id,
            mode=mode,  # type: ignore[arg-type]
        )
    )
    return result.count if result.ok else 0


def apply_mind_profile_to_affiliation_caste(
    bridge: SimBridge,
    affiliation_id: str,
    caste: str,
    profile_id: str,
    *,
    mode: str = "replace",
) -> int:
    from src.sim.commands import SetAffiliationCasteMind

    profile = MindPolicy().get_profile(profile_id)
    if profile is None:
        return 0
    actions = tuple(profile.get("actions") or [])
    result = bridge.execute(
        SetAffiliationCasteMind(
            affiliation_id=affiliation_id,
            caste=caste,  # type: ignore[arg-type]
            actions=actions,
            mode=mode,  # type: ignore[arg-type]
        )
    )
    return result.count if result.ok else 0


def apply_mind_actions_to_affiliation_caste(
    bridge: SimBridge,
    affiliation_id: str,
    caste: str,
    actions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    mode: str = "replace",
) -> int:
    from src.sim.commands import SetAffiliationCasteMind

    result = bridge.execute(
        SetAffiliationCasteMind(
            affiliation_id=affiliation_id,
            caste=caste,  # type: ignore[arg-type]
            actions=tuple(actions),
            mode=mode,  # type: ignore[arg-type]
        )
    )
    return result.count if result.ok else 0


def build_spawn_profile_commands(creature) -> list[SimCommand]:
    """spawn_profiles.json から初期適用コマンド列を生成。"""
    profile = SpawnProfileLoader().get(creature.species.name)
    if not profile:
        return []

    commands: list[SimCommand] = []
    if profile.get("starts_sheltered"):
        commands.append(EnterCreatureShelter(creature_id=id(creature)))

    profile_id = profile.get("reproduction_profile")
    if profile_id:
        mind_profile = MindPolicy().get_profile(str(profile_id))
        if mind_profile:
            actions = tuple(mind_profile.get("actions") or [])
            commands.append(
                SetCreatureMind(
                    creature_id=id(creature),
                    actions=actions,
                    mode="replace",
                )
            )
    return commands


def apply_spawn_profile(bridge: SimBridge, creature) -> None:
    """ワールド初期化時: スポーンプロファイルを Bridge 経由で適用。"""
    bridge.execute_all(build_spawn_profile_commands(creature))
