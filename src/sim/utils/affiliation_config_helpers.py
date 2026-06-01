"""ワールド JSON の affiliation ブロック解釈（sim 内完結。型は game.ColonyConfig と同形）。"""

from __future__ import annotations



from typing import Any



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



SPECIES_AFFILIATION_OVERRIDE_KEYS = frozenset(

    {

        "hide_radius",

        "spawn_spread",

        "max_mass",

        "initial_mass",

        "initial_food",

    }

)





def _affiliation_layout(world):

    return getattr(world, "_affiliation_layout", None)





def _raw_affiliation(world) -> dict:

    return dict(getattr(world, "_affiliation_layout_raw", None) or {})





def _profiles_from_raw(raw: dict) -> dict[str, dict]:

    return {str(k): dict(v) for k, v in (raw.get("profiles") or {}).items()}





def _settings_from_raw(raw: dict) -> dict:

    block = dict(raw)

    block.pop("factions", None)

    block.pop("affiliation_species", None)

    block.pop("profiles", None)

    return block





def get_affiliation_settings(world) -> dict:

    cfg = _affiliation_layout(world)

    if cfg is not None:

        return dict(cfg.settings)

    return _settings_from_raw(_raw_affiliation(world))





def get_affiliation_profiles(world) -> dict[str, dict]:

    cfg = _affiliation_layout(world)

    if cfg is not None:

        return cfg.profiles

    return _profiles_from_raw(_raw_affiliation(world))





def get_affiliation_profile(world, affiliation_id: str) -> dict:

    if not affiliation_id:

        return {}

    return dict(get_affiliation_profiles(world).get(affiliation_id) or {})





def get_min_storage_reserve(world) -> float:

    cfg = get_affiliation_settings(world)

    if "min_storage_reserve" not in cfg:

        raise KeyError("world affiliation.min_storage_reserve が未設定です")

    return float(cfg["min_storage_reserve"])





def _cfg_value(cfg: dict, key: str, legacy_key: str, default: Any):

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

    merged = {

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


