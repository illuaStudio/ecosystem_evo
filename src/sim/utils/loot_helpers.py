"""地面ルートの拾得・消費・探索。"""
from __future__ import annotations

import math

from src.sim.components.inventory import BiomassItem
from src.sim.entities.ground_loot import GroundLoot
from src.sim.utils.geo_helpers import distance_between
from src.sim.utils.inventory_helpers import get_creature_inventory
from src.sim.utils.movement_helpers import contact_range
from src.sim.utils.position_helpers import entity_xy


def is_edible_loot(loot: GroundLoot | None) -> bool:
    return loot is not None and not loot.is_depleted()


def loot_on_field(world, loot: GroundLoot | None) -> bool:
    if world is None or loot is None:
        return False
    gs = getattr(world, "ground_loot_system", None)
    return gs is not None and loot.id in gs.loots and is_edible_loot(loot)


def distance_to_loot(creature, loot: GroundLoot) -> float:
    cx, cy = entity_xy(creature)
    return math.hypot(loot.x - cx, loot.y - cy)


def find_nearest_field_loot_among(
    creature,
    species_names,
    exclude_loot_id: str | None = None,
):
    world = getattr(creature, "world", None)
    if world is None:
        return None
    gs = getattr(world, "ground_loot_system", None)
    if gs is None:
        return None

    names = tuple(species_names)
    vision = creature.get_current_vision()
    cx, cy = entity_xy(creature)
    candidates = gs.iter_in_radius(cx, cy, vision, species_names=names)
    best = None
    min_dist = float("inf")
    for loot in candidates:
        if exclude_loot_id and loot.id == exclude_loot_id:
            continue
        dist = math.hypot(loot.x - cx, loot.y - cy)
        if dist < min_dist:
            min_dist = dist
            best = loot
    return best


def find_nearest_field_biomass_among(creature, species_names, exclude=None):
    """地面ルートを優先し、なければ旧来の死骸個体を返す。"""
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


def try_pickup_loot(carrier, loot: GroundLoot, contact_padding: float = 8.0) -> bool:
    inv = get_creature_inventory(carrier)
    if inv is None or inv.empty_slot_count <= 0 or not is_edible_loot(loot):
        return False

    dist = distance_to_loot(carrier, loot)
    reach = float(loot.pickup_radius) + float(contact_padding)
    if dist > reach * 1.05:
        return False

    world = carrier.world
    gs = getattr(world, "ground_loot_system", None)
    if gs is None or not loot_on_field(world, loot):
        return False

    picked = False
    picked_amount = 0.0
    for slot in inv.slots:
        if not slot.can_accept("biomass"):
            continue
        if loot.biomass_amount() <= 0:
            break
        chunk = min(loot.biomass_amount(), slot.max_mass)
        if chunk <= 0:
            continue
        withdrawn = loot.stack.withdraw_biomass(chunk)
        if withdrawn <= 0:
            break
        slot.item = BiomassItem(amount=withdrawn, source_loot=loot)
        picked = True
        picked_amount += withdrawn

    if loot.is_depleted():
        gs.remove(loot)

    if picked and world is not None:
        from src.sim.emitters import emit_item_found

        emit_item_found(world, carrier, item_kind="biomass", amount=picked_amount)
    return picked


def consume_loot_biomass(
    predator,
    loot: GroundLoot,
    bite_gain: float = 1.35,
) -> float:
    if not is_edible_loot(loot):
        return 0.0

    world = predator.world
    gs = getattr(world, "ground_loot_system", None)
    if gs is None or not loot_on_field(world, loot):
        return 0.0

    base_size = float(predator.traits.get("base_size", 9.0))
    bite_gain = float(bite_gain)
    available = loot.biomass_amount()
    amount = min(
        available * 0.45,
        base_size * bite_gain * 1.6,
    )
    take = min(amount * 0.9, available)
    loot.stack.withdraw_biomass(take)

    gained = amount * bite_gain
    predator.satiety = min(predator.max_satiety, predator.satiety + gained)

    if loot.is_depleted():
        gs.remove(loot)

    return gained


def return_biomass_to_loot(world, chunk: float, loot: GroundLoot | None) -> None:
    if chunk <= 0 or loot is None:
        return
    gs = getattr(world, "ground_loot_system", None)
    if gs is None or not loot_on_field(world, loot):
        return
    loot.stack.deposit_biomass(chunk)


def is_trackable_loot(creature, loot: GroundLoot) -> bool:
    if not is_edible_loot(loot):
        return False
    cx, cy = entity_xy(creature)
    dist = math.hypot(loot.x - cx, loot.y - cy)
    return dist <= creature.get_current_vision()


def spawn_biomass_loot_from_creature(creature) -> GroundLoot | None:
    world = getattr(creature, "world", None)
    if world is None:
        return None
    gs = getattr(world, "ground_loot_system", None)
    if gs is None:
        return None
    cx, cy = entity_xy(creature)
    size = float(creature.traits.get("base_size", 9.0))
    amount = size * 200.0
    rate = float(
        creature.traits.get(
            "corpse_decompose_rate",
            0.00003,
        )
    )
    color = tuple(getattr(creature.species, "color", (140, 120, 90)))
    return gs.spawn_biomass(
        cx,
        cy,
        amount,
        decompose_rate=rate,
        source_species=creature.species.name,
        color=color,
    )


def consume_biomass_near(
    predator,
    x: float,
    y: float,
    *,
    species_name: str | None = None,
    bite_gain: float = 1.35,
    radius: float = 24.0,
) -> float:
    """死亡直後など、座標付近の地面ルートをその場で消費。"""
    world = getattr(predator, "world", None)
    gs = getattr(world, "ground_loot_system", None)
    if gs is None:
        return 0.0
    names = [species_name] if species_name else None
    loots = gs.iter_in_radius(x, y, radius, species_names=names)
    if not loots:
        return 0.0
    loots.sort(key=lambda loot: math.hypot(loot.x - x, loot.y - y))
    return consume_loot_biomass(predator, loots[0], bite_gain=bite_gain)


def is_biomass_field_target(world, target) -> bool:
    if isinstance(target, GroundLoot):
        return loot_on_field(world, target)
    from src.sim.utils.target_helpers import carcass_on_field

    return carcass_on_field(world, target)


def move_toward_biomass_target(creature, target, speed_multiplier: float = 1.0) -> float:
    from src.sim.utils.movement_helpers import move_toward, move_toward_point

    if isinstance(target, GroundLoot):
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
    if isinstance(target, GroundLoot):
        return consume_loot_biomass(predator, target, bite_gain=bite_gain)
    from src.sim.utils.combat_helpers import consume_carcass

    return consume_carcass(predator, target, bite_gain=bite_gain)


def try_pickup_biomass_target(
    carrier,
    target,
    contact_padding: float = 8.0,
) -> bool:
    if isinstance(target, GroundLoot):
        return try_pickup_loot(carrier, target, contact_padding=contact_padding)
    from src.sim.utils.inventory_helpers import try_pickup_carcass

    return try_pickup_carcass(carrier, target, contact_padding=contact_padding)


def is_trackable_biomass_target(creature, target, species_names) -> bool:
    names = tuple(species_names)
    if isinstance(target, GroundLoot):
        return target.source_species in names and is_trackable_loot(creature, target)
    from src.sim.utils.target_helpers import is_trackable_prey

    return is_trackable_prey(creature, target, names)


