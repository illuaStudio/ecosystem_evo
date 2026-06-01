"""テスト用: field_drop 死後の地面バイオマス取得。"""
from __future__ import annotations

from src.sim.utils.field_pickup_helpers import iter_pickup_in_radius
from src.sim.utils.position_helpers import entity_xy


def kill_creature(world, prey, predator=None, *, attack_power: float = 2.5):
    """殺害して field_drop し、地面バイオマスを返す。"""
    if predator is not None:
        from src.sim.utils.combat_helpers import try_attack_only

        while prey.alive:
            try_attack_only(predator, prey, attack_power=attack_power)
    else:
        prey.become_corpse()
    return loot_after_death(world, prey)


def pickup_field_biomass(carrier, loot) -> bool:
    from src.sim.utils.combat_helpers import try_pickup_field_biomass

    return try_pickup_field_biomass(carrier, loot)


def loot_after_death(world, creature):
    """become_corpse(field_drop) 直後、同位置付近の field バイオマスを返す。"""
    pickups = [
        o
        for o in world.world_object_system.iter_field_pickups()
        if not o.is_pickup_depleted()
    ]
    if len(pickups) == 1:
        return pickups[0]
    cx, cy = entity_xy(creature)
    matches = iter_pickup_in_radius(
        world,
        cx,
        cy,
        24.0,
        species_names=[creature.species.name],
    )
    return matches[0] if matches else None
