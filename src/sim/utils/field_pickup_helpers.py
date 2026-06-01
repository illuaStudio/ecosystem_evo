"""フィールド配置 WorldObject（pickup capability）の共通 API。"""
from __future__ import annotations

import math
from typing import Iterable, List, Optional, TYPE_CHECKING

from src.sim.entities.world_object import WorldObject

if TYPE_CHECKING:
    from src.sim.systems.world_object_system import WorldObjectSystem


def object_system(world) -> Optional["WorldObjectSystem"]:
    if world is None:
        return None
    return getattr(world, "world_object_system", None)


def is_field_pickup(target) -> bool:
    return isinstance(target, WorldObject) and target.is_field_pickup


def pickup_radius(target: WorldObject) -> float:
    return float(getattr(target, "pickup_radius", 12.0))


def is_pickable_pickup(obj: WorldObject | None) -> bool:
    return is_field_pickup(obj) and not obj.is_pickup_depleted()


def is_edible_pickup(obj: WorldObject | None) -> bool:
    if not is_pickable_pickup(obj):
        return False
    return obj.amount_for_kind("biomass") > 0


def is_haulable_pickup(obj: WorldObject | None) -> bool:
    if not is_pickable_pickup(obj):
        return False
    if "haul" not in getattr(obj, "pickup_modes", ()):
        return False
    if obj.amount_for_kind("biomass") > 0:
        return True
    stack = obj.storage.stack if obj.storage else None
    return stack is not None and stack.first_stack_item() is not None


def pickup_on_field(world, obj: WorldObject | None) -> bool:
    wos = object_system(world)
    if wos is None or obj is None:
        return False
    return obj.id in wos.objects and is_pickable_pickup(obj)


def distance_to_pickup(creature, obj: WorldObject) -> float:
    from src.sim.utils.position_helpers import entity_xy

    cx, cy = entity_xy(creature)
    return math.hypot(obj.x - cx, obj.y - cy)


def iter_field_pickups(world) -> List[WorldObject]:
    wos = object_system(world)
    if wos is None:
        return []
    return wos.iter_field_pickups()


def iter_pickup_in_radius(
    world,
    x: float,
    y: float,
    radius: float,
    *,
    species_names: Iterable[str] | None = None,
) -> List[WorldObject]:
    wos = object_system(world)
    if wos is None:
        return []
    return wos.iter_field_pickup_in_radius(
        x, y, radius, species_names=species_names
    )
