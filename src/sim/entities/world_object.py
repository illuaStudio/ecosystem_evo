"""マップ上の汎用オブジェクト（親子階層・容器・Shelter 接続点）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from src.sim.components.object_storage import ObjectStorage
from src.sim.components.spawn_capability import SpawnCapability
from src.sim.systems.zone_system import ZoneEffects
from src.sim.utils.object_capabilities import point_in_shape


@dataclass
class WorldObject:
    """Sim 上の配置オブジェクト。親=容器ルート、子=接続/Shelter。"""

    id: str
    type_ref: str
    x: float
    y: float
    parent_id: Optional[str] = None
    role: str = ""
    storage: Optional[ObjectStorage] = None
    shelter: bool = False
    deposit_access: bool = False
    withdraw_access: bool = False
    hp: float = 0.0
    max_hp: float = 0.0
    label: str = ""
    shape: str = ""
    radius: float = 0.0
    half_w: float = 0.0
    half_h: float = 0.0
    color: Tuple[int, int, int] = (120, 118, 110)
    zone_effects: Optional[ZoneEffects] = None
    compound_profile: str = ""
    layer: str = ""
    origin: str = "map"
    lifecycle: str = "static"
    pickup_radius: float = 12.0
    pickup_modes: Tuple[str, ...] = ()
    deplete_when_empty: bool = True
    decay_rate: float = 0.0
    initial_fill: float = 0.0
    pickup_species_filter: str = ""
    size_from_fill_ratio: bool = False
    spawn: SpawnCapability | None = None
    zone_affiliation_id: str = ""

    @property
    def is_spawn_emitter(self) -> bool:
        return self.spawn is not None

    @property
    def is_field_pickup(self) -> bool:
        return self.layer == "field" and self.storage is not None

    @property
    def is_obstacle(self) -> bool:
        return self.shape in ("circle", "rect")

    @property
    def is_zone(self) -> bool:
        return self.zone_effects is not None

    def contains_point(self, x: float, y: float) -> bool:
        if not self.is_zone and not self.is_obstacle:
            return False
        return point_in_shape(
            x,
            y,
            shape=self.shape or "circle",
            cx=self.x,
            cy=self.y,
            radius=self.radius,
            half_w=self.half_w,
            half_h=self.half_h,
        )

    @property
    def is_root(self) -> bool:
        if self.layer == "field":
            return False
        return self.parent_id is None and self.storage is not None

    def amount_for_kind(self, kind: str) -> float:
        if self.storage is None:
            return 0.0
        return self.storage.stack.amount_for_kind(kind)

    def is_pickup_depleted(self) -> bool:
        if self.storage is None:
            return True
        return self.storage.stack.is_empty

    @property
    def fill_ratio(self) -> float:
        if self.initial_fill > 0 and self.storage is not None:
            initial = max(float(self.initial_fill), 1.0)
            return max(0.0, min(1.0, self.storage.stored_mass / initial))
        if self.storage is None:
            return 0.0
        return self.storage.fill_ratio

    @property
    def is_access_point(self) -> bool:
        return self.parent_id is not None

    @property
    def is_affiliation_compound(self) -> bool:
        return self.compound_profile == "affiliation"

    @property
    def is_destroyed(self) -> bool:
        return self.max_hp > 0 and self.hp <= 0

    @property
    def compound_id(self) -> str:
        return str(self.parent_id or self.id)

    @property
    def affiliation_id(self) -> str:
        return self.compound_id

    @property
    def stored_mass(self) -> float:
        if self.storage is None:
            return 0.0
        return float(self.storage.stored_mass)

    @stored_mass.setter
    def stored_mass(self, amount: float) -> None:
        if self.storage is None:
            return
        cap = float(self.storage.capacity)
        amount = max(0.0, float(amount))
        self.storage.stored_mass = min(amount, cap) if cap > 0 else amount

    @property
    def capacity(self) -> float:
        if self.storage is None:
            return 0.0
        return float(self.storage.capacity)

    @capacity.setter
    def capacity(self, cap: float) -> None:
        if self.storage is None:
            return
        self.storage.capacity = max(0.0, float(cap))
