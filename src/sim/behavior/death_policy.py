"""死後 PostLife step 列の正規化（sim 層：エイリアスは species 読み込み時に展開）。"""
from __future__ import annotations

from typing import Any, Mapping, Tuple

EMPTY_DEATH_STEPS: Tuple[Any, ...] = ()

NormalizedDeathPolicy = Tuple[Any, ...]


def normalize_death_policy(raw: Any | None) -> NormalizedDeathPolicy:
    """step 列のみ受け付ける（文字列エイリアスは不可）。"""
    if raw is None or raw == {}:
        return EMPTY_DEATH_STEPS
    if isinstance(raw, (list, tuple)):
        return tuple(raw)
    if isinstance(raw, Mapping):
        steps = raw.get("steps")
        if not steps:
            return EMPTY_DEATH_STEPS
        return tuple(steps)
    return EMPTY_DEATH_STEPS


def death_policy_for_creature(creature) -> NormalizedDeathPolicy:
    override = getattr(creature, "death_policy_override", None)
    if override is not None:
        return normalize_death_policy(override)
    species = getattr(creature, "species", None)
    if species is not None:
        steps = getattr(species, "death_policy_steps", None)
        if steps is not None:
            return tuple(steps)
    return EMPTY_DEATH_STEPS


def set_creature_death_policy(creature, policy: Any | None) -> None:
    from src.sim.entities.species import expand_death_policy_content

    creature.death_policy_override = normalize_death_policy(
        expand_death_policy_content(policy)
    )
