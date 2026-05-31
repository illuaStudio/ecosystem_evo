"""マップ上の円形エリア（Zone）と属性合成を管理する。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    from src.sim.systems.world import World

DEFAULT_POISON_FOG = {
    "hp_drain_per_dt": 0.07,
    "field_tags": ["poison"],
    "radius": 95.0,
}

DEFAULT_NEST_CLEARING = {
    "spawn_rate_multiplier": 0.0,
    "radius": 150.0,
}


def _normalize_tags(raw: Any) -> Tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    return tuple(str(x) for x in raw if x)


@dataclass
class ZoneEffects:
    """エリアが座標に与える属性（未設定は合成時に無視）。"""

    hp_regen_per_dt: float = 0.0
    hp_drain_per_dt: float = 0.0
    field_tags: Tuple[str, ...] = ()
    spawn_rate_multiplier: Optional[float] = None

    def merged_with(self, other: ZoneEffects) -> ZoneEffects:
        spawn = self.spawn_rate_multiplier
        if other.spawn_rate_multiplier is not None:
            spawn = (
                other.spawn_rate_multiplier
                if spawn is None
                else min(spawn, other.spawn_rate_multiplier)
            )
        tags = self.field_tags + other.field_tags
        return ZoneEffects(
            hp_regen_per_dt=self.hp_regen_per_dt + other.hp_regen_per_dt,
            hp_drain_per_dt=self.hp_drain_per_dt + other.hp_drain_per_dt,
            field_tags=tags,
            spawn_rate_multiplier=spawn,
        )


@dataclass
class Zone:
    id: int
    zone_type: str
    x: float
    y: float
    radius: float
    effects: ZoneEffects = field(default_factory=ZoneEffects)
    label: str = ""
    colony_id: str = ""
    auto_generated: bool = False

    def contains(self, x: float, y: float) -> bool:
        if self.radius <= 0:
            return False
        dx = float(x) - self.x
        dy = float(y) - self.y
        return dx * dx + dy * dy <= self.radius * self.radius


@dataclass(frozen=True)
class ZoneSample:
    """座標における Zone 層の合成結果（バイオーム除く）。"""

    hp_regen_per_dt: float = 0.0
    hp_drain_per_dt: float = 0.0
    field_tags: Tuple[str, ...] = ()
    spawn_rate_multiplier: float = 1.0

    @property
    def spawn_blocked(self) -> bool:
        return self.spawn_rate_multiplier <= 0.0


class ZoneSystem:
    def __init__(self, world: "World") -> None:
        self.world = world
        self.zones: List[Zone] = []
        self._next_id = 1
        self._type_defaults: Dict[str, Dict] = {}

    def init_from_config(
        self,
        cfg: Dict | None,
        *,
        legacy_field_emitters: Dict | None = None,
        colony_profiles: Dict | None = None,
    ) -> None:
        self.zones.clear()
        self._next_id = 1
        self._type_defaults.clear()

        if cfg:
            defaults = dict(cfg.get("defaults") or {})
            for key, value in (cfg.get("types") or {}).items():
                if isinstance(value, dict):
                    self._type_defaults[str(key)] = dict(value)
            for entry in cfg.get("sources") or []:
                if isinstance(entry, dict):
                    self._add_from_entry(entry, defaults)

        if legacy_field_emitters:
            legacy_defaults = dict(legacy_field_emitters.get("defaults") or {})
            for entry in legacy_field_emitters.get("sources") or legacy_field_emitters.get(
                "emitters"
            ) or []:
                if isinstance(entry, dict):
                    self._add_from_legacy_field_emitter(entry, legacy_defaults)

        if colony_profiles:
            self._add_colony_clearing_zones(colony_profiles)

    def _resolve_entry(self, entry: Dict, global_defaults: Dict) -> Dict:
        zone_type = str(entry.get("type", global_defaults.get("type", "custom")))
        merged = dict(global_defaults)
        merged.update(self._type_defaults.get(zone_type, {}))
        merged.update(entry)
        merged["type"] = zone_type
        return merged

    def _effects_from_data(self, data: Dict) -> ZoneEffects:
        inline = data.get("effects")
        if isinstance(inline, dict):
            base = dict(inline)
        else:
            base = dict(data)

        tags = base.get("field_tags", base.get("tags"))
        spawn_raw = base.get("spawn_rate_multiplier")
        spawn: Optional[float] = None
        if spawn_raw is not None:
            spawn = float(spawn_raw)

        return ZoneEffects(
            hp_regen_per_dt=max(0.0, float(base.get("hp_regen_per_dt", 0.0))),
            hp_drain_per_dt=max(0.0, float(base.get("hp_drain_per_dt", 0.0))),
            field_tags=_normalize_tags(tags),
            spawn_rate_multiplier=spawn,
        )

    def _add_zone(
        self,
        *,
        x: float,
        y: float,
        radius: float,
        zone_type: str,
        effects: ZoneEffects,
        label: str = "",
        colony_id: str = "",
        auto_generated: bool = False,
    ) -> None:
        self.zones.append(
            Zone(
                id=self._next_id,
                zone_type=zone_type,
                x=float(x),
                y=float(y),
                radius=max(0.0, float(radius)),
                effects=effects,
                label=label,
                colony_id=colony_id,
                auto_generated=auto_generated,
            )
        )
        self._next_id += 1

    def _add_from_entry(self, entry: Dict, global_defaults: Dict) -> None:
        if entry.get("colony_id"):
            self._add_colony_zone_entry(entry, global_defaults)
            return
        if "x" not in entry or "y" not in entry:
            return
        data = self._resolve_entry(entry, global_defaults)
        effects = self._effects_from_data(data)
        self._add_zone(
            x=float(data["x"]),
            y=float(data["y"]),
            radius=float(data.get("radius", global_defaults.get("radius", 80.0))),
            zone_type=str(data.get("type", "custom")),
            effects=effects,
            label=str(data.get("label", data.get("type", ""))),
        )

    def _add_colony_zone_entry(self, entry: Dict, global_defaults: Dict) -> None:
        colony_id = str(entry["colony_id"])
        profiles = getattr(self.world, "colony_profiles", None) or {}
        profile = dict(profiles.get(colony_id) or {})
        data = self._resolve_entry(entry, global_defaults)
        x = entry.get("x", profile.get("nest_x"))
        y = entry.get("y", profile.get("nest_y"))
        if x is None or y is None:
            return
        radius = float(
            entry.get("radius", profile.get("spawn_exclusion_radius", data.get("radius", 150.0)))
        )
        effects = self._effects_from_data(data)
        if effects.spawn_rate_multiplier is None:
            effects = ZoneEffects(
                hp_regen_per_dt=effects.hp_regen_per_dt,
                hp_drain_per_dt=effects.hp_drain_per_dt,
                field_tags=effects.field_tags,
                spawn_rate_multiplier=0.0,
            )
        self._add_zone(
            x=float(x),
            y=float(y),
            radius=radius,
            zone_type=str(data.get("type", "nest_clearing")),
            effects=effects,
            label=str(data.get("label", f"{colony_id}_clearing")),
            colony_id=colony_id,
        )

    def _add_from_legacy_field_emitter(self, entry: Dict, global_defaults: Dict) -> None:
        if "x" not in entry or "y" not in entry:
            return
        merged = dict(DEFAULT_POISON_FOG)
        merged.update(global_defaults)
        zone_type = str(entry.get("type", merged.get("type", "poison_fog")))
        merged.update(self._type_defaults.get(zone_type, {}))
        merged.update(entry)
        effects = ZoneEffects(
            hp_regen_per_dt=max(0.0, float(merged.get("hp_regen_per_dt", 0.0))),
            hp_drain_per_dt=max(0.0, float(merged.get("hp_drain_per_dt", 0.0))),
            field_tags=_normalize_tags(merged.get("tags", merged.get("field_tags", ("poison",)))),
        )
        self._add_zone(
            x=float(merged["x"]),
            y=float(merged["y"]),
            radius=float(merged.get("radius", 95.0)),
            zone_type=zone_type,
            effects=effects,
            label=str(merged.get("label", zone_type)),
        )

    def _add_colony_clearing_zones(self, colony_profiles: Dict) -> None:
        for colony_id, raw_profile in colony_profiles.items():
            profile = dict(raw_profile or {})
            radius = float(profile.get("spawn_exclusion_radius", DEFAULT_NEST_CLEARING["radius"]))
            if radius <= 0:
                continue
            nest_x = profile.get("nest_x")
            nest_y = profile.get("nest_y")
            if nest_x is None or nest_y is None:
                continue
            if self._has_colony_clearing(colony_id):
                continue
            self._add_zone(
                x=float(nest_x),
                y=float(nest_y),
                radius=radius,
                zone_type="nest_clearing",
                effects=ZoneEffects(spawn_rate_multiplier=0.0),
                label=f"{colony_id}_clearing",
                colony_id=str(colony_id),
                auto_generated=True,
            )

    def sync_colony_clearing(
        self,
        colony_id: str,
        x: float,
        y: float,
        *,
        radius: float | None = None,
    ) -> None:
        """巣の実位置に合わせてクリアリング Zone を更新または追加する。"""
        if not colony_id:
            return
        if radius is None:
            radius = self._clearing_radius_for_colony(colony_id)
        radius = float(radius)
        if radius <= 0:
            return

        for zone in self.zones:
            if zone.colony_id == colony_id and zone.effects.spawn_rate_multiplier == 0.0:
                zone.x = float(x)
                zone.y = float(y)
                zone.radius = radius
                zone.auto_generated = True
                return

        self._add_zone(
            x=float(x),
            y=float(y),
            radius=radius,
            zone_type="nest_clearing",
            effects=ZoneEffects(spawn_rate_multiplier=0.0),
            label=f"{colony_id}_clearing",
            colony_id=str(colony_id),
            auto_generated=True,
        )

    def _clearing_radius_for_colony(self, colony_id: str) -> float:
        profiles = getattr(self.world, "colony_profiles", None) or {}
        profile = dict(profiles.get(colony_id) or {})
        return float(profile.get("spawn_exclusion_radius", DEFAULT_NEST_CLEARING["radius"]))

    def _has_colony_clearing(self, colony_id: str) -> bool:
        for zone in self.zones:
            if zone.colony_id == colony_id and zone.effects.spawn_rate_multiplier == 0.0:
                return True
        return False

    def zones_at(self, x: float, y: float) -> List[Zone]:
        px, py = float(x), float(y)
        return [zone for zone in self.zones if zone.contains(px, py)]

    def sample_at(self, x: float, y: float) -> ZoneSample:
        combined = ZoneEffects()
        for zone in self.zones_at(x, y):
            combined = combined.merged_with(zone.effects)
        spawn = combined.spawn_rate_multiplier if combined.spawn_rate_multiplier is not None else 1.0
        return ZoneSample(
            hp_regen_per_dt=combined.hp_regen_per_dt,
            hp_drain_per_dt=combined.hp_drain_per_dt,
            field_tags=combined.field_tags,
            spawn_rate_multiplier=spawn,
        )

    def is_spawn_allowed(self, x: float, y: float) -> bool:
        return not self.sample_at(x, y).spawn_blocked

    def get_spawn_rate_multiplier(self, x: float, y: float) -> float:
        """バイオームを含めた最終スポーン倍率。"""
        world = self.world
        zone_mult = self.sample_at(x, y).spawn_rate_multiplier
        if zone_mult <= 0:
            return 0.0
        biome_mult = world.biome.get_spawn_rate_multiplier(x, y)
        return zone_mult * biome_mult

    def sample_hp_modifiers(
        self,
        creature: Any,
        x: float,
        y: float,
        *,
        immunities: Sequence[str] | None = None,
    ):
        from src.sim.utils.field_modifiers import FieldModifiers, get_field_immunities

        sample = self.sample_at(x, y)
        if not sample.field_tags and sample.hp_regen_per_dt <= 0 and sample.hp_drain_per_dt <= 0:
            return FieldModifiers()

        immune = set(immunities or get_field_immunities(creature))
        if immune.intersection(sample.field_tags):
            return FieldModifiers(
                hp_regen_per_dt=sample.hp_regen_per_dt,
            )

        return FieldModifiers(
            hp_regen_per_dt=sample.hp_regen_per_dt,
            hp_drain_per_dt=sample.hp_drain_per_dt,
        )

    def pick_spawn_position(
        self,
        *,
        margin: int = 80,
        attempts: int = 32,
        center: Tuple[float, float] | None = None,
        radius: float | None = None,
        use_biome_weight: bool = True,
    ) -> Optional[Tuple[float, float]]:
        from src.sim.utils.spawn_placement import (
            SpawnAnchor,
            SpawnPlacementOptions,
            SpawnPlacementResolver,
        )

        resolver = SpawnPlacementResolver(self.world)
        if center is not None and radius is not None and radius > 0:
            anchor = SpawnAnchor(type="area", x=center[0], y=center[1], radius=float(radius))
        else:
            anchor = SpawnAnchor(type="world")
        return resolver.pick(
            anchor,
            SpawnPlacementOptions(
                margin=margin,
                attempts=attempts,
                use_biome_weight=use_biome_weight,
            ),
        )

    def accept_probabilistic_spawn(self, x: float, y: float) -> bool:
        """バイオーム・ゾーン倍率に基づく確率的スポーン受理。"""
        mult = self.get_spawn_rate_multiplier(x, y)
        if mult <= 0:
            return False
        rich = self.world.biome.get_max_spawn_rate_multiplier()
        if rich <= 0:
            return True
        return random.random() < min(1.0, mult / rich)
