"""獲物・敵対の探索と判定。"""
from src.sim.shelter.state import is_creature_sheltered
from src.sim.utils.geo_helpers import distance_between, is_in_vision
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
        return False
    if living_only:
        return bool(target.alive)
    return bool(target.alive)


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
    """戦闘対象（生きている指定種のみ）。"""
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
    from src.sim.combat.target_query import find_nearest_hostile_creature

    ref = find_nearest_hostile_creature(
        creature,
        tuple(species_names),
        territory_only=False,
        exclude=exclude,
    )
    return ref.as_creature() if ref else None


def find_nearest_hostile_in_territory_among(creature, species_names, exclude=None):
    from src.sim.combat.target_query import find_nearest_hostile_creature

    ref = find_nearest_hostile_creature(
        creature,
        tuple(species_names),
        territory_only=True,
        exclude=exclude,
    )
    return ref.as_creature() if ref else None


def find_nearest_edible_in_territory_among(creature, species_names, exclude=None):
    from src.sim.combat.target_query import find_nearest_prey_creature

    ref = find_nearest_prey_creature(
        creature,
        tuple(species_names),
        territory_only=True,
        exclude=exclude,
    )
    return ref.as_creature() if ref else None


def find_nearest_edible_among(creature, species_names, exclude=None):
    """複数種のうち視界内で最も近い獲物または地面バイオマス。"""
    from src.sim.combat.pickup_target import (
        distance_to_forage,
        find_nearest_field_pickup_among,
    )
    from src.sim.combat.target_query import find_nearest_prey_creature

    loot = find_nearest_field_pickup_among(creature, species_names)
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


def is_living_prey(target, species_name: str) -> bool:
    return target is not None and target.alive and target.species.name == species_name


def is_edible_target(creature, target, species_name: str) -> bool:
    if target is None or target is creature:
        return False
    if target.species.name != species_name:
        return False
    return bool(target.alive)


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
