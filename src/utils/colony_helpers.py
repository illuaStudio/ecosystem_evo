"""勢力（colony_id）・テリトリー・敗北の共通判定。"""
from __future__ import annotations

from src.utils.creature_helpers import (
    is_point_in_colony_territory,
    is_point_in_nest_territory,
)
from src.utils.position_helpers import entity_xy


def list_faction_colony_ids(world) -> tuple[str, ...]:
    styles = getattr(world, "faction_styles", None) or {}
    if styles:
        return tuple(styles.keys())
    species_map = getattr(world, "faction_species", None) or {}
    return tuple(species_map.keys())


def get_rival_colony_ids(world, colony_id: str) -> tuple[str, ...]:
    """他勢力 ID（同じ world にいるコロニー）。"""
    if not colony_id:
        return ()
    return tuple(cid for cid in list_faction_colony_ids(world) if cid != colony_id)


def is_rival_colony(world, colony_a: str, colony_b: str) -> bool:
    if not colony_a or not colony_b or colony_a == colony_b:
        return False
    return colony_b in get_rival_colony_ids(world, colony_a)


def is_colony_defeated(world, colony_id: str) -> bool:
    if not colony_id or world is None:
        return False
    defeated = getattr(world, "defeated_colonies", None) or set()
    return colony_id in defeated


def get_creature_colony_id(creature) -> str | None:
    colony = getattr(creature, "colony", None)
    if colony is None:
        return None
    if getattr(colony, "defeated", False):
        return colony.colony_id
    if colony.colony_id:
        return str(colony.colony_id)
    world = getattr(creature, "world", None)
    if world is None:
        return None
    nest = world.nest_system.get_creature_nest(creature)
    if nest is not None:
        return nest.colony_id
    return None


def is_creature_colony_defeated(creature) -> bool:
    colony = getattr(creature, "colony", None)
    if colony is None:
        return False
    if getattr(colony, "defeated", False):
        return True
    cid = colony.colony_id
    if cid and creature.world is not None:
        return is_colony_defeated(creature.world, cid)
    return False


def is_point_in_rival_territory(world, colony_id: str, x: float, y: float) -> bool:
    """いずれかの敵勢力テリトリー円内か。"""
    if world is None or not colony_id:
        return False
    ns = getattr(world, "nest_system", None)
    if ns is None:
        return False
    px, py = float(x), float(y)
    for nest in ns.nests.values():
        if not is_rival_colony(world, colony_id, nest.colony_id):
            continue
        if is_point_in_nest_territory(world, nest, px, py):
            return True
    return False


def is_creature_in_colony_territory(creature, colony_id: str) -> bool:
    """個体の位置が指定勢力のテリトリー内か。"""
    if creature is None or not colony_id:
        return False
    cx, cy = entity_xy(creature)
    world = creature.world
    if world is None:
        return False
    nest = world.nest_system.get_colony_nest(colony_id)
    if nest is None:
        return False
    return is_point_in_nest_territory(world, nest, cx, cy)


def can_attack_hole(
    creature,
    hole,
    hole_owner_colony_id: str,
    *,
    unrestricted: bool = False,
) -> bool:
    """兵隊がその敵巣穴を攻撃可能か。

    unrestricted=False（防衛）: 自テリトリー内の敵穴 or 敵テリトリーへの侵攻中。
    unrestricted=True（先兵）: 視界内の敵勢力の穴ならどこでも可。
    """
    world = getattr(creature, "world", None)
    my_id = get_creature_colony_id(creature)
    if world is None or not my_id or hole is None:
        return False
    if is_creature_colony_defeated(creature):
        return False
    if not is_rival_colony(world, my_id, hole_owner_colony_id):
        return False
    if unrestricted:
        return True
    hx, hy = float(hole.x), float(hole.y)
    if is_point_in_colony_territory(world, my_id, hx, hy):
        return True
    return is_creature_in_colony_territory(creature, hole_owner_colony_id)


def find_nearest_attackable_hole(
    creature,
    hostile_colony_ids: tuple[str, ...],
    *,
    unrestricted: bool = False,
    max_distance: float | None = None,
):
    """攻撃可能な最寄り敵巣穴（hp > 0）。combat 層への薄いラッパ。"""
    from src.combat.target_query import find_nearest_spawn_node

    ref = find_nearest_spawn_node(
        creature,
        hostile_colony_ids,
        unrestricted=unrestricted,
        max_distance=max_distance,
    )
    if ref is None:
        return None
    return ref.as_spawn_pair()
