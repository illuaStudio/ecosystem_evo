"""ゲーム層: affiliation レイアウト参照（実体は sim.AffiliationLayoutState）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.sim.affiliation_layout import AffiliationLayoutState

if TYPE_CHECKING:
    from src.sim.systems.world import World

ColonyConfig = AffiliationLayoutState

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


def colony_config(world: "World") -> AffiliationLayoutState:
    cfg = getattr(world, "_affiliation_layout", None)
    if cfg is None:
        raise RuntimeError(
            "affiliation レイアウトが未設定です。GameController.reset_for_world または "
            "tests.sim.colony_binding.bind_colony を呼んでください。"
        )
    return cfg


def try_colony_config(world: "World") -> AffiliationLayoutState | None:
    return getattr(world, "_affiliation_layout", None)


def get_affiliation_settings(world: "World") -> dict:
    cfg = try_colony_config(world)
    return dict(cfg.settings) if cfg else {}


def get_affiliation_profiles(world: "World") -> dict[str, dict]:
    cfg = try_colony_config(world)
    if cfg is None:
        return {}
    return cfg.profiles


def get_affiliation_profile(world: "World", affiliation_id: str) -> dict:
    cfg = try_colony_config(world)
    if cfg is None:
        return {}
    return cfg.get_profile(affiliation_id)


def get_min_storage_reserve(world: "World") -> float:
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
    world: "World",
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


def expand_affiliation_species(world: "World", affiliation_ids) -> tuple[str, ...]:
    cfg = try_colony_config(world)
    if cfg is None:
        return ()
    names: list[str] = []
    for aid in affiliation_ids:
        for name in cfg.species_by_affiliation.get(str(aid), ()):
            if name not in names:
                names.append(str(name))
    return tuple(names)


def get_rival_affiliation_ids(world: "World", affiliation_id: str) -> list[str]:
    cfg = try_colony_config(world)
    if cfg is None or not affiliation_id:
        return []
    style = cfg.styles.get(str(affiliation_id), {})
    rivals = style.get("rivals") or style.get("hostile_affiliations") or ()
    return [str(r) for r in rivals]
