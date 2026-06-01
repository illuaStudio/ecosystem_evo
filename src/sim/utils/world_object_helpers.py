"""ワールドオブジェクト階層を使った預入・Shelter 解決。"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

from src.sim.shelter.types import ShelterRef
from src.sim.utils.inventory_helpers import clear_inventory_biomass, inventory_is_loaded
from src.sim.utils.position_helpers import entity_xy


def get_compound_root(world, compound_id: str):
    """storage 親 WorldObject（汎用。敗北フィルタなし）。"""
    if world is None or not compound_id:
        return None
    cs = getattr(world, "compound_system", None)
    if cs is not None:
        return cs.get_root(str(compound_id))
    ws = getattr(world, "world_object_system", None)
    if ws is None:
        return None
    root = ws.get(str(compound_id))
    if root is not None and root.is_root:
        return root
    return None


def get_colony_root(world, colony_id: str):
    """colony_site 親 WorldObject（存在しなければ None）。"""
    if world is None or not colony_id:
        return None
    defeated = getattr(world, "defeated_colonies", None) or set()
    if str(colony_id) in defeated:
        return None
    return get_compound_root(world, colony_id)


def get_creature_colony_root(creature):
    """個体の所属 colony_site 親 WorldObject。"""
    from src.sim.utils.colony_helpers import get_creature_colony_id

    world = getattr(creature, "world", None)
    cid = get_creature_colony_id(creature)
    if world is None or not cid:
        return None
    return get_colony_root(world, cid)


def colony_stored_food(world, colony_id: str, default: float = 0.0) -> float:
    root = get_colony_root(world, colony_id)
    if root is None or root.storage is None:
        return default
    return float(root.storage.stored_food)


def colony_max_food(world, colony_id: str, default: float = 0.0) -> float:
    root = get_colony_root(world, colony_id)
    if root is None or root.storage is None:
        return default
    return float(root.storage.max_food)


def owner_species_for_colony(world, colony_id: str) -> str:
    factions = getattr(world, "faction_species", {}) or {}
    pool = factions.get(colony_id) or ()
    if pool:
        return str(pool[0])
    return str(colony_id)


def _colony_has_living_members(world, colony_id: str) -> bool:
    for creature in getattr(world, "creatures", ()) or ():
        if not getattr(creature, "alive", True):
            continue
        colony = getattr(creature, "colony", None)
        if colony is not None and str(colony.colony_id) == str(colony_id):
            return True
    return False


def _colony_is_active(world, colony_id: str) -> bool:
    """faction 所属・接続点・生存メンバーのいずれかがあれば稼働中。"""
    defeated = getattr(world, "defeated_colonies", None) or set()
    cid = str(colony_id)
    if cid in defeated:
        return False
    factions = getattr(world, "faction_species", {}) or {}
    if factions:
        if cid in factions:
            return True
        return _colony_has_living_members(world, cid)
    ws = getattr(world, "world_object_system", None)
    if ws is not None and ws.count_active_access(cid) > 0:
        return True
    return _colony_has_living_members(world, cid)


def iter_active_colony_roots(world):
    """稼働中の colony_site を列挙（マップ上の休眠拠点は除外）。"""
    ws = getattr(world, "world_object_system", None)
    if ws is None:
        return
    for root in ws.iter_roots():
        if _colony_is_active(world, root.id):
            yield root


def get_creature_compound_parent_ids(creature) -> Tuple[str, ...]:
    """Game / AI が渡した compound 親 ID 列。"""
    raw = getattr(creature, "compound_parent_object_ids", None)
    if raw is None:
        raw = getattr(creature, "nest_parent_object_ids", None) or ()
    return tuple(str(x) for x in raw if x)


def get_creature_nest_parent_ids(creature) -> Tuple[str, ...]:
    """後方互換。"""
    return get_creature_compound_parent_ids(creature)


def set_creature_compound_parent_ids(creature, parent_ids: Sequence[str]) -> None:
    creature.nest_parent_object_ids = tuple(str(x) for x in parent_ids if x)


def set_creature_nest_parent_ids(creature, parent_ids: Sequence[str]) -> None:
    set_creature_compound_parent_ids(creature, parent_ids)


def _compound_system(world):
    return getattr(world, "compound_system", None)


def resolve_deposit_target(creature) -> Tuple[Optional[object], Optional[object]]:
    """最寄りの (親, 預入接続子)。"""
    world = getattr(creature, "world", None)
    if world is None:
        return None, None
    cs = _compound_system(world)
    if cs is None:
        return None, None
    parent_ids = get_creature_compound_parent_ids(creature)
    if not parent_ids:
        return None, None
    cx, cy = entity_xy(creature)
    return cs.find_nearest_access(
        parent_ids,
        cx,
        cy,
        require_deposit=True,
    )


def resolve_withdraw_target(creature) -> Tuple[Optional[object], Optional[object]]:
    """最寄りの (親, 取出接続子)。"""
    world = getattr(creature, "world", None)
    if world is None:
        return None, None
    cs = _compound_system(world)
    if cs is None:
        return None, None
    parent_ids = get_creature_compound_parent_ids(creature)
    if not parent_ids:
        return None, None
    cx, cy = entity_xy(creature)
    return cs.find_nearest_access(
        parent_ids,
        cx,
        cy,
        require_withdraw=True,
    )


def deposit_carried_to_parent(creature) -> float:
    """インベントリ内バイオマスを親オブジェクト備蓄へ。移した量を返す。"""
    if not inventory_is_loaded(creature):
        return 0.0
    world = getattr(creature, "world", None)
    if world is None:
        return 0.0
    parent, _access = resolve_deposit_target(creature)
    if parent is None:
        return 0.0

    amount = clear_inventory_biomass(creature)
    if amount <= 0:
        return 0.0

    cs = _compound_system(world)
    if cs is None:
        return 0.0
    deposited = cs.deposit_to_parent(parent.id, amount)
    return deposited


def resolve_shelter_from_parents(creature, threat=None) -> Optional[ShelterRef]:
    """親オブジェクト配下の Shelter 接続点を解決。"""
    world = getattr(creature, "world", None)
    if world is None:
        return None
    cs = _compound_system(world)
    if cs is None:
        return None

    parent_ids = get_creature_compound_parent_ids(creature)
    if not parent_ids:
        return None

    from src.sim.shelter.helpers import _threat_blocks_approach, get_hide_radius

    approach_radius = get_hide_radius(creature)
    cx, cy = entity_xy(creature)

    best: Optional[ShelterRef] = None
    best_dist = float("inf")

    for pid in parent_ids:
        parent = cs.get_root(pid)
        if parent is None:
            continue
        for child in cs.iter_access_points(pid, require_shelter=True):
            if _threat_blocks_approach(
                creature, child.x, child.y, threat, approach_radius=approach_radius
            ):
                continue
            dist = math.hypot(child.x - cx, child.y - cy)
            if dist < best_dist:
                best_dist = dist
                best = ShelterRef(
                    kind="compound_access",
                    object_id=child.id,
                    parent_id=pid,
                    x=float(child.x),
                    y=float(child.y),
                )
    return best


def feed_creature_from_parent(creature, *, bite_gain: float = 1.2, feed_per_tick: float = 11.0) -> float:
    """親オブジェクト備蓄から満腹度回復。"""
    world = getattr(creature, "world", None)
    if world is None:
        return 0.0
    parent_ids = get_creature_compound_parent_ids(creature)
    if not parent_ids:
        return 0.0

    cs = _compound_system(world)
    if cs is None:
        return 0.0
    parent_id = parent_ids[0]
    parent = cs.get_root(parent_id)
    if parent is None or parent.storage is None or parent.storage.stored_food <= 0:
        return 0.0

    max_sat = float(creature.max_satiety)
    if float(creature.satiety) >= max_sat:
        return 0.0

    take = min(parent.storage.stored_food, float(feed_per_tick))
    if take <= 0:
        return 0.0

    parent.storage.withdraw(take)
    creature.satiety = min(max_sat, creature.satiety + take * float(bite_gain))
    return take


def parent_stored_food(creature, default: float = 0.0) -> float:
    world = getattr(creature, "world", None)
    if world is None:
        return default
    parent_ids = get_creature_compound_parent_ids(creature)
    if not parent_ids:
        return default
    cs = _compound_system(world)
    if cs is None:
        return default
    return cs.stored_food(parent_ids[0])


def creature_has_colony_target(creature) -> bool:
    """預入/拠点行動の行き先があるか。"""
    if get_creature_compound_parent_ids(creature):
        parent, _access = resolve_deposit_target(creature)
        return parent is not None
    return get_creature_colony_root(creature) is not None


def iter_obstacle_objects(world):
    """WorldObjectSystem 上の静的障害物を列挙。"""
    ws = getattr(world, "world_object_system", None)
    if ws is None:
        return
    yield from ws.iter_obstacles()


def iter_access_xy(world, compound_id: str) -> list[tuple[float, float]]:
    """描画・距離用: access 座標。"""
    cs = _compound_system(world)
    if cs is not None and cs.has_root(compound_id):
        points = cs.iter_access_xy(compound_id)
        if points:
            return points
    root = get_compound_root(world, compound_id)
    if root is not None:
        return [(float(root.x), float(root.y))]
    return []


def iter_colony_access_xy(world, colony_id: str) -> list[tuple[float, float]]:
    """後方互換。"""
    return iter_access_xy(world, colony_id)


def iter_colony_access_for_display(world, colony_id: str):
    """描画・HP 表示用: colony_access オブジェクト。"""
    ws = getattr(world, "world_object_system", None)
    if ws is not None and ws.has_colony_root(colony_id):
        yield from ws.iter_access_points(colony_id)


def colony_site_xy(world, colony_id: str) -> tuple[float, float]:
    """拠点中心座標。"""
    root = get_colony_root(world, colony_id)
    if root is not None:
        return float(root.x), float(root.y)
    return 0.0, 0.0


def colony_food_ratio(world, colony_id: str) -> float:
    """備蓄率 0..1。"""
    root = get_colony_root(world, colony_id)
    if root is not None and root.storage is not None and root.storage.max_food > 0:
        return max(
            0.0,
            min(1.0, root.storage.stored_food / root.storage.max_food),
        )
    return 0.0


def access_count(world, compound_id: str) -> int:
    cs = _compound_system(world)
    if cs is not None and cs.has_root(compound_id):
        return cs.count_active_access(compound_id)
    return 0


def colony_access_count(world, colony_id: str) -> int:
    return access_count(world, colony_id)


def resolve_shelter_from_colony(world, colony_id: str, creature, threat=None) -> Optional[ShelterRef]:
    """勢力 ID 指定で colony_access から Shelter を解決。"""
    cs = _compound_system(world)
    if cs is None or not cs.has_root(colony_id):
        return None

    from src.sim.shelter.helpers import _threat_blocks_approach, get_hide_radius

    approach_radius = get_hide_radius(creature)
    cx, cy = entity_xy(creature)
    best: Optional[ShelterRef] = None
    best_dist = float("inf")

    for child in cs.iter_access_points(colony_id, require_shelter=True):
        if _threat_blocks_approach(
            creature, child.x, child.y, threat, approach_radius=approach_radius
        ):
            continue
        dist = math.hypot(child.x - cx, child.y - cy)
        if dist < best_dist:
            best_dist = dist
            best = ShelterRef(
                kind="compound_access",
                object_id=child.id,
                parent_id=colony_id,
                x=float(child.x),
                y=float(child.y),
            )
    return best
