"""地面ドロップ（field WorldObject）の拾得・消費・探索。

採餌統合 API は `combat.pickup_target` / `forage_helpers` を優先すること。
"""
from __future__ import annotations

from src.sim.components.inventory import BiomassItem
from src.sim.entities.world_object import WorldObject
from src.sim.combat.pickup_target import (
    distance_to_forage,
    find_nearest_field_pickup_among,
    find_nearest_forage_among,
    is_forage_field_target,
    is_trackable_forage_target,
    move_toward_forage_target,
    consume_forage_target,
    try_pickup_forage_target,
)
from src.sim.utils.field_pickup_helpers import (
    is_edible_pickup,
    is_field_pickup,
    is_haulable_pickup,
    is_pickable_pickup,
    iter_pickup_in_radius,
    pickup_on_field,
    pickup_radius,
)
from src.sim.utils.inventory_helpers import get_creature_inventory

# 後方互換エイリアス
distance_to_loot = distance_to_forage
find_nearest_field_loot_among = find_nearest_field_pickup_among
find_nearest_field_biomass_among = find_nearest_forage_among
is_biomass_field_target = is_forage_field_target
move_toward_biomass_target = move_toward_forage_target
consume_biomass_target = consume_forage_target
try_pickup_biomass_target = try_pickup_forage_target
is_trackable_biomass_target = is_trackable_forage_target

is_edible_loot = is_edible_pickup
loot_on_field = pickup_on_field


def try_pickup_loot(carrier, obj: WorldObject, contact_padding: float = 8.0) -> bool:
    if not is_haulable_pickup(obj):
        return False

    dist = distance_to_loot(carrier, obj)
    reach = pickup_radius(obj) + float(contact_padding)
    if dist > reach * 1.05:
        return False

    world = carrier.world
    wos = getattr(world, "world_object_system", None)
    if wos is None or not loot_on_field(world, obj):
        return False

    inv = get_creature_inventory(carrier)
    if inv is None or inv.empty_slot_count <= 0:
        return False

    stack = obj.storage.stack if obj.storage else None
    if stack is None:
        return False

    picked = False
    picked_amount = 0.0
    picked_item_type = ""

    if obj.amount_for_kind("biomass") > 0:
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

    if not picked:
        field_item = stack.first_stack_item()
        if field_item is not None:
            for slot in inv.slots:
                if not slot.can_accept("item"):
                    continue
                taken = stack.withdraw_stack_item(field_item.item_type)
                if taken is None:
                    break
                slot.item = taken
                picked = True
                picked_item_type = taken.item_type
                picked_amount = float(taken.quantity)
                break

    if obj.is_pickup_depleted() and obj.deplete_when_empty:
        wos.remove_instance(obj.id)

    if picked and world is not None:
        from src.sim.emitters import emit_item_found

        kind = picked_item_type or "biomass"
        emit_item_found(world, carrier, item_kind=kind, amount=picked_amount)
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
    if not is_pickable_pickup(obj):
        return False
    if obj.pickup_species_filter:
        return False
    if not is_edible_pickup(obj) and not is_haulable_pickup(obj):
        return False
    return distance_to_loot(creature, obj) <= creature.get_current_vision()


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
    loots.sort(key=lambda obj: distance_to_loot(predator, obj))
    return consume_loot_biomass(predator, loots[0], bite_gain=bite_gain)
