"""ワールド JSON のコロニー共通設定（profiles / min_food_reserve）解決。"""
from __future__ import annotations

COLONY_PROFILE_REQUIRED_KEYS = frozenset({
    "nest_x",
    "nest_y",
    "territory_radius",
    "max_food",
    "initial_stored_food",
    "food_leak_per_tick",
    "food_leak_reserve_ratio",
    "spawn_spread",
})

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
    profile = dict(get_colony_profiles(world).get(colony_id) or {})
    if not profile:
        return profile
    missing = sorted(COLONY_PROFILE_REQUIRED_KEYS - profile.keys())
    if missing:
        raise KeyError(
            f"colony.profiles.{colony_id} に必須キーがありません: {missing}"
        )
    return profile


def get_min_food_reserve(world) -> float:
    """接続点設置・産卵で共有する最低食料備蓄。"""
    cfg = get_colony_settings(world)
    if "min_food_reserve" not in cfg:
        raise KeyError("world colony.min_food_reserve が未設定です")
    return float(cfg["min_food_reserve"])


def _colony_cfg_value(cfg: dict, key: str, legacy_key: str, default):
    if key in cfg:
        return cfg[key]
    return cfg.get(legacy_key, default)


def get_access_food_cost(cfg: dict) -> float:
    return float(_colony_cfg_value(cfg, "access_food_cost", "hole_food_cost", 250.0))


def get_max_access_points(cfg: dict) -> int:
    return int(_colony_cfg_value(cfg, "max_access_points", "max_holes", 8))


def get_min_access_spacing(cfg: dict) -> float:
    return float(_colony_cfg_value(cfg, "min_access_spacing", "min_hole_spacing", 120.0))


def get_access_max_hp(cfg: dict) -> float:
    return float(_colony_cfg_value(cfg, "access_max_hp", "hole_max_hp", 120.0))


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
