"""マップ上のエリア（Zone：円・軸平行矩形）と属性合成を管理する。"""
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


def _geometry_from_data(
    data: Dict[str, Any],
    global_defaults: Dict[str, Any],
) -> Tuple[str, float, float, float]:
    """shape, radius, half_w, half_h を data から解決。"""
    shape = str(data.get("shape", "circle")).lower()
    if shape == "rect":
        width = float(data.get("width", 160.0))
        height = float(data.get("height", 80.0))
        return (
            "rect",
            0.0,
            max(1.0, width * 0.5),
            max(1.0, height * 0.5),
        )
    radius = float(data.get("radius", global_defaults.get("radius", 80.0)))
    return ("circle", max(0.0, radius), 0.0, 0.0)


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
    shape: str = "circle"
    radius: float = 0.0
    half_w: float = 0.0
    half_h: float = 0.0
    effects: ZoneEffects = field(default_factory=ZoneEffects)
    label: str = ""
    affiliation_id: str = ""
    auto_generated: bool = False

    @property
    def is_rect(self) -> bool:
        return str(self.shape).lower() == "rect"

    def bounding_radius(self) -> float:
        if self.is_rect:
            return math.hypot(max(0.0, self.half_w), max(0.0, self.half_h))
        return max(0.0, self.radius)

    def contains(self, x: float, y: float) -> bool:
        px, py = float(x), float(y)
        if self.is_rect:
            if self.half_w <= 0 or self.half_h <= 0:
                return False
            return abs(px - self.x) <= self.half_w and abs(py - self.y) <= self.half_h
        if self.radius <= 0:
            return False
        dx = px - self.x
        dy = py - self.y
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

    def init_from_layout(self, layout: Dict | None = None) -> None:
        """WorldObject（layer: zone）のみから Zone キャッシュを構築する。"""
        self.rebuild_from_world_objects()

    def rebuild_from_world_objects(self) -> None:
        """WorldObjectSystem の zone 配置から Zone キャッシュを再構築。"""
        self.zones.clear()
        self._next_id = 1
        ws = getattr(self.world, "world_object_system", None)
        if ws is None:
            return

        for obj in ws.iter_zones():
            if obj.zone_effects is None:
                continue
            affiliation_id = str(obj.zone_affiliation_id or "")
            if not affiliation_id and obj.type_ref == "nest_clearing" and str(
                obj.id
            ).endswith("_clearing"):
                affiliation_id = str(obj.id)[: -len("_clearing")]
            self._add_zone(
                x=float(obj.x),
                y=float(obj.y),
                zone_type=str(obj.type_ref),
                effects=obj.zone_effects,
                shape=str(obj.shape or "circle"),
                radius=float(obj.radius),
                half_w=float(obj.half_w),
                half_h=float(obj.half_h),
                label=str(obj.label or obj.type_ref),
                affiliation_id=affiliation_id,
            )

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
        zone_type: str,
        effects: ZoneEffects,
        shape: str = "circle",
        radius: float = 0.0,
        half_w: float = 0.0,
        half_h: float = 0.0,
        label: str = "",
        affiliation_id: str = "",
        auto_generated: bool = False,
    ) -> None:
        self.zones.append(
            Zone(
                id=self._next_id,
                zone_type=zone_type,
                x=float(x),
                y=float(y),
                shape=str(shape),
                radius=max(0.0, float(radius)),
                half_w=max(0.0, float(half_w)),
                half_h=max(0.0, float(half_h)),
                effects=effects,
                label=label,
                affiliation_id=affiliation_id,
                auto_generated=auto_generated,
            )
        )
        self._next_id += 1

    def _add_from_entry(self, entry: Dict, global_defaults: Dict) -> None:
        if entry.get("affiliation_id"):
            self._add_affiliation_zone_entry(entry, global_defaults)
            return
        if "x" not in entry or "y" not in entry:
            return
        data = self._resolve_entry(entry, global_defaults)
        effects = self._effects_from_data(data)
        shape, radius, half_w, half_h = _geometry_from_data(data, global_defaults)
        self._add_zone(
            x=float(data["x"]),
            y=float(data["y"]),
            zone_type=str(data.get("type", "custom")),
            effects=effects,
            shape=shape,
            radius=radius,
            half_w=half_w,
            half_h=half_h,
            label=str(data.get("label", data.get("type", ""))),
        )

    def _add_affiliation_zone_entry(self, entry: Dict, global_defaults: Dict) -> None:
        affiliation_id = str(entry["affiliation_id"])
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile

        profile = get_affiliation_profile(self.world, affiliation_id)
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
            zone_type=str(data.get("type", "nest_clearing")),
            effects=effects,
            shape="circle",
            radius=radius,
            label=str(data.get("label", f"{affiliation_id}_clearing")),
            affiliation_id=affiliation_id,
        )

    def sync_affiliation_clearing(
        self,
        affiliation_id: str,
        x: float,
        y: float,
        *,
        radius: float | None = None,
    ) -> None:
        """巣位置に合わせクリアリング WorldObject を更新し Zone キャッシュを再構築。"""
        if not affiliation_id:
            return
        ws = getattr(self.world, "world_object_system", None)
        if ws is None:
            return
        ws.sync_affiliation_clearing(affiliation_id, x, y, radius=radius)
        self.rebuild_from_world_objects()
        from src.sim.utils.field_effect_cache import invalidate_field_effect_cache

        invalidate_field_effect_cache(self.world)

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
