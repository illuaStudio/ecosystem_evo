"""テスト用: 旧来の死骸個体ポリシー・地面ルート。"""
from src.sim.behavior import set_creature_death_policy
from src.sim.utils.position_helpers import entity_xy


def become_legacy_corpse(creature, cause: str = "hp") -> None:
    set_creature_death_policy(creature, "biomass_corpse_legacy")
    creature.become_corpse(cause=cause)


def use_legacy_corpse_on_death(creature) -> None:
    set_creature_death_policy(creature, "biomass_corpse_legacy")


def loot_after_death(world, creature):
    loots = list(world.ground_loot_system.loots.values())
    if len(loots) == 1:
        return loots[0]
    cx, cy = entity_xy(creature)
    matches = world.ground_loot_system.iter_in_radius(
        cx,
        cy,
        24.0,
        species_names=[creature.species.name],
    )
    return matches[0] if matches else None
