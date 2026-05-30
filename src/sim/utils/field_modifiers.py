"""座標・バイオーム・テリトリーから環境 HP 変化を集約（Applied Effect Phase 2 とは別）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.sim.utils.colony_helpers import get_creature_colony_id
from src.sim.utils.creature_helpers import is_point_in_colony_territory
from src.sim.utils.position_helpers import entity_xy


def get_field_immunities(creature: Any) -> frozenset[str]:
    """種 traits の field_immunities（完全無効化タグ）。"""
    traits = getattr(creature, "traits", {}) or {}
    raw = traits.get("field_immunities") or ()
    if isinstance(raw, str):
        return frozenset({raw})
    return frozenset(str(tag) for tag in raw if tag)


@dataclass(frozen=True)
class FieldModifiers:
    """1 tick あたりの環境由来 HP 変化（加算合成）。"""

    hp_regen_per_dt: float = 0.0
    hp_drain_per_dt: float = 0.0

    def merged_with(self, other: FieldModifiers) -> FieldModifiers:
        return FieldModifiers(
            hp_regen_per_dt=self.hp_regen_per_dt + other.hp_regen_per_dt,
            hp_drain_per_dt=self.hp_drain_per_dt + other.hp_drain_per_dt,
        )


def _biome_modifiers(world: Any, x: float, y: float) -> FieldModifiers:
    biome = world.biome.get_biome_at(x, y)
    return FieldModifiers(
        hp_regen_per_dt=float(biome.get("hp_regen_per_dt", 0.0)),
        hp_drain_per_dt=float(biome.get("hp_drain_per_dt", 0.0)),
    )


def _territory_modifiers(world: Any, creature: Any, x: float, y: float) -> FieldModifiers:
    colony_settings = getattr(world, "colony_settings", None) or {}
    effects = colony_settings.get("territory_effects") or {}
    if not effects:
        return FieldModifiers()

    regen = float(effects.get("hp_regen_per_dt", 0.0))
    drain = float(effects.get("hp_drain_per_dt", 0.0))
    if regen == 0.0 and drain == 0.0:
        return FieldModifiers()

    requires_match = bool(effects.get("requires_colony_match", True))
    if requires_match:
        colony_id = get_creature_colony_id(creature)
        if not colony_id or not is_point_in_colony_territory(world, colony_id, x, y):
            return FieldModifiers()

    return FieldModifiers(hp_regen_per_dt=regen, hp_drain_per_dt=drain)


def _emitter_modifiers(world: Any, creature: Any, x: float, y: float) -> FieldModifiers:
    system = getattr(world, "field_emitter_system", None)
    if system is None:
        return FieldModifiers()
    return system.sample_modifiers(creature, x, y)


def sample_field_modifiers(world: Any, creature: Any) -> FieldModifiers:
    """個体の現在位置から環境 modifier を合成する。"""
    if world is None or not getattr(creature, "alive", True):
        return FieldModifiers()

    x, y = entity_xy(creature)
    biome = _biome_modifiers(world, x, y)
    territory = _territory_modifiers(world, creature, x, y)
    emitters = _emitter_modifiers(world, creature, x, y)
    return biome.merged_with(territory).merged_with(emitters)


def resolve_field_hp_delta(creature: Any, modifiers: FieldModifiers, dt: float) -> float:
    """traits の耐性・倍率を適用した net HP 変化量。"""
    traits = getattr(creature, "traits", {}) or {}
    poison_resist = max(0.0, min(1.0, float(traits.get("poison_resist", 0.0))))
    regen_mult = float(traits.get("hp_regen_mult", 1.0))
    regen = modifiers.hp_regen_per_dt * regen_mult
    drain = modifiers.hp_drain_per_dt * (1.0 - poison_resist)
    return (regen - drain) * float(dt)


def apply_field_hp_effects(creature: Any, dt: float = 1.0) -> None:
    """環境フィールドによる HP 回復・ダメージを適用する。"""
    world = getattr(creature, "world", None)
    if world is None or not getattr(creature, "alive", True):
        return

    modifiers = sample_field_modifiers(world, creature)
    delta = resolve_field_hp_delta(creature, modifiers, dt)
    if delta == 0.0:
        return

    max_hp = float(getattr(creature, "max_hp", 0.0))
    creature.hp = min(max_hp, max(0.0, float(creature.hp) + delta))
