"""種・個体の死後処理ポリシー（PostLife step 列）。"""
from __future__ import annotations

from typing import Any, Mapping, Tuple

DEFAULT_FIELD_DROP_STEPS: Tuple[Any, ...] = (
    {"step": "spawn_drop", "type": "field_bulk"},
    "remove",
)

_LEGACY_CORPSE_ON_CREATURE_STEPS: Tuple[str, ...] = (
    "convert_corpse_mass",
    "decompose_until_empty",
)

NormalizedDeathPolicy = Tuple[Any, ...]

_POLICY_ALIASES: dict[str, Tuple[Any, ...]] = {
    "field_drop": DEFAULT_FIELD_DROP_STEPS,
    "corpse_on_creature": _LEGACY_CORPSE_ON_CREATURE_STEPS,
    "immediate_remove": ("remove",),
    "remove": ("remove",),
}


def normalize_death_policy(raw: Any | None) -> NormalizedDeathPolicy:
    """species JSON の death_policy を step 列へ（文字列 or パラメータ付き dict）。"""
    if raw is None or raw == {}:
        return DEFAULT_FIELD_DROP_STEPS
    if isinstance(raw, str):
        return _POLICY_ALIASES.get(raw, DEFAULT_FIELD_DROP_STEPS)
    if isinstance(raw, Mapping):
        steps = raw.get("steps")
        if not steps:
            return DEFAULT_FIELD_DROP_STEPS
        return tuple(steps)
    return DEFAULT_FIELD_DROP_STEPS


def death_policy_for_creature(creature) -> NormalizedDeathPolicy:
    override = getattr(creature, "death_policy_override", None)
    if override is not None:
        return normalize_death_policy(override)
    species = getattr(creature, "species", None)
    if species is not None:
        steps = getattr(species, "death_policy_steps", None)
        if steps:
            return tuple(steps)
    return DEFAULT_FIELD_DROP_STEPS


def set_creature_death_policy(creature, policy: Any | None) -> None:
    creature.death_policy_override = policy
