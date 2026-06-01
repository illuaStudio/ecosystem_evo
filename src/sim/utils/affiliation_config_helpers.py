"""ワールド JSON の affiliation 共通設定（profiles / min_storage_reserve）解決。

旧 colony_* は廃止し、affiliation を所属・拠点の一般名として扱う。
"""

from __future__ import annotations

AFFILIATION_PROFILE_REQUIRED_KEYS = frozenset(
    {
        "nest_x",
        "nest_y",
        "territory_radius",
        "max_mass",
        "initial_mass",
        "storage_leak_per_tick",
        "storage_leak_reserve_ratio",
        "spawn_spread",
    }
)

# 種 JSON の affiliation に残す上書き可能キー（拠点プロファイルへのマージ）
SPECIES_AFFILIATION_OVERRIDE_KEYS = frozenset(
    {
        "hide_radius",
        "spawn_spread",
        "max_mass",
        "initial_mass",
        "initial_food",
    }
)


def get_affiliation_settings(world) -> dict:
    return getattr(world, "affiliation_settings", {}) or {}


def get_affiliation_profiles(world) -> dict[str, dict]:
    profiles = getattr(world, "affiliation_profiles", None)
    if profiles is not None:
        return profiles
    return dict(get_affiliation_settings(world).get("profiles") or {})


def get_affiliation_profile(world, affiliation_id: str) -> dict:
    if not affiliation_id:
        return {}
    profile = dict(get_affiliation_profiles(world).get(affiliation_id) or {})
    if not profile:
        return profile
    return profile


def get_min_storage_reserve(world) -> float:
    """接続点設置・産卵で共有する最低食料備蓄。"""
    cfg = get_affiliation_settings(world)
    if "min_storage_reserve" not in cfg:
        raise KeyError("world affiliation.min_storage_reserve が未設定です")
    return float(cfg["min_storage_reserve"])


def _cfg_value(cfg: dict, key: str, legacy_key: str, default):
    if key in cfg:
        return cfg[key]
    return cfg.get(legacy_key, default)


def get_access_deposit_cost(cfg: dict) -> float:
    return float(_cfg_value(cfg, "access_deposit_cost", "hole_food_cost", 250.0))


def get_max_access_points(cfg: dict) -> int:
    return int(_cfg_value(cfg, "max_access_points", "max_holes", 8))


def get_min_access_spacing(cfg: dict) -> float:
    return float(_cfg_value(cfg, "min_access_spacing", "min_hole_spacing", 120.0))


def get_access_max_hp(cfg: dict) -> float:
    return float(_cfg_value(cfg, "access_max_hp", "hole_max_hp", 120.0))


def resolve_affiliation_runtime_cfg(
    world,
    affiliation_id: str,
    species_affiliation_cfg: dict | None = None,
) -> dict:
    """ワールド profiles[affiliation_id] + 種別の上書き（hide_radius 等）。"""
    merged = {
        # profiles が無い/不足する world でも NestSystem が動けるように既定値を入れる
        "territory_radius": 180.0,
        "max_mass": 400.0,
        "initial_mass": 0.0,
        "storage_leak_per_tick": 0.0,
        "storage_leak_reserve_ratio": 0.15,
        "spawn_spread": 28.0,
    }
    merged.update(get_affiliation_profile(world, affiliation_id))
    species_cfg = species_affiliation_cfg or {}
    for key in SPECIES_AFFILIATION_OVERRIDE_KEYS:
        if key in species_cfg:
            merged[key] = species_cfg[key]
    return merged

