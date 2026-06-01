"""マップエディタ専用: 複数 instances を1つの配置単位として扱うプリセット。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple

EDITOR_GROUP_KEY = "editor_group"
COLONY_PREFIX = "colony:"


@dataclass(frozen=True)
class CompositePart:
    layer: str
    type_ref: str
    dx: float = 0.0
    dy: float = 0.0
    props: Dict[str, Any] = field(default_factory=dict)
    instance_id: Optional[str] = None
    parent: Optional[str] = None


@dataclass(frozen=True)
class CompositeDef:
    id: str
    label: str
    parts: Tuple[CompositePart, ...]


COMPOSITES: Dict[str, CompositeDef] = {
    "healing_goddess": CompositeDef(
        id="healing_goddess",
        label="回復する女神像",
        parts=(
            CompositePart(
                layer="obstacle",
                type_ref="rock",
                props={"radius": 26},
            ),
            CompositePart(
                layer="zone",
                type_ref="poison_fog",
                props={
                    "radius": 88.0,
                    "hp_regen_per_dt": 0.025,
                    "hp_drain_per_dt": 0.0,
                    "field_tags": ["heal"],
                    "label": "女神像の回復エリア",
                },
            ),
        ),
    ),
}


def is_colony_composite(composite_id: str) -> bool:
    return str(composite_id).startswith(COLONY_PREFIX)


def colony_affiliation_id(composite_id: str) -> str:
    if not is_colony_composite(composite_id):
        raise ValueError(f"not a colony composite: {composite_id}")
    return str(composite_id)[len(COLONY_PREFIX) :]


def clearing_instance_id(affiliation_id: str) -> str:
    return f"{affiliation_id}_clearing"


def build_colony_composite(
    affiliation_id: str, profile: Mapping[str, Any]
) -> CompositeDef:
    radius = float(profile.get("spawn_exclusion_radius", 150.0))
    return CompositeDef(
        id=f"{COLONY_PREFIX}{affiliation_id}",
        label=f"コロニー ({affiliation_id})",
        parts=(
            CompositePart(
                layer="affiliation_site",
                type_ref="affiliation_site",
                props={"role": "root"},
                instance_id=affiliation_id,
            ),
            CompositePart(
                layer="affiliation_access",
                type_ref="affiliation_access",
                props={"role": "access"},
                instance_id=f"{affiliation_id}_access_main",
                parent=affiliation_id,
            ),
            CompositePart(
                layer="zone",
                type_ref="nest_clearing",
                props={"radius": radius},
                instance_id=clearing_instance_id(affiliation_id),
            ),
        ),
    )


def list_composite_ids(
    affiliation_profiles: Optional[Mapping[str, Any]] = None,
) -> list[str]:
    ids = list(COMPOSITES.keys())
    for affiliation_id in sorted((affiliation_profiles or {}).keys()):
        ids.append(f"{COLONY_PREFIX}{affiliation_id}")
    return ids


def get_composite(
    composite_id: str,
    affiliation_profiles: Optional[Mapping[str, Any]] = None,
) -> CompositeDef:
    if composite_id in COMPOSITES:
        return COMPOSITES[composite_id]
    if is_colony_composite(composite_id):
        affiliation_id = colony_affiliation_id(composite_id)
        profiles = affiliation_profiles or {}
        if affiliation_id not in profiles:
            raise KeyError(f"unknown affiliation profile: {affiliation_id}")
        return build_colony_composite(affiliation_id, profiles[affiliation_id])
    raise KeyError(f"unknown composite: {composite_id}")


def composite_label(
    composite_id: str,
    affiliation_profiles: Optional[Mapping[str, Any]] = None,
) -> str:
    return get_composite(composite_id, affiliation_profiles).label
