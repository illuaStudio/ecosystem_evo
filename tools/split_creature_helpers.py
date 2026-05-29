"""One-off script: split creature_helpers into domain modules."""
import ast
from pathlib import Path

src_path = Path("src/utils/creature_helpers_backup.py")
if not src_path.exists():
    src_path = Path("src/utils/creature_helpers.py")
source = src_path.read_text(encoding="utf-8")
module = ast.parse(source)

items = []
for node in module.body:
    if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
        items.append((node.name, ast.get_source_segment(source, node)))
    elif isinstance(node, ast.Assign):
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in (
                "LIFE_STAGE_PIPELINE",
                "TRAIT_DISPLAY_LABELS",
                "NUTRITION_LABELS",
                "DEFAULT_TERRITORY_RADIUS",
            ):
                items.append((t.id, ast.get_source_segment(source, node)))

MODULE_MAP = {
    "geo_helpers": {
        "distance_between",
        "distance_to_point",
        "closeness_ratio",
        "is_in_vision",
        "PointTarget",
    },
    "movement_helpers": {
        "move_toward_point",
        "move_toward",
        "move_toward_contact",
        "move_away_from",
        "wander_step",
        "contact_range",
        "_sim_dt",
        "get_mana_gradient_direction",
        "get_local_mana_gradient_direction",
        "same_species_repulsion_angle",
        "count_same_species_near",
        "is_flee_threat",
        "find_nearest_flee_threat_among",
        "get_flee_safe_distance",
        "update_flee_latch",
        "refresh_flee_latch_from_species",
        "is_flee_latch_active",
        "distance_to_creature_nest",
        "is_beyond_nest_leash",
        "return_toward_nest",
    },
    "nutrition_helpers": {
        "NutritionState",
        "NUTRITION_LABELS",
        "satiety_ratio",
        "hunger_ratio",
        "get_satiety_hungry_below",
        "get_satiety_full_above",
        "satiety_feed_target",
        "satiety_room_until_feed_target",
        "needs_nest_feed",
        "get_nutrition_state",
        "is_hungry",
        "update_nutrition_recovery",
        "needs_self_feed",
        "is_satiated",
        "format_nutrition_status",
        "format_carry_status",
        "get_haul_max_carry",
        "nest_stored_food",
        "nest_has_food",
        "nest_feed_satiety_gain_estimate",
        "nest_has_usable_food",
    },
    "territory_helpers": {
        "DEFAULT_TERRITORY_RADIUS",
        "expand_faction_species",
        "resolve_colony_id",
        "get_territory_radius_for_nest",
        "iter_territory_centers",
        "distance_from_nest_center",
        "is_point_in_nest_territory",
        "is_point_in_colony_territory",
        "is_point_in_creature_territory",
        "is_in_creature_territory",
    },
    "target_helpers": {
        "is_edible_prey",
        "is_trackable_prey",
        "is_hostile_target",
        "is_trackable_hostile",
        "find_nearest_hostile_among",
        "find_nearest_hostile_in_territory_among",
        "find_nearest_edible_in_territory_among",
        "find_nearest_edible_among",
        "find_nearest_field_carcass_among",
        "has_edible_carcass",
        "carcass_on_field",
        "is_unclaimed_carcass",
        "is_living_prey",
        "is_edible_target",
        "is_trackable_target",
        "find_nearest_edible",
        "find_nearest_carcass_in_vision",
    },
    "combat_helpers": {
        "hp_ratio",
        "bite",
        "consume_carcass",
        "try_predate",
        "try_attack_only",
        "_remove_depleted_carcass",
        "release_carried_carcass",
        "try_pickup_carcass",
        "consume_carried_biomass",
    },
    "stats_helpers": {
        "current_size",
        "LIFE_STAGE_PIPELINE",
        "get_life_stage",
        "format_life_stage_line",
        "TRAIT_DISPLAY_LABELS",
        "_format_trait_number",
        "_format_trait_delta",
        "format_individual_trait_lines",
        "count_alive_by_species",
        "get_species_population_cap",
        "is_species_at_population_cap",
        "is_at_population_cap",
    },
}

HEADERS = {
    "geo_helpers": (
        '"""距離・視界・近さの幾何計算。"""\n'
        "import math\n\n"
        "from src.utils.position_helpers import entity_xy\n\n"
    ),
    "movement_helpers": (
        '"""移動・徘徊・逃走・巣への帰還。"""\n'
        "import math\n"
        "import random\n\n"
        "from src.utils.geo_helpers import PointTarget, distance_between\n"
        "from src.utils.position_helpers import entity_xy\n\n"
    ),
    "nutrition_helpers": (
        '"""満腹度・飢餓・巣の食料判定。"""\n\n'
        "from src.utils.target_helpers import has_edible_carcass\n\n"
    ),
    "territory_helpers": (
        '"""コロニーテリトリー・勢力 ID 解決。"""\n'
        "import math\n\n"
        "from src.utils.position_helpers import entity_xy\n\n"
    ),
    "target_helpers": (
        '"""獲物・敵対・死骸の探索と判定。"""\n\n'
        "from src.utils.geo_helpers import distance_between, is_in_vision\n"
        "from src.utils.position_helpers import entity_xy\n\n"
    ),
    "combat_helpers": (
        '"""攻撃・捕食・死骸・運搬チャンクの処理。"""\n\n'
        "from src.utils.geo_helpers import distance_between\n"
        "from src.utils.movement_helpers import contact_range\n"
        "from src.utils.nutrition_helpers import get_haul_max_carry\n"
        "from src.utils.position_helpers import entity_xy\n"
        "from src.utils.target_helpers import has_edible_carcass\n\n"
    ),
    "stats_helpers": (
        '"""ライフステージ・個体差表示・個体数上限。"""\n'
        "import math\n\n"
        "from src.utils.geo_helpers import distance_between\n"
        "from src.utils.position_helpers import entity_xy\n\n"
    ),
}

name_to_seg = {name: seg for name, seg in items if seg}
out_dir = Path("src/utils")

for mod, names in MODULE_MAP.items():
    parts = [HEADERS[mod]]
    for name, seg in items:
        if name in names and seg:
            parts.append(seg.rstrip() + "\n\n")
    path = out_dir / f"{mod}.py"
    path.write_text("".join(parts).rstrip() + "\n", encoding="utf-8")
    print(f"wrote {path}")

all_exports = []
for mod, names in MODULE_MAP.items():
    pub = sorted(n for n in names if n in name_to_seg)
    if pub:
        all_exports.extend(pub)

imports = []
for mod in MODULE_MAP:
    pub = sorted(n for n in MODULE_MAP[mod] if n in name_to_seg)
    if pub:
        imports.append(
            f"from src.utils.{mod} import (\n    "
            + ",\n    ".join(pub)
            + ",\n)"
        )

barrel = (
    '# creature_helpers.py\n'
    '"""生物まわりの共通計算（後方互換 re-export ハブ）。"""\n'
    + "\n".join(imports)
    + "\n\n__all__ = [\n    "
    + ",\n    ".join(f'"{n}"' for n in sorted(set(all_exports)))
    + ",\n]\n"
)
Path("src/utils/creature_helpers.py").write_text(barrel, encoding="utf-8")
print("wrote creature_helpers.py barrel")
