"""compound 配置レイヤー名（legacy エイリアス含む）。"""
from __future__ import annotations

from src.config import config
from src.sim.utils.object_capabilities import capability_block

ROOT_LAYERS = frozenset({"compound_root", "colony_site", "nest"})
ACCESS_LAYERS = frozenset({"compound_access", "colony_access"})
DEFAULT_ACCESS_TYPE = "colony_access"


def profile_for_type(type_ref: str) -> str:
    type_def = config.get_object_type(type_ref)
    compound = capability_block(type_def, "compound")
    profile = compound.get("profile")
    if profile:
        return str(profile)
    if type_ref in ("colony_site",):
        return "colony"
    return "generic"


def default_access_type_for_root(type_ref: str) -> str:
    type_def = config.get_object_type(type_ref)
    compound = capability_block(type_def, "compound")
    return str(compound.get("default_access_type", DEFAULT_ACCESS_TYPE))
