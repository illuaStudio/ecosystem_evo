"""獲物・敵対・死骸の探索と判定。"""

from src.sim.shelter.state import is_creature_sheltered
from src.sim.utils.geo_helpers import distance_between, is_in_vision, is_in_vision
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.spatial_grid import iter_creatures_in_radius

def is_edible_prey(
    creature,
    target,
    species_names,
    *,
    living_only: bool = False,
    carcass_only_species: tuple[str, ...] | list[str] | None = None,
) -> bool:
    if target is None or target is creature:
        return False
    if is_creature_sheltered(target):
        return False
    names = species_names if isinstance(species_names, (list, tuple, set)) else (species_names,)
    if target.species.name not in names:
        return False
    carcass_only = set(carcass_only_species or ())
    if target.species.name in carcass_only:
        if target.alive:
            return False
        world = getattr(creature, "world", None)
        return carcass_on_field(world, target)
    if living_only:
        return bool(target.alive)
    if target.alive:
        return True
    world = getattr(creature, "world", None)
    return carcass_on_field(world, target)

def is_trackable_prey(
    creature,
    target,
    species_names,
    *,
    living_only: bool = False,
    carcass_only_species: tuple[str, ...] | list[str] | None = None,
) -> bool:
    return is_edible_prey(
        creature,
        target,
        species_names,
        living_only=living_only,
        carcass_only_species=carcass_only_species,
    ) and is_in_vision(creature, target)

def is_hostile_target(creature, target, species_names) -> bool:
    """戦闘対象（生きている指定種のみ。死骸は対象外）。"""
    if target is None or target is creature:
        return False
    if is_creature_sheltered(target):
        return False
    names = species_names if isinstance(species_names, (list, tuple, set)) else (species_names,)
    if target.species.name not in names:
        return False
    return bool(target.alive)

def is_trackable_hostile(creature, target, species_names) -> bool:
    return is_hostile_target(creature, target, species_names) and is_in_vision(
        creature, target
    )

def find_nearest_hostile_among(creature, species_names, exclude=None):
    """視界内で最も近い敵対生体（combat/target_query に委譲）。"""
    from src.sim.combat.target_query import find_nearest_hostile_creature

    ref = find_nearest_hostile_creature(
        creature,
        tuple(species_names),
        territory_only=False,
        exclude=exclude,
    )
    return ref.as_creature() if ref else None

def find_nearest_hostile_in_territory_among(creature, species_names, exclude=None):
    """テリトリー内にいる敵対生体のうち、視界内で最も近いもの（combat/target_query に委譲）。"""
    from src.sim.combat.target_query import find_nearest_hostile_creature

    ref = find_nearest_hostile_creature(
        creature,
        tuple(species_names),
        territory_only=True,
        exclude=exclude,
    )
    return ref.as_creature() if ref else None

def find_nearest_edible_in_territory_among(creature, species_names, exclude=None):
    """テリトリー内の獲物／死骸のうち視界内で最も近いもの（combat/target_query に委譲）。"""
    from src.sim.combat.target_query import find_nearest_prey_creature

    ref = find_nearest_prey_creature(
        creature,
        tuple(species_names),
        territory_only=True,
        exclude=exclude,
    )
    return ref.as_creature() if ref else None

def find_nearest_edible_among(creature, species_names, exclude=None):
    """複数種のうち視界内で最も近い獲物／地面ルート／死骸。"""
    from src.sim.combat.pickup_target import (
        distance_to_forage,
        find_nearest_field_pickup_among,
    )

    loot = find_nearest_field_pickup_among(creature, species_names)
    from src.sim.combat.target_query import find_nearest_prey_creature

    ref = find_nearest_prey_creature(
        creature,
        tuple(species_names),
        territory_only=False,
        exclude=exclude,
    )
    best_creature = ref.as_creature() if ref else None
    if loot is None:
        return best_creature
    if best_creature is None:
        return loot
    if distance_to_forage(creature, loot) <= distance_between(creature, best_creature):
        return loot
    return best_creature

def find_nearest_field_carcass_among(creature, species_names, exclude=None):
    """視界内で最も近い、現場に残る死骸（生きた個体は除外）。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()
    cx, cy = entity_xy(creature)

    for other in iter_creatures_in_radius(creature.world, cx, cy, vision, alive_only=False):
        if other is exclude:
            continue
        if other.alive or other.species.name not in names:
            continue
        if not carcass_on_field(creature.world, other):
            continue
        dist = distance_between(creature, other)
        if dist < min_dist:
            min_dist = dist
            best = other
    return best

def has_edible_carcass(target) -> bool:
    return not target.alive and getattr(target, "remaining_mass", 0) > 0

def carcass_on_field(world, target) -> bool:
    """ワールド上に存在し、まだバイオマスが残る死骸か。"""
    if world is None or target is None:
        return False
    return target in world.creatures and has_edible_carcass(target)

def is_unclaimed_carcass(world, carcass) -> bool:
    """残存バイオマスがある死骸（複数個体が同時に回収可能）。"""
    return has_edible_carcass(carcass)

def is_living_prey(target, species_name: str) -> bool:
    return target is not None and target.alive and target.species.name == species_name

def is_edible_target(creature, target, species_name: str) -> bool:
    if target is None or target is creature:
        return False
    if target.species.name != species_name:
        return False
    if target.alive:
        return True
    world = getattr(creature, "world", None)
    return carcass_on_field(world, target)

def is_trackable_target(creature, target, species_name: str) -> bool:
    return is_edible_target(creature, target, species_name) and is_in_vision(creature, target)

def find_nearest_edible(creature, species_name: str, exclude=None):
    if not creature.world:
        return None

    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()
    cx, cy = entity_xy(creature)

    for other in iter_creatures_in_radius(creature.world, cx, cy, vision):
        if other is exclude or not is_edible_target(creature, other, species_name):
            continue
        dist = distance_between(creature, other)
        if dist < min_dist:
            min_dist = dist
            best = other
    return best

def find_nearest_carcass_in_vision(creature, species_name: str, exclude=None):
    """視界内の未運搬・指定種の死骸を探す。"""
    if not creature.world:
        return None

    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()
    cx, cy = entity_xy(creature)

    for other in iter_creatures_in_radius(creature.world, cx, cy, vision, alive_only=False):
        if other is exclude:
            continue
        if other.species.name != species_name:
            continue
        if not has_edible_carcass(other):
            continue
        dist = distance_between(creature, other)
        if dist < min_dist:
            min_dist = dist
            best = other
    return best
