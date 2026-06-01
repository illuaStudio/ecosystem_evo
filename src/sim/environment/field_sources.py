"""環境フィールドの合成（バイオーム・ゾーン・テリトリー）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from src.sim.utils.affiliation_group_helpers import get_creature_affiliation_id
from src.sim.utils.creature_helpers import is_point_in_affiliation_territory
from src.sim.utils.position_helpers import entity_xy


def get_field_immunities(creature: Any) -> frozenset[str]:
    traits = getattr(creature, "traits", {}) or {}
    raw = traits.get("field_immunities") or ()
    if isinstance(raw, str):
        return frozenset({raw})
    return frozenset(str(tag) for tag in raw if tag)


@dataclass(frozen=True)
class FieldModifiers:
    hp_regen_per_dt: float = 0.0
    hp_drain_per_dt: float = 0.0

    def merged_with(self, other: FieldModifiers) -> FieldModifiers:
        return FieldModifiers(
            hp_regen_per_dt=self.hp_regen_per_dt + other.hp_regen_per_dt,
            hp_drain_per_dt=self.hp_drain_per_dt + other.hp_drain_per_dt,
        )


@dataclass(frozen=True)
class FieldSample:
    """座標または個体における環境 HP 変化の合成結果。"""

    hp_regen_per_dt: float = 0.0
    hp_drain_per_dt: float = 0.0
    field_tags: tuple[str, ...] = ()

    def merged_with(self, other: FieldSample) -> FieldSample:
        tags = self.field_tags + other.field_tags
        return FieldSample(
            hp_regen_per_dt=self.hp_regen_per_dt + other.hp_regen_per_dt,
            hp_drain_per_dt=self.hp_drain_per_dt + other.hp_drain_per_dt,
            field_tags=tags,
        )

    def to_modifiers(self) -> FieldModifiers:
        return FieldModifiers(
            hp_regen_per_dt=self.hp_regen_per_dt,
            hp_drain_per_dt=self.hp_drain_per_dt,
        )


class FieldSource(Protocol):
  def sample_at(self, world: Any, x: float, y: float, creature: Any | None = None) -> FieldSample:
      ...


class BiomeFieldSource:
    def sample_at(
        self, world: Any, x: float, y: float, creature: Any | None = None
    ) -> FieldSample:
        biome = world.biome.get_biome_at(x, y)
        return FieldSample(
            hp_regen_per_dt=float(biome.get("hp_regen_per_dt", 0.0)),
            hp_drain_per_dt=float(biome.get("hp_drain_per_dt", 0.0)),
        )


class ZoneFieldSource:
    def sample_at(
        self, world: Any, x: float, y: float, creature: Any | None = None
    ) -> FieldSample:
        zone_system = getattr(world, "zone_system", None)
        if zone_system is None:
            return FieldSample()
        sample = zone_system.sample_at(x, y)
        if creature is None:
            return FieldSample(
                hp_regen_per_dt=sample.hp_regen_per_dt,
                hp_drain_per_dt=sample.hp_drain_per_dt,
                field_tags=tuple(sample.field_tags),
            )
        immune = get_field_immunities(creature)
        if immune.intersection(sample.field_tags):
            return FieldSample(hp_regen_per_dt=sample.hp_regen_per_dt)
        return FieldSample(
            hp_regen_per_dt=sample.hp_regen_per_dt,
            hp_drain_per_dt=sample.hp_drain_per_dt,
            field_tags=tuple(sample.field_tags),
        )


class TerritoryFieldSource:
    def sample_at(
        self, world: Any, x: float, y: float, creature: Any | None = None
    ) -> FieldSample:
        affiliation_settings = getattr(world, "affiliation_settings", None) or {}
        effects = affiliation_settings.get("territory_effects") or {}
        if not effects:
            return FieldSample()
        regen = float(effects.get("hp_regen_per_dt", 0.0))
        drain = float(effects.get("hp_drain_per_dt", 0.0))
        if regen == 0.0 and drain == 0.0:
            return FieldSample()
        requires_match = bool(effects.get("requires_affiliation_match", True))
        if requires_match:
            if creature is None:
                return FieldSample()
            affiliation_id = get_creature_affiliation_id(creature)
            if not affiliation_id or not is_point_in_affiliation_territory(
                world, affiliation_id, x, y
            ):
                return FieldSample()
        return FieldSample(hp_regen_per_dt=regen, hp_drain_per_dt=drain)


DEFAULT_FIELD_SOURCES: tuple[FieldSource, ...] = (
    BiomeFieldSource(),
    TerritoryFieldSource(),
    ZoneFieldSource(),
)


def compose_field_sample(
    world: Any,
    x: float,
    y: float,
    creature: Any | None = None,
    sources: tuple[FieldSource, ...] | None = None,
) -> FieldSample:
    combined = FieldSample()
    for source in sources or DEFAULT_FIELD_SOURCES:
        combined = combined.merged_with(source.sample_at(world, x, y, creature))
    return combined


def sample_field_modifiers(world: Any, creature: Any) -> FieldModifiers:
    if world is None or not getattr(creature, "alive", True):
        return FieldModifiers()
    cache = getattr(world, "field_effect_cache", None)
    if cache is not None:
        return cache.sample_for_creature(creature)
    x, y = entity_xy(creature)
    return compose_field_sample(world, x, y, creature).to_modifiers()
