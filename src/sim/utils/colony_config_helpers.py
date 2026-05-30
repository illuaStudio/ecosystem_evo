"""ワールド JSON のコロニー共通設定（profiles / min_food_reserve）解決。"""
from __future__ import annotations

DEFAULT_MIN_FOOD_RESERVE = 72.0

# 種 JSON の colony に残す上書き可能キー（巣プロファイルへのマージ）
SPECIES_COLONY_OVERRIDE_KEYS = frozenset({
    "hide_radius",
    "spawn_spread",
    "max_food",
    "initial_stored_food",
    "initial_food",
})


def get_colony_settings(world) -> dict:
    return getattr(world, "colony_settings", {}) or {}


def get_colony_profiles(world) -> dict[str, dict]:
    profiles = getattr(world, "colony_profiles", None)
    if profiles is not None:
        return profiles
    return dict(get_colony_settings(world).get("profiles") or {})


def get_colony_profile(world, colony_id: str) -> dict:
    if not colony_id:
        return {}
    return dict(get_colony_profiles(world).get(colony_id) or {})


def get_min_food_reserve(world) -> float:
    """巣穴設置・産卵で共有する最低食料備蓄。"""
    cfg = get_colony_settings(world)
    if "min_food_reserve" in cfg:
        return float(cfg["min_food_reserve"])
    if "hole_min_food_reserve" in cfg:
        return float(cfg["hole_min_food_reserve"])
    return DEFAULT_MIN_FOOD_RESERVE


def resolve_colony_runtime_cfg(
    world,
    colony_id: str,
    species_colony_cfg: dict | None = None,
) -> dict:
    """ワールド profiles[colony_id] + 種別の上書き（hide_radius 等）。"""
    merged = get_colony_profile(world, colony_id)
    species_cfg = species_colony_cfg or {}
    for key in SPECIES_COLONY_OVERRIDE_KEYS:
        if key in species_cfg:
            merged[key] = species_cfg[key]
    return merged
