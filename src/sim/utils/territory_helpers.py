"""所属（affiliation）テリトリー・勢力 ID 解決。"""
import math

from src.sim.utils.position_helpers import entity_xy


def expand_affiliation_species(world, affiliation_ids) -> tuple[str, ...]:
    """所属 ID からそのグループに属する全種名を列挙（world.affiliation_species）。"""
    if world is None:
        return ()
    affiliation_species = getattr(world, "affiliation_species", {}) or {}
    names: list[str] = []
    for aid in affiliation_ids or ():
        for name in affiliation_species.get(aid, ()):
            if name not in names:
                names.append(str(name))
    return tuple(names)


DEFAULT_TERRITORY_RADIUS = 180.0


def resolve_affiliation_id(species_name: str, affiliation_cfg: dict | None = None) -> str:
    """種設定から affiliation_id を解決（join_species / join_affiliation_id 対応）。"""
    cfg = affiliation_cfg or {}
    aid = cfg.get("affiliation_id")
    if aid:
        return str(aid)
    join_aid = cfg.get("join_affiliation_id")
    if join_aid:
        return str(join_aid)

    join_species = cfg.get("join_species")
    if join_species:
        from src.config import config

        join_data = config.get_species(join_species) or {}
        return resolve_affiliation_id(
            join_species,
            join_data.get("affiliation") or {},
        )
    return str(species_name)


def get_territory_radius_for_affiliation(world, affiliation_id: str) -> float:
    """affiliation profiles の territory_radius（未設定時は既定 180）。"""
    if world is None or not affiliation_id:
        return DEFAULT_TERRITORY_RADIUS
    from src.sim.utils.affiliation_config_helpers import get_affiliation_profile

    profile = get_affiliation_profile(world, affiliation_id)
    return float(profile.get("territory_radius", DEFAULT_TERRITORY_RADIUS))


def get_territory_radius_for_nest(world, nest) -> float:
    if nest is None:
        return DEFAULT_TERRITORY_RADIUS
    affiliation_id = getattr(nest, "affiliation_id", None) or getattr(nest, "id", None)
    if affiliation_id is not None:
        return get_territory_radius_for_affiliation(world, str(affiliation_id))
    return DEFAULT_TERRITORY_RADIUS


def iter_territory_centers(affiliation_id: str, world=None) -> list[tuple[float, float]]:
    if world is not None and affiliation_id:
        from src.sim.utils.world_object_helpers import iter_affiliation_access_xy

        points = iter_affiliation_access_xy(world, affiliation_id)
        if points:
            return points
    from src.sim.utils.world_object_helpers import affiliation_site_xy

    sx, sy = affiliation_site_xy(world, affiliation_id)
    if sx or sy:
        return [(sx, sy)]
    return []


def distance_from_affiliation_center(world, affiliation_id: str, x: float, y: float) -> float:
    from src.sim.utils.world_object_helpers import affiliation_site_xy

    cx, cy = affiliation_site_xy(world, affiliation_id)
    return math.hypot(float(x) - cx, float(y) - cy)


def distance_from_nest_center(world, nest, x: float, y: float) -> float:
    affiliation_id = getattr(nest, "affiliation_id", None) or getattr(nest, "id", None)
    if affiliation_id is None:
        return float("inf")
    return distance_from_affiliation_center(world, str(affiliation_id), x, y)


def is_point_in_affiliation_territory(world, affiliation_id: str, x: float, y: float) -> bool:
    if world is None or not affiliation_id:
        return False
    radius = get_territory_radius_for_affiliation(world, affiliation_id)
    px, py = float(x), float(y)
    for cx, cy in iter_territory_centers(affiliation_id, world):
        if math.hypot(px - cx, py - cy) <= radius:
            return True
    return False


def is_point_in_nest_territory(world, nest, x: float, y: float) -> bool:
    if nest is None:
        return False
    affiliation_id = getattr(nest, "affiliation_id", None) or getattr(nest, "id", None)
    if affiliation_id is None:
        return False
    return is_point_in_affiliation_territory(world, str(affiliation_id), x, y)


def is_point_in_creature_territory(creature, x: float, y: float) -> bool:
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

    world = getattr(creature, "world", None)
    if world is None:
        return False
    affiliation_id = get_creature_affiliation_id(creature)
    if not affiliation_id:
        return False
    return is_point_in_affiliation_territory(world, affiliation_id, x, y)


def is_in_creature_territory(creature, other) -> bool:
    if other is None:
        return False
    ox, oy = entity_xy(other)
    return is_point_in_creature_territory(creature, ox, oy)


def distance_to_creature_territory_edge(creature, x: float, y: float) -> float:
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

    world = getattr(creature, "world", None)
    if world is None:
        return float("inf")
    affiliation_id = get_creature_affiliation_id(creature)
    if not affiliation_id:
        return float("inf")
    px, py = float(x), float(y)
    if is_point_in_affiliation_territory(world, affiliation_id, px, py):
        return 0.0
    radius = get_territory_radius_for_affiliation(world, affiliation_id)
    best = float("inf")
    for cx, cy in iter_territory_centers(affiliation_id, world):
        dist_center = math.hypot(px - cx, py - cy)
        best = min(best, max(0.0, dist_center - radius))
    return best


def is_creature_threatening_territory(
    creature, other, approach_margin: float = 0.0
) -> bool:
    if other is None:
        return False
    if is_in_creature_territory(creature, other):
        return True
    margin = float(approach_margin)
    if margin <= 0.0:
        return False
    ox, oy = entity_xy(other)
    return distance_to_creature_territory_edge(creature, ox, oy) <= margin
