"""layout zones / field_emitters → zone instances。"""
from __future__ import annotations

from typing import Any, Dict, List

_ZONE_GEOMETRY_KEYS = (
    "shape",
    "radius",
    "width",
    "height",
    "half_w",
    "half_h",
)
_ZONE_EFFECT_KEYS = (
    "hp_regen_per_dt",
    "hp_drain_per_dt",
    "field_tags",
    "tags",
    "spawn_rate_multiplier",
    "effects",
)


def _resolve_zone_entry(
    entry: Dict[str, Any],
    *,
    global_defaults: Dict[str, Any],
    type_defaults: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    zone_type = str(entry.get("type", global_defaults.get("type", "custom")))
    merged = dict(global_defaults)
    merged.update(type_defaults.get(zone_type, {}))
    merged.update(entry)
    merged["type"] = zone_type
    return merged


def _entry_to_zone_instance(
    entry: Dict[str, Any],
    *,
    global_defaults: Dict[str, Any],
    type_defaults: Dict[str, Dict[str, Any]],
) -> Dict[str, Any] | None:
    affiliation_id = entry.get("affiliation_id")
    if affiliation_id and ("x" not in entry or "y" not in entry):
        return None
    if "x" not in entry or "y" not in entry:
        return None

    data = _resolve_zone_entry(
        entry,
        global_defaults=global_defaults,
        type_defaults=type_defaults,
    )
    zone_type = str(data["type"])
    inst: Dict[str, Any] = {
        "layer": "zone",
        "type": zone_type,
        "x": float(data["x"]),
        "y": float(data["y"]),
        "origin": "legacy_import",
    }
    if affiliation_id:
        inst["id"] = f"{affiliation_id}_clearing"
        inst["affiliation_id"] = str(affiliation_id)
    for key in _ZONE_GEOMETRY_KEYS + _ZONE_EFFECT_KEYS:
        if key in data:
            inst[key] = data[key]
    if "label" in data:
        inst["label"] = data["label"]
    return inst


def instances_from_zones_block(zones_cfg: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not zones_cfg:
        return []
    global_defaults = dict(zones_cfg.get("defaults") or {})
    type_defaults = {
        str(key): dict(value)
        for key, value in (zones_cfg.get("types") or {}).items()
        if isinstance(value, dict)
    }
    out: List[Dict[str, Any]] = []
    for entry in zones_cfg.get("sources") or []:
        if not isinstance(entry, dict):
            continue
        inst = _entry_to_zone_instance(
            entry,
            global_defaults=global_defaults,
            type_defaults=type_defaults,
        )
        if inst is not None:
            out.append(inst)
    return out


def instances_from_field_emitters_block(
    emitters_cfg: Dict[str, Any] | None,
) -> List[Dict[str, Any]]:
    if not emitters_cfg:
        return []
    global_defaults = dict(emitters_cfg.get("defaults") or {})
    type_defaults = {
        str(key): dict(value)
        for key, value in (emitters_cfg.get("types") or {}).items()
        if isinstance(value, dict)
    }
    out: List[Dict[str, Any]] = []
    for entry in (
        emitters_cfg.get("sources") or emitters_cfg.get("emitters") or []
    ):
        if not isinstance(entry, dict):
            continue
        if "x" not in entry or "y" not in entry:
            continue
        zone_type = str(
            entry.get("type", global_defaults.get("type", "poison_fog"))
        )
        merged = dict(global_defaults)
        merged.update(type_defaults.get(zone_type, {}))
        merged.update(entry)
        inst: Dict[str, Any] = {
            "layer": "zone",
            "type": zone_type,
            "x": float(merged["x"]),
            "y": float(merged["y"]),
            "origin": "legacy_field_emitter",
        }
        for key in _ZONE_GEOMETRY_KEYS:
            if key in merged:
                inst[key] = merged[key]
        if "radius" not in inst and zone_type == "poison_fog":
            inst.setdefault("radius", 95.0)
        if "hp_drain_per_dt" in merged:
            inst["hp_drain_per_dt"] = merged["hp_drain_per_dt"]
        if "hp_regen_per_dt" in merged:
            inst["hp_regen_per_dt"] = merged["hp_regen_per_dt"]
        tags = merged.get("tags", merged.get("field_tags"))
        if tags is not None:
            inst["field_tags"] = tags
        if "label" in merged:
            inst["label"] = merged["label"]
        out.append(inst)
    return out
