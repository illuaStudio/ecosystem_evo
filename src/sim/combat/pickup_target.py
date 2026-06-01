"""採餌・運搬対象（死骸個体 / field WorldObject）の統一参照。"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Iterable, Optional

if TYPE_CHECKING:
    from src.sim.entities.world_object import WorldObject


class PickupTargetKind(Enum):
    CREATURE_CARCASS = "creature_carcass"
    FIELD_OBJECT = "field_object"


@dataclass(frozen=True, slots=True)
class PickupTarget:
    kind: PickupTargetKind
    creature: object | None = None
    world_object: Optional["WorldObject"] = None

    @staticmethod
    def from_creature(creature) -> PickupTarget:
        return PickupTarget(
            kind=PickupTargetKind.CREATURE_CARCASS,
            creature=creature,
        )

    @staticmethod
    def from_field_object(obj: "WorldObject") -> PickupTarget:
        return PickupTarget(
            kind=PickupTargetKind.FIELD_OBJECT,
            world_object=obj,
        )

    @staticmethod
    def from_any(target) -> PickupTarget | None:
        from src.sim.entities.world_object import WorldObject
        from src.sim.utils.field_pickup_helpers import is_field_pickup

        if target is None:
            return None
        if isinstance(target, PickupTarget):
            return target
        if isinstance(target, WorldObject) and is_field_pickup(target):
            return PickupTarget.from_field_object(target)
        if hasattr(target, "species") and hasattr(target, "alive") and not target.alive:
            return PickupTarget.from_creature(target)
        return None

    def unwrap(self):
        """AI・移動が期待する生の target（Creature または WorldObject）。"""
        if self.kind is PickupTargetKind.FIELD_OBJECT:
            return self.world_object
        return self.creature

    def position(self) -> tuple[float, float]:
        if self.kind is PickupTargetKind.FIELD_OBJECT and self.world_object is not None:
            return float(self.world_object.x), float(self.world_object.y)
        if self.creature is not None:
            from src.sim.utils.position_helpers import entity_xy

            return entity_xy(self.creature)
        return (0.0, 0.0)


def distance_to_forage(creature, target) -> float:
    from src.sim.utils.field_pickup_helpers import distance_to_pickup
    from src.sim.utils.position_helpers import entity_xy

    ref = PickupTarget.from_any(target)
    if ref is None:
        return float("inf")
    if ref.kind is PickupTargetKind.FIELD_OBJECT and ref.world_object is not None:
        return distance_to_pickup(creature, ref.world_object)
    if ref.creature is not None:
        from src.sim.utils.geo_helpers import distance_between

        return distance_between(creature, ref.creature)
    cx, cy = entity_xy(creature)
    tx, ty = ref.position()
    return math.hypot(tx - cx, ty - cy)


def find_nearest_field_pickup_among(
    creature,
    species_names: Iterable[str],
    *,
    exclude_loot_id: str | None = None,
):
    from src.sim.utils.field_pickup_helpers import iter_pickup_in_radius
    from src.sim.utils.position_helpers import entity_xy

    world = getattr(creature, "world", None)
    if world is None:
        return None

    names = tuple(species_names)
    cx, cy = entity_xy(creature)
    candidates = iter_pickup_in_radius(
        world, cx, cy, creature.get_current_vision(), species_names=names
    )
    best = None
    min_dist = float("inf")
    for obj in candidates:
        if exclude_loot_id and obj.id == exclude_loot_id:
            continue
        dist = math.hypot(obj.x - cx, obj.y - cy)
        if dist < min_dist:
            min_dist = dist
            best = obj
    return best


def find_nearest_forage_among(creature, species_names, exclude=None):
    """field ドロップを優先し、なければ死骸個体。"""
    from src.sim.utils.target_helpers import find_nearest_field_carcass_among

    loot = find_nearest_field_pickup_among(creature, species_names)
    carcass = find_nearest_field_carcass_among(creature, species_names, exclude=exclude)
    if loot is None:
        return carcass
    if carcass is None:
        return loot
    if distance_to_forage(creature, loot) <= distance_to_forage(creature, carcass):
        return loot
    return carcass


def is_forage_field_target(world, target) -> bool:
    from src.sim.utils.field_pickup_helpers import is_field_pickup, pickup_on_field
    from src.sim.utils.target_helpers import carcass_on_field

    if is_field_pickup(target):
        return pickup_on_field(world, target)
    return carcass_on_field(world, target)


def move_toward_forage_target(creature, target, speed_multiplier: float = 1.0) -> float:
    from src.sim.utils.movement_helpers import move_toward, move_toward_point
    from src.sim.utils.field_pickup_helpers import is_field_pickup

    if is_field_pickup(target):
        return move_toward_point(
            creature,
            target.x,
            target.y,
            float(speed_multiplier),
        )
    return move_toward(creature, target, float(speed_multiplier))


def consume_forage_target(predator, target, *, bite_gain: float = 1.35) -> float:
    from src.sim.utils.field_pickup_helpers import is_field_pickup

    if is_field_pickup(target):
        from src.sim.utils.loot_helpers import consume_loot_biomass

        return consume_loot_biomass(predator, target, bite_gain=bite_gain)
    from src.sim.utils.combat_helpers import consume_carcass

    return consume_carcass(predator, target, bite_gain=bite_gain)


def try_pickup_forage_target(
    carrier, target, contact_padding: float = 8.0
) -> bool:
    from src.sim.utils.field_pickup_helpers import is_field_pickup

    if is_field_pickup(target):
        from src.sim.utils.loot_helpers import try_pickup_loot

        return try_pickup_loot(carrier, target, contact_padding=contact_padding)
    from src.sim.utils.inventory_helpers import try_pickup_carcass

    return try_pickup_carcass(carrier, target, contact_padding=contact_padding)


def is_trackable_forage_target(creature, target, species_names) -> bool:
    from src.sim.utils.field_pickup_helpers import (
        is_edible_pickup,
        is_field_pickup,
        is_haulable_pickup,
        is_pickable_pickup,
    )
    from src.sim.utils.position_helpers import entity_xy
    from src.sim.utils.target_helpers import is_trackable_prey

    names = tuple(species_names)
    if is_field_pickup(target):
        filt = target.pickup_species_filter
        if filt and filt not in names:
            return False
        if not is_pickable_pickup(target):
            return False
        if not is_edible_pickup(target) and not is_haulable_pickup(target):
            return False
        cx, cy = entity_xy(creature)
        return math.hypot(target.x - cx, target.y - cy) <= creature.get_current_vision()
    return is_trackable_prey(creature, target, names)
