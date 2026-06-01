"""ワールドオブジェクト階層を使った預入・Shelter 解決。"""
from __future__ import annotations

import math
from typing import Optional, Sequence, Tuple

from src.sim.shelter.types import ShelterRef
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.item_stack_helpers import transfer_kind_storage_to_creature
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


def get_affiliation_root(world, affiliation_id: str):
    """colony_site 親 WorldObject（存在しなければ None）。"""
    if world is None or not affiliation_id:
        return None
    defeated = getattr(world, "defeated_affiliations", None) or getattr(world, "defeated_affiliations", None) or set()
    if str(affiliation_id) in defeated:
        return None
    return get_compound_root(world, affiliation_id)


def get_creature_affiliation_root(creature):
    """個体の所属 colony_site 親 WorldObject。"""
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

    world = getattr(creature, "world", None)
    cid = get_creature_affiliation_id(creature)
    if world is None or not cid:
        return None
    return get_affiliation_root(world, cid)


def affiliation_stored_mass(world, affiliation_id: str, default: float = 0.0) -> float:
    root = get_affiliation_root(world, affiliation_id)
    if root is None or root.storage is None:
        return default
    return float(root.storage.stored_mass)


def affiliation_capacity(world, affiliation_id: str, default: float = 0.0) -> float:
    root = get_affiliation_root(world, affiliation_id)
    if root is None or root.storage is None:
        return default
    return float(root.storage.capacity)


def owner_species_for_affiliation(world, affiliation_id: str) -> str:
    groups = getattr(world, "affiliation_species", {}) or getattr(world, "affiliation_species", {}) or {}
    pool = groups.get(affiliation_id) or ()
    if pool:
        return str(pool[0])
    return str(affiliation_id)


def _affiliation_has_living_members(world, affiliation_id: str) -> bool:
    for creature in getattr(world, "creatures", ()) or ():
        if not getattr(creature, "alive", True):
            continue
        aff = getattr(creature, "affiliation", None)
        if aff is not None and str(getattr(aff, "affiliation_id", "") or "") == str(affiliation_id):
            return True
    return False


def _affiliation_is_active(world, affiliation_id: str) -> bool:
    """faction 所属・接続点・生存メンバーのいずれかがあれば稼働中。"""
    defeated = getattr(world, "defeated_affiliations", None) or getattr(world, "defeated_affiliations", None) or set()
    cid = str(affiliation_id)
    if cid in defeated:
        return False
    groups = getattr(world, "affiliation_species", {}) or getattr(world, "affiliation_species", {}) or {}
    if groups:
        if cid in groups:
            return True
        return _affiliation_has_living_members(world, cid)
    ws = getattr(world, "world_object_system", None)
    if ws is not None and ws.count_active_access(cid) > 0:
        return True
    return _affiliation_has_living_members(world, cid)


def iter_active_affiliation_roots(world):
    """稼働中の colony_site を列挙（マップ上の休眠拠点は除外）。"""
    ws = getattr(world, "world_object_system", None)
    if ws is None:
        return
    for root in ws.iter_roots():
        if _affiliation_is_active(world, root.id):
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
    """インベントリ内バイオマスを親オブジェクト ItemStack へ。移した量を返す。"""
    from src.sim.utils.inventory_helpers import clear_inventory_for_kind

    if not inventory_is_loaded(creature):
        return 0.0
    world = getattr(creature, "world", None)
    if world is None:
        return 0.0
    parent, _access = resolve_deposit_target(creature)
    if parent is None or parent.storage is None:
        return 0.0

    amount = clear_inventory_for_kind(creature, kind="biomass")
    if amount <= 0:
        return 0.0
    return parent.storage.deposit(amount)


def withdraw_from_parent_storage(creature, amount: float) -> float:
    """親 storage から指定 kind を取出してインベントリへ。"""
    world = getattr(creature, "world", None)
    if world is None or amount <= 0:
        return 0.0
    _parent, _access = resolve_withdraw_target(creature)
    if _parent is None or _parent.storage is None:
        return 0.0
    return transfer_kind_storage_to_creature(creature, _parent.storage, amount)


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
    if parent is None or parent.storage is None or parent.storage.stored_mass <= 0:
        return 0.0

    max_sat = float(creature.max_satiety)
    if float(creature.satiety) >= max_sat:
        return 0.0

    take = min(parent.storage.stored_mass, float(feed_per_tick))
    if take <= 0:
        return 0.0

    parent.storage.withdraw(take)
    creature.satiety = min(max_sat, creature.satiety + take * float(bite_gain))
    return take


def parent_stored_mass(creature, default: float = 0.0) -> float:
    world = getattr(creature, "world", None)
    if world is None:
        return default
    parent_ids = get_creature_compound_parent_ids(creature)
    if not parent_ids:
        return default
    cs = _compound_system(world)
    if cs is None:
        return default
    return cs.stored_mass(parent_ids[0])


def creature_has_affiliation_target(creature) -> bool:
    """預入/拠点行動の行き先があるか。"""
    if get_creature_compound_parent_ids(creature):
        parent, _access = resolve_deposit_target(creature)
        return parent is not None
    return get_creature_affiliation_root(creature) is not None


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


def iter_affiliation_access_xy(world, affiliation_id: str) -> list[tuple[float, float]]:
    """後方互換。"""
    return iter_access_xy(world, affiliation_id)


def iter_affiliation_access_for_display(world, affiliation_id: str):
    """描画・HP 表示用: colony_access オブジェクト。"""
    ws = getattr(world, "world_object_system", None)
    if ws is not None and ws.has_affiliation_root(affiliation_id):
        yield from ws.iter_access_points(affiliation_id)


def affiliation_site_xy(world, affiliation_id: str) -> tuple[float, float]:
    """拠点中心座標。"""
    root = get_affiliation_root(world, affiliation_id)
    if root is not None:
        return float(root.x), float(root.y)
    return 0.0, 0.0


def affiliation_fill_ratio(world, affiliation_id: str) -> float:
    """備蓄率 0..1。"""
    root = get_affiliation_root(world, affiliation_id)
    if root is not None and root.storage is not None and root.storage.capacity > 0:
        return max(
            0.0,
            min(1.0, root.storage.stored_mass / root.storage.capacity),
        )
    return 0.0


def access_count(world, compound_id: str) -> int:
    cs = _compound_system(world)
    if cs is not None and cs.has_root(compound_id):
        return cs.count_active_access(compound_id)
    return 0


def affiliation_access_count(world, affiliation_id: str) -> int:
    return access_count(world, affiliation_id)


def resolve_shelter_from_affiliation(world, affiliation_id: str, creature, threat=None) -> Optional[ShelterRef]:
    """勢力 ID 指定で colony_access から Shelter を解決。"""
    cs = _compound_system(world)
    if cs is None or not cs.has_root(affiliation_id):
        return None

    from src.sim.shelter.helpers import _threat_blocks_approach, get_hide_radius

    approach_radius = get_hide_radius(creature)
    cx, cy = entity_xy(creature)
    best: Optional[ShelterRef] = None
    best_dist = float("inf")

    for child in cs.iter_access_points(affiliation_id, require_shelter=True):
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
                parent_id=affiliation_id,
                x=float(child.x),
                y=float(child.y),
            )
    return best
