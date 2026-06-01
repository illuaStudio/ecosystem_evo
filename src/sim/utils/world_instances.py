"""world.json の instances[] と legacy sections（obstacles/zones/spawn/nest）の相互変換。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, MutableMapping, Optional

from src.sim.utils.compound_layers import ACCESS_LAYERS, ROOT_LAYERS

INSTANCE_LAYERS = frozenset(
    {"obstacle", "zone", "spawn", "nest", "affiliation_site", "affiliation_access", "compound_root", "compound_access"}
)
COLONY_PROFILE_LAYERS = frozenset({"affiliation_site", "nest"})
RESERVED_INSTANCE_KEYS = frozenset(
    {"id", "layer", "type", "x", "y", "parent", "role", "editor_group", "affiliation_id"}
)


def uses_instances_format(world_data: Dict[str, Any]) -> bool:
    """instances キーがあれば instances 形式（空配列でも正）。"""
    return "instances" in world_data


def _instance_overrides(instance: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: copy.deepcopy(value)
        for key, value in instance.items()
        if key not in RESERVED_INSTANCE_KEYS
    }


def instance_to_source_entry(instance: Dict[str, Any]) -> Dict[str, Any]:
    """instances 1件 → legacy source エントリ。"""
    entry: Dict[str, Any] = {
        "type": str(instance["type"]),
        "x": float(instance["x"]),
        "y": float(instance["y"]),
    }
    if instance.get("id") is not None:
        entry["id"] = instance["id"]
    entry.update(_instance_overrides(instance))
    return entry


def source_entry_to_instance(layer: str, entry: Dict[str, Any]) -> Dict[str, Any]:
    """legacy source 1件 → instances エントリ。"""
    instance: Dict[str, Any] = {
        "layer": layer,
        "type": str(entry.get("type", entry.get("shape", "custom"))),
        "x": float(entry.get("x", 0.0)),
        "y": float(entry.get("y", 0.0)),
    }
    if entry.get("id") is not None:
        instance["id"] = entry["id"]
    for key, value in entry.items():
        if key not in ("type", "shape", "x", "y", "id"):
            instance[key] = copy.deepcopy(value)
    return instance


def nest_profile_to_instance(affiliation_id: str, profile: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if "nest_x" not in profile or "nest_y" not in profile:
        return None
    return {
        "id": str(affiliation_id),
        "layer": "affiliation_site",
        "type": "affiliation_site",
        "role": "root",
        "x": float(profile["nest_x"]),
        "y": float(profile["nest_y"]),
    }


def collapse_legacy_to_instances(world_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """legacy sections から instances 配列を構築。"""
    instances: List[Dict[str, Any]] = []

    obstacles = world_data.get("obstacles") or {}
    for entry in obstacles.get("sources") or []:
        if isinstance(entry, dict):
            instances.append(source_entry_to_instance("obstacle", entry))

    zones = world_data.get("zones") or {}
    for entry in zones.get("sources") or []:
        if isinstance(entry, dict):
            instances.append(source_entry_to_instance("zone", entry))

    spawns = world_data.get("spawn_emitters") or {}
    for entry in spawns.get("sources") or []:
        if isinstance(entry, dict):
            instances.append(source_entry_to_instance("spawn", entry))

    profiles = (world_data.get("affiliation") or {}).get("profiles") or {}
    for affiliation_id, profile in profiles.items():
        if not isinstance(profile, dict):
            continue
        inst = nest_profile_to_instance(str(affiliation_id), profile)
        if inst is not None:
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


def expand_instances_to_legacy(world_data: MutableMapping[str, Any]) -> None:
    """instances[] を legacy sections へ展開（in-place）。"""
    if "instances" not in world_data:
        return

    obstacle_sources: List[Dict[str, Any]] = []
    zone_sources: List[Dict[str, Any]] = []
    spawn_sources: List[Dict[str, Any]] = []

    for raw in world_data.get("instances") or []:
        if not isinstance(raw, dict):
            continue
        layer = str(raw.get("layer", ""))
        if layer not in INSTANCE_LAYERS:
            continue
        if layer in COLONY_PROFILE_LAYERS:
            affiliation_id = str(raw.get("id", raw.get("type", "")))
            if not affiliation_id:
                continue
            affiliation = world_data.setdefault("affiliation", {})
            profiles = affiliation.setdefault("profiles", {})
            profile = profiles.setdefault(affiliation_id, {})
            if not isinstance(profile, dict):
                profile = {}
                profiles[affiliation_id] = profile
            profile["nest_x"] = float(raw.get("x", profile.get("nest_x", 0.0)))
            profile["nest_y"] = float(raw.get("y", profile.get("nest_y", 0.0)))
            continue
        if layer in ACCESS_LAYERS:
            continue

        entry = instance_to_source_entry(raw)
        if layer == "obstacle":
            obstacle_sources.append(entry)
        elif layer == "zone":
            zone_sources.append(entry)
        elif layer == "spawn":
            spawn_sources.append(entry)

    obstacles = world_data.setdefault("obstacles", {})
    if isinstance(obstacles, dict):
        obstacles["sources"] = obstacle_sources

    zones = world_data.setdefault("zones", {})
    if isinstance(zones, dict):
        zones["sources"] = zone_sources

    spawns = world_data.setdefault("spawn_emitters", {})
    if isinstance(spawns, dict):
        spawns["sources"] = spawn_sources


def normalize_world_layout(world_data: Dict[str, Any]) -> Dict[str, Any]:
    """エディタ/テスト用: instances 形式なら legacy sections へミラーしたコピーを返す。

    sim ランタイムは ``layout.canonicalize_runtime_layout`` を使うこと。
    """
    if not uses_instances_format(world_data):
        return world_data
    expanded = copy.deepcopy(world_data)
    expand_instances_to_legacy(expanded)
    return expanded


def map_object_to_instance(obj: Any) -> Dict[str, Any]:
    """MapObject → instances エントリ。"""
    instance: Dict[str, Any] = {
        "id": str(getattr(obj, "source_id", None) or obj.uid),
        "layer": obj.layer,
        "type": obj.type_ref,
        "x": float(obj.x),
        "y": float(obj.y),
    }
    for key, value in (getattr(obj, "props", None) or {}).items():
        instance[key] = copy.deepcopy(value)
    for key in ("parent", "role"):
        val = (getattr(obj, "props", None) or {}).get(key)
        if val is not None and key not in instance:
            instance[key] = copy.deepcopy(val)
    return instance


def instance_to_map_object_props(instance: Dict[str, Any]) -> Dict[str, Any]:
    return _instance_overrides(instance)
