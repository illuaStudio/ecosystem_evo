"""コロニーテリトリー・勢力 ID 解決。"""
import math

from src.sim.utils.position_helpers import entity_xy

def expand_faction_species(world, colony_ids) -> tuple[str, ...]:
    """勢力 ID からそのコロニーに属する全種名を列挙（world.colony.faction_species）。"""
    if world is None:
        return ()
    faction_species = getattr(world, "faction_species", {}) or {}
    names: list[str] = []
    for cid in colony_ids or ():
        for name in faction_species.get(cid, ()):
            if name not in names:
                names.append(str(name))
    return tuple(names)

DEFAULT_TERRITORY_RADIUS = 180.0

def resolve_colony_id(species_name: str, colony_cfg: dict | None = None) -> str:
    """種設定から勢力 ID を解決（join_species / join_colony_id 対応）。"""
    cfg = colony_cfg or {}
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
        return resolve_colony_id(join_species, join_data.get("colony", {}))
    return str(species_name)

def get_territory_radius_for_nest(world, nest) -> float:
    """巣の owner 種の colony.territory_radius（未設定時は既定 180）。"""
    if world is None or nest is None:
        return DEFAULT_TERRITORY_RADIUS
    from src.config import config

    species_data = config.get_species(nest.owner_species) or {}
    cfg = species_data.get("colony", {})
    return float(cfg.get("territory_radius", DEFAULT_TERRITORY_RADIUS))

def iter_territory_centers(nest) -> list[tuple[float, float]]:
    """テリトリー円の中心（全巣穴。穴が無いときは巣座標）。"""
    holes = getattr(nest, "holes", None) or []
    if holes:
        return [(float(h.x), float(h.y)) for h in holes]
    return [(float(nest.x), float(nest.y))]

def distance_from_nest_center(world, nest, x: float, y: float) -> float:
    """巣備蓄座標からワールド座標までの距離（レガシー）。"""
    return math.hypot(float(x) - nest.x, float(y) - nest.y)

def is_point_in_nest_territory(world, nest, x: float, y: float) -> bool:
    """いずれかの巣穴（または巣座標）を中心とするテリトリー円内か。"""
    if world is None or nest is None:
        return False
    radius = get_territory_radius_for_nest(world, nest)
    px, py = float(x), float(y)
    for cx, cy in iter_territory_centers(nest):
        if math.hypot(px - cx, py - cy) <= radius:
            return True
    return False

def is_point_in_colony_territory(world, colony_id: str, x: float, y: float) -> bool:
    """勢力のコロニー巣テリトリー内か。"""
    if world is None or not colony_id:
        return False
    nest = world.nest_system.get_colony_nest(colony_id)
    if nest is None:
        return False
    return is_point_in_nest_territory(world, nest, x, y)

def is_point_in_creature_territory(creature, x: float, y: float) -> bool:
    """個体の所属コロニーテリトリー内か（全巣穴の円の和集合）。"""
    world = getattr(creature, "world", None)
    if world is None:
        return False
    nest = world.nest_system.get_creature_nest(creature)
    if nest is None:
        return False
    return is_point_in_nest_territory(world, nest, x, y)

def is_in_creature_territory(creature, other) -> bool:
    """他個体が自分のコロニーテリトリー内にいるか。"""
    if other is None:
        return False
    ox, oy = entity_xy(other)
    return is_point_in_creature_territory(creature, ox, oy)


def distance_to_creature_territory_edge(creature, x: float, y: float) -> float:
    """テリトリー内なら 0。外なら最寄りの境界までの距離。"""
    world = getattr(creature, "world", None)
    if world is None:
        return float("inf")
    nest = world.nest_system.get_creature_nest(creature)
    if nest is None:
        return float("inf")
    px, py = float(x), float(y)
    if is_point_in_nest_territory(world, nest, px, py):
        return 0.0
    radius = get_territory_radius_for_nest(world, nest)
    best = float("inf")
    for cx, cy in iter_territory_centers(nest):
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
