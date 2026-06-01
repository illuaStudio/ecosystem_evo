"""コロニーテリトリー・勢力 ID 解決。"""
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


# legacy alias
def expand_faction_species(world, colony_ids) -> tuple[str, ...]:
    return expand_affiliation_species(world, colony_ids)

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
    # legacy key
    cid = cfg.get("colony_id")
    if cid:
        return str(cid)
    join_cid = cfg.get("join_colony_id")
    if join_cid:
        return str(join_cid)

    join_species = cfg.get("join_species")
    if join_species:
        from src.config import config

        join_data = config.get_species(join_species) or {}
        # affiliation が無い種は colony を自動変換している（Species 側）ので両方見る
        return resolve_affiliation_id(
            join_species,
            (join_data.get("affiliation") or join_data.get("colony") or {}),
        )
    return str(species_name)


# legacy alias
def resolve_colony_id(species_name: str, colony_cfg: dict | None = None) -> str:
    return resolve_affiliation_id(species_name, colony_cfg)

def get_territory_radius_for_colony(world, colony_id: str) -> float:
    """コロニー profiles[colony_id].territory_radius（未設定時は既定 180）。"""
    if world is None or not colony_id:
        return DEFAULT_TERRITORY_RADIUS
    from src.sim.utils.affiliation_config_helpers import get_affiliation_profile as get_colony_profile

    profile = get_colony_profile(world, colony_id)
    return float(profile.get("territory_radius", DEFAULT_TERRITORY_RADIUS))

def get_territory_radius_for_nest(world, nest) -> float:
    """後方互換: nest は colony_site WorldObject または colony_id 相当。"""
    if nest is None:
        return DEFAULT_TERRITORY_RADIUS
    colony_id = getattr(nest, "colony_id", None) or getattr(nest, "id", None)
    if colony_id is not None:
        return get_territory_radius_for_colony(world, str(colony_id))
    return DEFAULT_TERRITORY_RADIUS

def iter_territory_centers(colony_id: str, world=None) -> list[tuple[float, float]]:
    """テリトリー円の中心（colony_access 優先）。"""
    if world is not None and colony_id:
        from src.sim.utils.world_object_helpers import iter_colony_access_xy

        points = iter_colony_access_xy(world, colony_id)
        if points:
            return points
    from src.sim.utils.world_object_helpers import colony_site_xy

    sx, sy = colony_site_xy(world, colony_id)
    if sx or sy:
        return [(sx, sy)]
    return []

def distance_from_colony_center(world, colony_id: str, x: float, y: float) -> float:
    from src.sim.utils.world_object_helpers import colony_site_xy

    cx, cy = colony_site_xy(world, colony_id)
    return math.hypot(float(x) - cx, float(y) - cy)

def distance_from_nest_center(world, nest, x: float, y: float) -> float:
    """後方互換。"""
    colony_id = getattr(nest, "colony_id", None) or getattr(nest, "id", None)
    if colony_id is None:
        return float("inf")
    return distance_from_colony_center(world, str(colony_id), x, y)

def is_point_in_colony_territory(world, colony_id: str, x: float, y: float) -> bool:
    """いずれかの colony_access を中心とするテリトリー円内か。"""
    if world is None or not colony_id:
        return False
    radius = get_territory_radius_for_colony(world, colony_id)
    px, py = float(x), float(y)
    for cx, cy in iter_territory_centers(colony_id, world):
        if math.hypot(px - cx, py - cy) <= radius:
            return True
    return False

def is_point_in_nest_territory(world, nest, x: float, y: float) -> bool:
    """後方互換: nest は colony_site WorldObject。"""
    if nest is None:
        return False
    colony_id = getattr(nest, "colony_id", None) or getattr(nest, "id", None)
    if colony_id is None:
        return False
    return is_point_in_colony_territory(world, str(colony_id), x, y)

def is_point_in_creature_territory(creature, x: float, y: float) -> bool:
    """個体の所属コロニーテリトリー内か。"""
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id as get_creature_colony_id

    world = getattr(creature, "world", None)
    if world is None:
        return False
    colony_id = get_creature_colony_id(creature)
    if not colony_id:
        return False
    return is_point_in_colony_territory(world, colony_id, x, y)

def is_in_creature_territory(creature, other) -> bool:
    """他個体が自分のコロニーテリトリー内にいるか。"""
    if other is None:
        return False
    ox, oy = entity_xy(other)
    return is_point_in_creature_territory(creature, ox, oy)


def distance_to_creature_territory_edge(creature, x: float, y: float) -> float:
    """テリトリー内なら 0。外なら最寄りの境界までの距離。"""
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id as get_creature_colony_id

    world = getattr(creature, "world", None)
    if world is None:
        return float("inf")
    colony_id = get_creature_colony_id(creature)
    if not colony_id:
        return float("inf")
    px, py = float(x), float(y)
    if is_point_in_colony_territory(world, colony_id, px, py):
        return 0.0
    radius = get_territory_radius_for_colony(world, colony_id)
    best = float("inf")
    for cx, cy in iter_territory_centers(colony_id, world):
        dist_center = math.hypot(px - cx, py - cy)
        best = min(best, max(0.0, dist_center - radius))
    return best


def is_creature_threatening_territory(
    creature, other, approach_margin: float = 0.0
) -> bool:
    """侵入、またはテリトリー境界から approach_margin 以内に接近しているか。"""
    if other is None:
        return False
    if is_in_creature_territory(creature, other):
        return True
    margin = float(approach_margin)
    if margin <= 0.0:
        return False
    ox, oy = entity_xy(other)
    return distance_to_creature_territory_edge(creature, ox, oy) <= margin
