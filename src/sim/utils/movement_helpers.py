"""移動・徘徊・逃走・巣への帰還。"""
import math
import random

from src.sim.utils.geo_helpers import PointTarget, distance_between
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.spatial_grid import iter_creatures_in_radius

def _movement_blocked_in_shelter(creature) -> bool:
    from src.sim.shelter.state import is_creature_sheltered

    return is_creature_sheltered(creature)


def move_toward_point(
    creature,
    x: float,
    y: float,
    speed_multiplier: float = 1.0,
    dt: float | None = None,
) -> float:
    """座標へ移動し、移動後の距離を返す。"""
    if _movement_blocked_in_shelter(creature):
        cx, cy = entity_xy(creature)
        return math.hypot(x - cx, y - cy)
    return move_toward(creature, PointTarget(x, y), speed_multiplier, dt)

def is_flee_threat(creature, other, species_names) -> bool:
    """逃走対象（指定種の生存個体）。"""
    if other is None or other is creature:
        return False
    names = species_names if isinstance(species_names, (list, tuple, set)) else (species_names,)
    if other.species.name not in names:
        return False
    return bool(getattr(other, "alive", True))

def find_nearest_flee_threat_among(creature, species_names, exclude=None):
    """視界内で最も近い逃走対象。"""
    if not creature.world:
        return None

    names = tuple(species_names)
    best = None
    min_dist = float("inf")
    vision = creature.get_current_vision()
    cx, cy = entity_xy(creature)

    for other in iter_creatures_in_radius(creature.world, cx, cy, vision, alive_only=True):
        if other is exclude or not is_flee_threat(creature, other, names):
            continue
        dist = distance_between(creature, other)
        if dist < min_dist:
            min_dist = dist
            best = other
    return best

def get_flee_safe_distance(creature) -> float:
    """この距離より脅威が近い間は逃走ラッチを維持する。"""
    custom = creature.traits.get("flee_safe_distance")
    if custom is not None:
        return float(custom)
    vision = max(creature.get_current_vision(), 1.0)
    return max(120.0, vision * 0.55)

def update_flee_latch(creature, threat_species) -> None:
    """視界内の脅威でラッチ ON。解除は safe 距離外まで。"""
    names = tuple(threat_species)
    if find_nearest_flee_threat_among(creature, names, exclude=creature) is not None:
        creature.flee_latch = True
        return
    if not getattr(creature, "flee_latch", False) or not creature.world:
        creature.flee_latch = False
        return
    safe = get_flee_safe_distance(creature)
    cx, cy = entity_xy(creature)
    for other in iter_creatures_in_radius(creature.world, cx, cy, safe, alive_only=True):
        if other is creature or not is_flee_threat(creature, other, names):
            continue
        if distance_between(creature, other) < safe:
            return
    creature.flee_latch = False

def refresh_flee_latch_from_species(creature) -> None:
    """種定義の FleeAction / SeekShelterAction から threat_species を集めてラッチを更新。"""
    if not getattr(creature, "alive", True):
        creature.flee_latch = False
        return
    from src.sim.shelter.helpers import collect_threat_species_from_mind

    threats = collect_threat_species_from_mind(creature)
    if threats:
        update_flee_latch(creature, threats)
    else:
        creature.flee_latch = False

def is_flee_latch_active(creature) -> bool:
    return bool(getattr(creature, "flee_latch", False))

def distance_to_affiliation_site(creature) -> float:
    from src.sim.utils.affiliation_site_helpers import distance_to_affiliation_site as _dist

    world = getattr(creature, "world", None)
    if world is None or getattr(creature, "affiliation", None) is None:
        return float("inf")
    return _dist(creature)


def is_beyond_affiliation_leash(creature, leash_radius) -> bool:
    if leash_radius is None:
        return False
    return distance_to_affiliation_site(creature) > float(leash_radius)


def return_toward_affiliation_site(creature, speed_multiplier: float = 1.0) -> float:
    from src.sim.utils.affiliation_site_helpers import affiliation_target_xy

    tx, ty = affiliation_target_xy(creature)
    return move_toward_point(creature, tx, ty, speed_multiplier)


def distance_to_creature_nest(creature) -> float:
    return distance_to_affiliation_site(creature)


def is_beyond_nest_leash(creature, leash_radius) -> bool:
    return is_beyond_affiliation_leash(creature, leash_radius)


def return_toward_nest(creature, speed_multiplier: float = 1.0) -> float:
    return return_toward_affiliation_site(creature, speed_multiplier)

def contact_range(creature, other, padding: float = 8.0) -> float:
    return (
        creature.traits["base_size"]
        + other.traits.get("base_size", 9)
        + padding
    )

def _sim_dt(creature, dt: float | None = None) -> float:
    if dt is not None:
        return float(dt)
    world = getattr(creature, "world", None)
    if world is None:
        return 1.0
    return float(getattr(world, "sim_dt", 1.0))

def move_away_from(
    creature,
    target,
    speed_multiplier: float = 1.0,
    dt: float | None = None,
) -> float:
    """脅威から離れる方向へ移動し、移動後の距離を返す。"""
    if _movement_blocked_in_shelter(creature):
        tx, ty = entity_xy(target)
        cx, cy = entity_xy(creature)
        return math.hypot(tx - cx, ty - cy)
    from src.sim.systems.movement_system import MovementSystem

    position = MovementSystem._require_position(creature)
    tx, ty = entity_xy(target)
    dx = position.x - tx
    dy = position.y - ty
    dist = math.hypot(dx, dy)
    if dist > 1e-6:
        creature.wander_angle = math.degrees(math.atan2(dy, dx)) % 360
    step = creature.get_current_speed() * speed_multiplier * _sim_dt(creature, dt)
    position.x += math.cos(math.radians(creature.wander_angle)) * step
    position.y += math.sin(math.radians(creature.wander_angle)) * step
    from src.sim.utils.position_helpers import sync_legacy_pos

    sync_legacy_pos(creature)
    MovementSystem.finish_move(creature, getattr(creature, "world", None))
    sync_legacy_pos(creature)
    return math.hypot(tx - position.x, ty - position.y)

def move_toward(
    creature,
    target,
    speed_multiplier: float = 1.0,
    dt: float | None = None,
    min_distance: float | None = None,
) -> float:
    """ターゲット方向へ移動し、移動後の距離を返す。"""
    if _movement_blocked_in_shelter(creature):
        tx, ty = entity_xy(target)
        cx, cy = entity_xy(creature)
        return math.hypot(tx - cx, ty - cy)
    from src.sim.systems.movement_system import MovementSystem

    return MovementSystem.move_toward(
        creature,
        target,
        speed_multiplier,
        _sim_dt(creature, dt),
        min_distance=min_distance,
    )

def move_toward_contact(
    creature,
    target,
    speed_multiplier: float = 1.0,
    contact_padding: float = 8.0,
    dt: float | None = None,
) -> float:
    """contact_range だけ近づき、相手の中心には入り込まない。"""
    standoff = contact_range(creature, target, contact_padding)
    return move_toward(
        creature,
        target,
        speed_multiplier,
        dt,
        min_distance=standoff,
    )

def wander_step(
    creature,
    angle_range: float,
    speed_multiplier: float,
    dt: float | None = None,
) -> None:
    if _movement_blocked_in_shelter(creature):
        return
    from src.sim.systems.movement_system import MovementSystem

    MovementSystem.wander_step(
        creature,
        angle_range,
        speed_multiplier,
        _sim_dt(creature, dt),
        getattr(creature, "world", None),
    )

def count_same_species_near(
    creature,
    x: float,
    y: float,
    radius: float,
    *,
    exclude_self: bool = True,
) -> int:
    """指定座標の半径内にいる同種（生存）の個体数。"""
    if not creature.world or radius <= 0:
        return 0

    species_name = creature.species.name
    count = 0
    for other in iter_creatures_in_radius(creature.world, x, y, radius, alive_only=True):
        if exclude_self and other is creature:
            continue
        if other.species.name != species_name:
            continue
        count += 1
    return count

def same_species_repulsion_angle(creature, radius: float) -> float | None:
    """近傍同種から離れる方向（度数）。近傍がなければ None。"""
    if not creature.world or radius <= 0:
        return None

    cx, cy = entity_xy(creature)
    species_name = creature.species.name
    push_x = 0.0
    push_y = 0.0

    for other in iter_creatures_in_radius(creature.world, cx, cy, radius, alive_only=True):
        if other is creature:
            continue
        if other.species.name != species_name:
            continue
        ox, oy = entity_xy(other)
        dx = cx - ox
        dy = cy - oy
        dist = math.hypot(dx, dy)
        if dist <= 1e-6 or dist > radius:
            continue
        weight = (radius - dist) / radius
        push_x += (dx / dist) * weight
        push_y += (dy / dist) * weight

    magnitude = math.hypot(push_x, push_y)
    if magnitude <= 1e-6:
        return None
    return math.degrees(math.atan2(push_y, push_x)) % 360
