"""ワールド layout の instances 正規化（sim ランタイム用）。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from src.sim.layout.obstacle_import import instances_from_obstacles_block
from src.sim.layout.spawn_import import instances_from_spawn_emitters_block
from src.sim.layout.zone_import import (
    instances_from_field_emitters_block,
    instances_from_zones_block,
)
from src.sim.utils.world_instances import COLONY_PROFILE_LAYERS, uses_instances_format


def sync_affiliation_profiles_from_instances(layout: Dict[str, Any]) -> None:
    """instances の affiliation_site から profiles.nest_x/y を補完（エディタ用ミラーなし）。"""
    affiliation = layout.setdefault("affiliation", {})
    profiles = affiliation.setdefault("profiles", {})
    for raw in layout.get("instances") or []:
        if not isinstance(raw, dict):
            continue
        layer = str(raw.get("layer", ""))
        if layer not in COLONY_PROFILE_LAYERS:
            continue
        affiliation_id = str(raw.get("id", raw.get("type", "")))
        if not affiliation_id:
            continue
        profile = dict(profiles.get(affiliation_id) or {})
        profile["nest_x"] = float(raw.get("x", profile.get("nest_x", 0.0)))
        profile["nest_y"] = float(raw.get("y", profile.get("nest_y", 0.0)))
        profiles[affiliation_id] = profile


def expand_layout_instances(layout: Dict[str, Any]) -> List[Dict[str, Any]]:
    """instances + レガシー section を 1 リストにまとめる（WOS 読み込み用）。"""
    instances = list(layout.get("instances") or [])
    uses_instances = "instances" in layout

    if not uses_instances:
        instances.extend(instances_from_zones_block(layout.get("zones")))
        instances.extend(instances_from_obstacles_block(layout.get("obstacles")))
        instances.extend(
            instances_from_spawn_emitters_block(
                layout.get("spawn_emitters"),
                include_point_sources=True,
            )
        )
    else:
        instances.extend(
            instances_from_spawn_emitters_block(
                layout.get("spawn_emitters"),
                include_point_sources=False,
            )
        )

    instances.extend(instances_from_field_emitters_block(layout.get("field_emitters")))

    ambient_legacy = layout.get("ambient_spawns")
    if isinstance(ambient_legacy, dict):
        instances.extend(
            instances_from_spawn_emitters_block(
                {"ambient": ambient_legacy},
                include_point_sources=False,
            )
        )

    return instances


def canonicalize_runtime_layout(world_data: Dict[str, Any]) -> Dict[str, Any]:
    """sim ランタイム用: instances 正規化のみ（legacy sections へのミラーはしない）。"""
    layout = copy.deepcopy(world_data)
    if uses_instances_format(layout):
        sync_affiliation_profiles_from_instances(layout)
    layout["instances"] = expand_layout_instances(layout)
    return layout
