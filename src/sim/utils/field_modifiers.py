"""座標・バイオーム・テリトリーから環境 HP 変化を集約。"""
from __future__ import annotations

from typing import Any

from src.sim.environment.field_sources import (
    FieldModifiers,
    compose_field_sample,
    sample_field_modifiers,
)

__all__ = [
    "FieldModifiers",
    "compose_field_sample",
    "sample_field_modifiers",
    "get_field_immunities",
    "resolve_field_hp_delta",
    "apply_field_hp_effects",
]


def get_field_immunities(creature: Any) -> frozenset[str]:
    traits = getattr(creature, "traits", {}) or {}
    raw = traits.get("field_immunities") or ()
    if isinstance(raw, str):
        return frozenset({raw})
    return frozenset(str(tag) for tag in raw if tag)


def resolve_field_hp_delta(creature: Any, modifiers: FieldModifiers, dt: float) -> float:
    traits = getattr(creature, "traits", {}) or {}
    poison_resist = max(0.0, min(1.0, float(traits.get("poison_resist", 0.0))))
    regen = modifiers.hp_regen_per_dt
    drain = modifiers.hp_drain_per_dt * (1.0 - poison_resist)
    return (regen - drain) * float(dt)


def apply_field_hp_effects(creature: Any, dt: float = 1.0) -> None:
    world = getattr(creature, "world", None)
    if world is None or not getattr(creature, "alive", True):
        return

    modifiers = sample_field_modifiers(world, creature)
    delta = resolve_field_hp_delta(creature, modifiers, dt)
    if delta == 0.0:
        return

    max_hp = float(getattr(creature, "max_hp", 0.0))
    creature.hp = min(max_hp, max(0.0, float(creature.hp) + delta))
