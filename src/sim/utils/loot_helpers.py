"""地面ドロップ（field WorldObject）の拾得・消費・探索。"""
from __future__ import annotations

import math

from src.sim.components.inventory import BiomassItem
from src.sim.entities.world_object import WorldObject
from src.sim.utils.field_pickup_helpers import (
    distance_to_pickup,
    is_edible_pickup,
    is_field_pickup,
    iter_pickup_in_radius,
    pickup_on_field,
    pickup_radius,
)
from src.sim.utils.geo_helpers import distance_between
from src.sim.utils.inventory_helpers import get_creature_inventory
from src.sim.utils.position_helpers import entity_xy


def is_edible_loot(obj: WorldObject | None) -> bool:
    return is_edible_pickup(obj)


def loot_on_field(world, obj: WorldObject | None) -> bool:
    return pickup_on_field(world, obj)


def distance_to_loot(creature, obj: WorldObject) -> float:
    return distance_to_pickup(creature, obj)


def find_nearest_field_loot_among(
    creature,
    species_names,
    exclude_loot_id: str | None = None,
):
    world = getattr(creature, "world", None)
    if world is None:
        return None

    names = tuple(species_names)
    vision = creature.get_current_vision()
    cx, cy = entity_xy(creature)
    candidates = iter_pickup_in_radius(world, cx, cy, vision, species_names=names)
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


def find_nearest_field_biomass_among(creature, species_names, exclude=None):
    """地面ドロップを優先し、なければ旧来の死骸個体を返す。"""
    from src.sim.utils.target_helpers import find_nearest_field_carcass_among

    loot = find_nearest_field_loot_among(creature, species_names)
    carcass = find_nearest_field_carcass_among(creature, species_names, exclude=exclude)
    if loot is None:
        return carcass
    if carcass is None:
        return loot
    if distance_to_loot(creature, loot) <= distance_between(creature, carcass):
        return loot
    return carcass


def try_pickup_loot(carrier, obj: WorldObject, contact_padding: float = 8.0) -> bool:
    inv = get_creature_inventory(carrier)
    if inv is None or inv.empty_slot_count <= 0 or not is_edible_pickup(obj):
        return False

    dist = distance_to_loot(carrier, obj)
    reach = pickup_radius(obj) + float(contact_padding)
    if dist > reach * 1.05:
        return False

    world = carrier.world
    wos = getattr(world, "world_object_system", None)
    if wos is None or not loot_on_field(world, obj):
        return False

    picked = False
    picked_amount = 0.0
    stack = obj.storage.stack if obj.storage else None
    if stack is None:
        return False

    for slot in inv.slots:
        if not slot.can_accept("biomass"):
            continue
        if obj.amount_for_kind("biomass") <= 0:
            break
        chunk = min(obj.amount_for_kind("biomass"), slot.max_mass)
        if chunk <= 0:
            continue
        withdrawn = stack.withdraw_kind("biomass", chunk)
        if withdrawn <= 0:
            break
        slot.item = BiomassItem(amount=withdrawn, source_loot=obj)
        picked = True
        picked_amount += withdrawn

    if obj.is_pickup_depleted() and obj.deplete_when_empty:
        wos.remove_instance(obj.id)

    if picked and world is not None:
        from src.sim.emitters import emit_item_found

        emit_item_found(world, carrier, item_kind="biomass", amount=picked_amount)
    return picked


def consume_loot_biomass(
    predator,
    obj: WorldObject,
    bite_gain: float = 1.35,
) -> float:
    if not is_edible_pickup(obj):
        return 0.0

    world = predator.world
    wos = getattr(world, "world_object_system", None)
    if wos is None or not loot_on_field(world, obj):
        return 0.0

    stack = obj.storage.stack if obj.storage else None
    if stack is None:
        return 0.0

    base_size = float(predator.traits.get("base_size", 9.0))
    bite_gain = float(bite_gain)
    available = obj.amount_for_kind("biomass")
    amount = min(
        available * 0.45,
        base_size * bite_gain * 1.6,
    )
    take = min(amount * 0.9, available)
    stack.withdraw_kind("biomass", take)

    gained = amount * bite_gain
    predator.satiety = min(predator.max_satiety, predator.satiety + gained)

    if obj.is_pickup_depleted() and obj.deplete_when_empty:
        wos.remove_instance(obj.id)

    return gained


def return_biomass_to_loot(world, chunk: float, obj: WorldObject | None) -> None:
    if chunk <= 0 or obj is None or obj.storage is None:
        return
    if not pickup_on_field(world, obj):
        return
    obj.storage.stack.deposit_kind("biomass", chunk)


def is_trackable_loot(creature, obj: WorldObject) -> bool:
    if not is_edible_pickup(obj):
        return False
    cx, cy = entity_xy(creature)
    dist = math.hypot(obj.x - cx, obj.y - cy)
    return dist <= creature.get_current_vision()


def spawn_drop_from_creature(creature) -> WorldObject | None:
    from src.sim.utils.drop_helpers import apply_spawn_drop_step

    return apply_spawn_drop_step(creature, {"type": "field_bulk"})


def consume_biomass_near(
    predator,
    x: float,
    y: float,
    *,
    species_name: str | None = None,
    bite_gain: float = 1.35,
    radius: float = 24.0,
) -> float:
    world = getattr(predator, "world", None)
    if world is None:
        return 0.0
    names = [species_name] if species_name else None
    loots = iter_pickup_in_radius(world, x, y, radius, species_names=names)
    if not loots:
        return 0.0
    loots.sort(key=lambda obj: math.hypot(obj.x - x, obj.y - y))
    return consume_loot_biomass(predator, loots[0], bite_gain=bite_gain)


def is_biomass_field_target(world, target) -> bool:
    if is_field_pickup(target):
        return loot_on_field(world, target)
    from src.sim.utils.target_helpers import carcass_on_field

    return carcass_on_field(world, target)


def move_toward_biomass_target(creature, target, speed_multiplier: float = 1.0) -> float:
    from src.sim.utils.movement_helpers import move_toward, move_toward_point

    if is_field_pickup(target):
        return move_toward_point(
            creature,
            target.x,
            target.y,
            float(speed_multiplier),
        )
    return move_toward(creature, target, float(speed_multiplier))


def consume_biomass_target(
    predator,
    target,
    *,
    bite_gain: float = 1.35,
) -> float:
    if is_field_pickup(target):
        return consume_loot_biomass(predator, target, bite_gain=bite_gain)
    from src.sim.utils.combat_helpers import consume_carcass

    return consume_carcass(predator, target, bite_gain=bite_gain)


def try_pickup_biomass_target(
    carrier,
    target,
    contact_padding: float = 8.0,
) -> bool:
    if is_field_pickup(target):
        return try_pickup_loot(carrier, target, contact_padding=contact_padding)
    from src.sim.utils.inventory_helpers import try_pickup_carcass

    return try_pickup_carcass(carrier, target, contact_padding=contact_padding)


def is_trackable_biomass_target(creature, target, species_names) -> bool:
    names = tuple(species_names)
    if is_field_pickup(target):
        return target.pickup_species_filter in names and is_trackable_loot(creature, target)
    from src.sim.utils.target_helpers import is_trackable_prey

    return is_trackable_prey(creature, target, names)
