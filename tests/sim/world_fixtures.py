"""テスト用ワールド JSON 断片（コード既定フォールバックなし）。"""

from __future__ import annotations

from typing import Any, Dict, List

MICRO_FAUNA_PREY = (
    "springtail",
    "soil_mite",
    "aphid_larva",
    "woodlouse",
    "grub",
)

DEFAULT_TEST_PREY = MICRO_FAUNA_PREY[0]

RED_ANT_PROFILE = {
    "nest_x": 120,
    "nest_y": 120,
    "territory_radius": 180,
    "max_food": 5000,
    "initial_stored_food": 80,
    "food_leak_per_tick": 0.5,
    "food_leak_reserve_ratio": 0.15,
    "spawn_spread": 28,
}

BLUE_ANT_PROFILE = {
    "nest_x": 500,
    "nest_y": 820,
    "territory_radius": 180,
    "max_food": 5000,
    "initial_stored_food": 80,
    "food_leak_per_tick": 0.5,
    "food_leak_reserve_ratio": 0.15,
    "spawn_spread": 28,
}

YELLOW_ANT_PROFILE = {
    "nest_x": 880,
    "nest_y": 120,
    "territory_radius": 180,
    "max_food": 5000,
    "initial_stored_food": 80,
    "food_leak_per_tick": 0.5,
    "food_leak_reserve_ratio": 0.15,
    "spawn_spread": 28,
}

MINIMAL_TEST_BIOME = {
    "biome_map_cell_size": 64,
    "biomes": [{"name": "rich", "color": "#2E8B57", "spawn_rate_multiplier": 1.0}],
    "biome_noise": {
        "scale": 0.003,
        "octaves": 2,
        "persistence": 0.55,
        "lacunarity": 2.2,
        "threshold": 0.5,
        "seed": 1,
    },
}


def affiliation_settings(**extra) -> dict:
    """巣穴・産卵共通 + 全コロニー profiles。"""
    base = {
        "min_food_reserve": 72,
        "profiles": {
            "red_ant": dict(RED_ANT_PROFILE),
            "blue_ant": dict(BLUE_ANT_PROFILE),
            "yellow_ant": dict(YELLOW_ANT_PROFILE),
        },
    }
    base.update(extra)
    return base


def affiliation_instances_from_colony(affiliation_block: dict) -> List[Dict[str, Any]]:
    """legacy: colony.profiles から colony_site + colony_access instances を生成。"""
    from src.sim.utils.world_instances import nest_profile_to_instance

    instances: List[Dict[str, Any]] = []
    profiles = affiliation_block.get("profiles") or {}
    factions = affiliation_block.get("affiliation_species") or affiliation_block.get("affiliation_species") or {}
    allowed = set(factions.keys()) if factions else None
    for affiliation_id, profile in profiles.items():
        if allowed is not None and str(affiliation_id) not in allowed:
            continue
        if not isinstance(profile, dict):
            continue
        inst = nest_profile_to_instance(str(affiliation_id), profile)
        if inst is None:
            continue
        instances.append(inst)
        cid = str(affiliation_id)
        instances.append(
            {
                "id": f"{cid}_access_main",
                "layer": "affiliation_access",
                "type": "affiliation_access",
                "parent": cid,
                "role": "access",
                "x": inst["x"],
                "y": inst["y"],
            }
        )
    return instances


def ensure_affiliation_instances(world_data: dict) -> None:
    """instances[] に colony_site/access が無ければ profiles から追加（in-place）。"""
    existing = list(world_data.get("instances") or []) if "instances" in world_data else []
    has_affiliation_layer = any(
        isinstance(entry, dict)
        and str(entry.get("layer", "")) in ("affiliation_site", "nest", "affiliation_access")
        for entry in existing
    )
    if has_affiliation_layer:
        world_data["instances"] = existing
        return

    affiliation_inst = affiliation_instances_from_colony(world_data.get("affiliation") or {})
    world_data["instances"] = existing + affiliation_inst


def build_test_world(**overrides) -> dict:
    """テスト用 world.json 相当 dict（colony instances 付き）。"""
    name = overrides.pop("name", "TestWorld")
    world_width = overrides.pop("world_width", 1000)
    world_height = overrides.pop("world_height", 1000)
    initial_entities = overrides.pop("initial_entities", {})
    affiliation = overrides.pop("affiliation", None)

    data: Dict[str, Any] = {
        "name": name,
        "world_width": world_width,
        "world_height": world_height,
        "initial_entities": initial_entities,
        "affiliation": affiliation if affiliation is not None else affiliation_settings(),
    }
    if "world" not in overrides:
        data["world"] = dict(MINIMAL_TEST_BIOME)
    data.update(overrides)
    ensure_affiliation_instances(data)
    return data


def load_test_world(**overrides):
    """build_test_world → World.from_json。"""
    from src.sim.systems.world import World

    return World.from_json(build_test_world(**overrides))


def set_affiliation_stored_food(world, affiliation_id: str, amount: float) -> None:
    """Nest ミラーと colony_site ObjectStorage の両方に備蓄を設定。"""
    world.nest_system.set_affiliation_stored_food(affiliation_id, amount)


def primary_affiliation_access(world, affiliation_id: str):
    """勢力の先頭 colony_access（テスト用）。"""
    ws = getattr(world, "world_object_system", None)
    if ws is None:
        return None
    points = ws.iter_access_points(affiliation_id)
    return points[0] if points else None
