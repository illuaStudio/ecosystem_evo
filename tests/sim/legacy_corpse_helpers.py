"""テスト用: 死骸（個体残留 / 地面ドロップ）。"""
from src.sim.behavior import set_creature_death_policy
from src.sim.utils.field_pickup_helpers import iter_pickup_in_radius
from src.sim.utils.position_helpers import entity_xy

# 攻撃で倒したとき: 個体のまま死骸質量を持たせる（即死しない）
ON_CREATURE_CORPSE_POLICY = {"steps": ["convert_corpse_mass"]}


def use_on_creature_corpse_on_death(creature) -> None:
    set_creature_death_policy(creature, ON_CREATURE_CORPSE_POLICY)


def become_creature_carcass(creature, cause: str = "hp") -> None:
    """即座に死骸化して質量を付与（運搬・分解テスト用）。"""
    set_creature_death_policy(creature, ON_CREATURE_CORPSE_POLICY)
    creature.become_corpse(cause=cause)


def become_field_drop_corpse(creature, cause: str = "hp") -> None:
    set_creature_death_policy(creature, "field_drop")
    creature.become_corpse(cause=cause)


def use_field_drop_on_death(creature) -> None:
    set_creature_death_policy(creature, "field_drop")


use_legacy_corpse_on_death = use_on_creature_corpse_on_death
become_legacy_corpse = become_creature_carcass


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
