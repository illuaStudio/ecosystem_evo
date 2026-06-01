"""勢力拠点（colony_site / access）への空間参照（ゲーム意味なし）。"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.world_object_helpers import get_affiliation_root

if TYPE_CHECKING:
    from src.sim.systems.world import World


def nearest_access_xy(
    world: "World",
    affiliation_id: str,
    x: float,
    y: float,
) -> tuple[float, float]:
    ws = world.world_object_system
    best = None
    best_d = float("inf")
    if ws.has_affiliation_root(affiliation_id):
        for child in ws.iter_access_points(affiliation_id):
            ax, ay = float(child.x), float(child.y)
            d = (ax - x) ** 2 + (ay - y) ** 2
            if d < best_d:
                best_d = d
                best = (ax, ay)
    if best is not None:
        return best
    root = get_affiliation_root(world, affiliation_id)
    if root is not None:
        return float(root.x), float(root.y)
    return x, y


def affiliation_target_xy(creature) -> tuple[float, float]:
    from src.sim.utils.world_object_helpers import (
        get_creature_compound_parent_ids,
        resolve_deposit_target,
    )

    if get_creature_compound_parent_ids(creature):
        _parent, access = resolve_deposit_target(creature)
        if access is not None:
            return float(access.x), float(access.y)
        if _parent is not None:
            return float(_parent.x), float(_parent.y)

    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

    affiliation_id = get_creature_affiliation_id(creature)
    if not affiliation_id or creature.world is None:
        return entity_xy(creature)
    cx, cy = entity_xy(creature)
    return nearest_access_xy(creature.world, affiliation_id, cx, cy)


def distance_to_affiliation_site(creature) -> float:
    cx, cy = entity_xy(creature)
    tx, ty = affiliation_target_xy(creature)
    return math.hypot(tx - cx, ty - cy)


def is_at_affiliation_site(creature, radius: float) -> bool:
    return distance_to_affiliation_site(creature) <= float(radius)


def register_affiliation_site(
    world: "World",
    affiliation_id: str,
    x: float,
    y: float,
    *,
    max_mass: float,
    stored_mass: float,
    with_default_access: bool = True,
) -> None:
    from src.sim.utils.field_effect_cache import invalidate_field_effect_cache

    ws = world.world_object_system
    if not ws.has_affiliation_root(affiliation_id):
        ws.ensure_affiliation_site(
            affiliation_id,
            x,
            y,
            max_mass=max_mass,
            stored_mass=stored_mass,
        )
        if with_default_access and ws.find_access_at(affiliation_id, x, y) is None:
            ws.add_access_point(affiliation_id, x, y)
    invalidate_field_effect_cache(world)
    zone_system = getattr(world, "zone_system", None)
    if zone_system is not None:
        root = ws.get(affiliation_id)
        if root is not None:
            zone_system.sync_affiliation_clearing(affiliation_id, root.x, root.y)
