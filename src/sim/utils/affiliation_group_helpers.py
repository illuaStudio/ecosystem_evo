"""affiliation（所属ID）・テリトリー・敗北の共通判定。"""

from __future__ import annotations

from src.sim.utils.affiliation_helpers import get_creature_affiliation_id
from src.sim.utils.creature_helpers import is_point_in_affiliation_territory, is_point_in_nest_territory
from src.sim.utils.position_helpers import entity_xy


def list_affiliation_ids(world) -> tuple[str, ...]:
    styles = getattr(world, "affiliation_styles", None) or {}
    if styles:
        return tuple(styles.keys())
    species_map = getattr(world, "affiliation_species", None) or {}
    return tuple(species_map.keys())


def get_rival_affiliation_ids(world, affiliation_id: str) -> tuple[str, ...]:
    if not affiliation_id:
        return ()
    return tuple(aid for aid in list_affiliation_ids(world) if aid != affiliation_id)


def is_rival_affiliation(world, affiliation_a: str, affiliation_b: str) -> bool:
    if not affiliation_a or not affiliation_b or affiliation_a == affiliation_b:
        return False
    return affiliation_b in get_rival_affiliation_ids(world, affiliation_a)


def is_affiliation_defeated(world, affiliation_id: str) -> bool:
    if not affiliation_id or world is None:
        return False
    defeated = getattr(world, "defeated_affiliations", None) or set()
    return affiliation_id in defeated


def is_creature_affiliation_defeated(creature) -> bool:
    if creature is None:
        return False
    aid = get_creature_affiliation_id(creature)
    if not aid or creature.world is None:
        return False
    return is_affiliation_defeated(creature.world, aid)


def is_point_in_rival_territory(world, affiliation_id: str, x: float, y: float) -> bool:
    if world is None or not affiliation_id:
        return False
    from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

    px, py = float(x), float(y)
    for root in iter_active_affiliation_roots(world):
        if not is_rival_affiliation(world, affiliation_id, root.id):
            continue
        if is_point_in_affiliation_territory(world, root.id, px, py):
            return True
    return False


def is_creature_in_affiliation_territory(creature, affiliation_id: str) -> bool:
    if creature is None or not affiliation_id:
        return False
    cx, cy = entity_xy(creature)
    world = creature.world
    if world is None:
        return False
    from src.sim.utils.world_object_helpers import get_affiliation_root

    if get_affiliation_root(world, affiliation_id) is None:
        return False
    return is_point_in_affiliation_territory(world, affiliation_id, cx, cy)


def can_attack_affiliation_access(
    creature,
    access,
    owner_affiliation_id: str,
    *,
    unrestricted: bool = False,
) -> bool:
    world = getattr(creature, "world", None)
    my_id = get_creature_affiliation_id(creature)
    if world is None or not my_id or access is None:
        return False
    if is_creature_affiliation_defeated(creature):
        return False
    if not is_rival_affiliation(world, my_id, owner_affiliation_id):
        return False
    if unrestricted:
        return True
    hx, hy = float(access.x), float(access.y)
    if is_point_in_affiliation_territory(world, my_id, hx, hy):
        return True
    return is_creature_in_affiliation_territory(creature, owner_affiliation_id)


def find_nearest_attackable_access(
    creature,
    hostile_affiliation_ids: tuple[str, ...],
    *,
    unrestricted: bool = False,
    max_distance: float | None = None,
):
    from src.sim.combat.target_query import find_nearest_affiliation_access

    ref = find_nearest_affiliation_access(
        creature,
        hostile_affiliation_ids,
        unrestricted=unrestricted,
        max_distance=max_distance,
    )
    if ref is None or ref.world_object is None:
        return None
    world = getattr(creature, "world", None)
    if world is None:
        return None
    return (ref.world_object, ref.affiliation_id or "")

