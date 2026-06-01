"""テスト用: 旧来の死骸個体ポリシー・地面ドロップ。"""
from src.sim.behavior import set_creature_death_policy
from src.sim.utils.field_pickup_helpers import iter_pickup_in_radius
from src.sim.utils.position_helpers import entity_xy


def become_legacy_corpse(creature, cause: str = "hp") -> None:
    set_creature_death_policy(creature, "corpse_on_creature")
    creature.become_corpse(cause=cause)


def use_legacy_corpse_on_death(creature) -> None:
    set_creature_death_policy(creature, "corpse_on_creature")


def loot_after_death(world, creature):
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
