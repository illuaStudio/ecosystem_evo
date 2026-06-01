"""採餌・地面ドロップ（field WorldObject / 死骸）の探索と取得。"""
from __future__ import annotations

from src.sim.combat.pickup_target import (
    PickupTarget,
    consume_forage_target,
    distance_to_forage,
    find_nearest_field_pickup_among,
    find_nearest_forage_among,
    is_forage_field_target,
    is_trackable_forage_target,
    move_toward_forage_target,
    try_pickup_forage_target,
)
from src.sim.utils.field_pickup_helpers import (
    is_edible_pickup,
    is_haulable_pickup,
    is_pickable_pickup,
    pickup_on_field,
)
from src.sim.utils.loot_helpers import (
    consume_biomass_near,
    consume_loot_biomass,
    return_biomass_to_loot,
    spawn_drop_from_creature,
    try_pickup_loot,
)

is_forage_pickup = is_edible_pickup
is_haulable_forage = is_haulable_pickup
is_pickable_forage = is_pickable_pickup
forage_on_field = pickup_on_field
find_nearest_field_forage_among = find_nearest_field_pickup_among
try_pickup_forage = try_pickup_loot
consume_forage_mass = consume_loot_biomass
return_mass_to_forage = return_biomass_to_loot
spawn_forage_drop = spawn_drop_from_creature
consume_forage_near = consume_biomass_near
move_toward_forage = move_toward_forage_target
is_trackable_forage = is_trackable_forage_target

__all__ = [
    "PickupTarget",
    "is_forage_pickup",
    "is_haulable_forage",
    "is_pickable_forage",
    "forage_on_field",
    "distance_to_forage",
    "find_nearest_field_forage_among",
    "find_nearest_forage_among",
    "try_pickup_forage",
    "consume_forage_mass",
    "return_mass_to_forage",
    "is_trackable_forage",
    "spawn_forage_drop",
    "consume_forage_near",
    "is_forage_field_target",
    "move_toward_forage",
    "consume_forage_target",
    "try_pickup_forage_target",
    "is_trackable_forage_target",
]
