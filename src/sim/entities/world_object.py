"""マップ上の汎用オブジェクト（親子階層・備蓄・Shelter 接続点）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Tuple

from src.sim.components.object_storage import ObjectStorage
from src.sim.systems.zone_system import ZoneEffects
from src.sim.utils.object_capabilities import point_in_shape


@dataclass
class WorldObject:
    """Sim 上の配置オブジェクト。親=備蓄、子=接続/Shelter。"""

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
        return self.parent_id is None and self.storage is not None

    @property
    def is_access_point(self) -> bool:
        return self.parent_id is not None

    @property
    def is_colony_compound(self) -> bool:
        return self.compound_profile == "colony"

    @property
    def is_destroyed(self) -> bool:
        return self.max_hp > 0 and self.hp <= 0

    @property
    def compound_id(self) -> str:
        """ルート=自身 id、接続点=parent_id（colony_id の汎化名）。"""
        return str(self.parent_id or self.id)

    @property
    def colony_id(self) -> str:
        """後方互換。"""
        return self.compound_id

    @property
    def stored_food(self) -> float:
        if self.storage is None:
            return 0.0
        return float(self.storage.stored_food)

    @stored_food.setter
    def stored_food(self, amount: float) -> None:
        if self.storage is None:
            return
        cap = float(self.storage.max_food)
        amount = max(0.0, float(amount))
        self.storage.stored_food = min(amount, cap) if cap > 0 else amount

    @property
    def max_food(self) -> float:
        if self.storage is None:
            return 0.0
        return float(self.storage.max_food)

    @max_food.setter
    def max_food(self, cap: float) -> None:
        if self.storage is None:
            return
        self.storage.max_food = max(0.0, float(cap))

    @property
    def food_ratio(self) -> float:
        if self.storage is None:
            return 0.0
        return float(self.storage.food_ratio)
