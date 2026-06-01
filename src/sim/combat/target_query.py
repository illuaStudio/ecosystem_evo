"""対象の列挙・探索・有効性判定。"""
from __future__ import annotations

import math

from src.sim.combat.target_ref import TargetKind, TargetRef
from src.sim.utils.affiliation_group_helpers import (
    can_attack_affiliation_access as can_attack_colony_access,
    is_affiliation_defeated as is_colony_defeated,
)
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    is_edible_prey,
    is_hostile_target,
    is_creature_threatening_territory,
    is_in_creature_territory,
    is_trackable_hostile,
    is_trackable_prey,
)
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.spatial_grid import iter_creatures_in_radius


def vision_range(creature) -> float:
    if hasattr(creature, "get_current_vision"):
        return float(creature.get_current_vision())
    return float(creature.traits.get("base_vision", 200))


def target_position(ref: TargetRef) -> tuple[float, float]:
    if ref.kind is TargetKind.CREATURE and ref.creature is not None:
        return entity_xy(ref.creature)
    if ref.kind is TargetKind.WORLD_OBJECT and ref.world_object is not None:
        return float(ref.world_object.x), float(ref.world_object.y)
    return (0.0, 0.0)


def iter_targets(world, kinds: tuple[TargetKind, ...] | list[TargetKind]):
    """ワールド上の戦闘対象を列挙。"""
    kind_set = set(kinds)
    if TargetKind.CREATURE in kind_set:
        for c in world.creatures:
            yield TargetRef.from_creature(c)

    if TargetKind.WORLD_OBJECT not in kind_set:
        return

    ws = getattr(world, "world_object_system", None)
    if ws is None:
        return

    for root in ws.iter_roots():
        if is_colony_defeated(world, root.id):
            continue
        for child in ws.get_children(root.id):
            if float(getattr(child, "max_hp", 0)) <= 0 or child.is_destroyed:
                continue
            yield TargetRef.from_world_object(child, root.id)


def distance_to_target(creature, ref: TargetRef) -> float:
    cx, cy = entity_xy(creature)
    tx, ty = target_position(ref)
    return math.hypot(tx - cx, ty - cy)


def target_closeness(creature, ref: TargetRef, *, max_distance: float | None = None) -> float:
    if ref.kind is TargetKind.CREATURE and ref.creature is not None:
        return closeness_ratio(creature, ref.creature)
    max_d = max_distance if max_distance is not None else vision_range(creature)
    if max_d <= 0:
        return 0.0
    d = distance_to_target(creature, ref)
    return max(0.0, min(1.0, 1.0 - d / max_d))


def find_nearest_hostile_creature(
    creature,
    species_names: tuple[str, ...],
    *,
    territory_only: bool = False,
    exclude=None,
    max_distance: float | None = None,
) -> TargetRef | None:
    if not creature.world:
        return None
    names = tuple(species_names)
    max_d = vision_range(creature) if max_distance is None else float(max_distance)
    best: TargetRef | None = None
    best_d = float("inf")
    cx, cy = entity_xy(creature)

    for other in iter_creatures_in_radius(
        creature.world, cx, cy, max_d, alive_only=True
    ):
        if other is exclude or not is_hostile_target(creature, other, names):
            continue
        if territory_only and not is_in_creature_territory(creature, other):
            continue
        d = math.hypot(*(a - b for a, b in zip((cx, cy), entity_xy(other))))
        if d >= best_d:
            continue
        best_d = d
        best = TargetRef.from_creature(other)
    return best


def is_trackable_hostile_creature(
    creature,
    target,
    species_names: tuple[str, ...],
    *,
    territory_only: bool = False,
) -> bool:
    if target is None:
        return False
    if not is_trackable_hostile(creature, target, species_names):
        return False
    if territory_only and not is_in_creature_territory(creature, target):
        return False
    return True


def _prey_passes_territory_filter(
    creature,
    other,
    *,
    territory_only: bool = False,
    territory_threat: bool = False,
    territory_approach_margin: float = 0.0,
) -> bool:
    if territory_threat:
        return is_creature_threatening_territory(
            creature, other, territory_approach_margin
        )
    if territory_only:
        return is_in_creature_territory(creature, other)
    return True


def find_nearest_prey_creature(
    creature,
    species_names: tuple[str, ...],
    *,
    territory_only: bool = False,
    territory_threat: bool = False,
    territory_approach_margin: float = 0.0,
    living_only: bool = False,
    carcass_only_species: tuple[str, ...] = (),
    exclude=None,
    max_distance: float | None = None,
) -> TargetRef | None:
    if not creature.world:
        return None
    names = tuple(species_names)
    max_d = vision_range(creature) if max_distance is None else float(max_distance)
    best: TargetRef | None = None
    best_d = float("inf")
    cx, cy = entity_xy(creature)

    for other in iter_creatures_in_radius(creature.world, cx, cy, max_d):
        if other is exclude or not is_edible_prey(
            creature,
            other,
            names,
            living_only=living_only,
            carcass_only_species=carcass_only_species,
        ):
            continue
        if not _prey_passes_territory_filter(
            creature,
            other,
            territory_only=territory_only,
            territory_threat=territory_threat,
            territory_approach_margin=territory_approach_margin,
        ):
            continue
        d = math.hypot(*(a - b for a, b in zip((cx, cy), entity_xy(other))))
        if d >= best_d:
            continue
        best_d = d
        best = TargetRef.from_creature(other)
    return best


def is_trackable_prey_creature(
    creature,
    target,
    species_names: tuple[str, ...],
    *,
    territory_only: bool = False,
    territory_threat: bool = False,
    territory_approach_margin: float = 0.0,
    living_only: bool = False,
    carcass_only_species: tuple[str, ...] = (),
) -> bool:
    if target is None:
        return False
    if not is_trackable_prey(
        creature,
        target,
        species_names,
        living_only=living_only,
        carcass_only_species=carcass_only_species,
    ):
        return False
    if not _prey_passes_territory_filter(
        creature,
        target,
        territory_only=territory_only,
        territory_threat=territory_threat,
        territory_approach_margin=territory_approach_margin,
    ):
        return False
    return True


def find_nearest_colony_access(
    creature,
    hostile_colony_ids: tuple[str, ...],
    *,
    unrestricted: bool = False,
    max_distance: float | None = None,
) -> TargetRef | None:
    from src.sim.utils.colony_helpers import is_creature_colony_defeated

    if not creature.world or is_creature_colony_defeated(creature):
        return None

    max_d = vision_range(creature) if max_distance is None else float(max_distance)
    cx, cy = entity_xy(creature)
    best: TargetRef | None = None
    best_d = float("inf")

    for ref in iter_targets(creature.world, (TargetKind.WORLD_OBJECT,)):
        colony_id = ref.colony_id
        if not colony_id or colony_id not in hostile_colony_ids:
            continue
        access = ref.world_object
        if access is None:
            continue
        if not can_attack_colony_access(
            creature, access, colony_id, unrestricted=unrestricted
        ):
            continue
        tx, ty = float(access.x), float(access.y)
        d = math.hypot(tx - cx, ty - cy)
        if d > max_d or d >= best_d:
            continue
        best_d = d
        best = ref
    return best


def is_valid_colony_access(
    creature,
    ref: TargetRef,
    *,
    hostile_colony_ids: tuple[str, ...],
    unrestricted: bool = False,
) -> bool:
    if creature.world is None or ref.kind is not TargetKind.WORLD_OBJECT:
        return False
    access = ref.world_object
    colony_id = ref.colony_id
    if access is None or not colony_id:
        return False
    ws = getattr(creature.world, "world_object_system", None)
    live = ws.get(access.id) if ws is not None else None
    if live is None or live is not access:
        return False
    if is_colony_defeated(creature.world, colony_id):
        return False
    if float(live.hp) <= 0 or live.is_destroyed:
        return False
    if colony_id not in hostile_colony_ids:
        return False
    return can_attack_colony_access(
        creature, live, colony_id, unrestricted=unrestricted
    )


def colony_access_in_range(creature, ref: TargetRef, max_distance: float) -> bool:
    if ref.kind is not TargetKind.WORLD_OBJECT:
        return False
    if ref.world_object is None or float(ref.world_object.hp) <= 0:
        return False
    return distance_to_target(creature, ref) <= float(max_distance)
