"""layout spawn_emitters → spawn instances。"""
from __future__ import annotations

from typing import Any, Dict, List

AMBIENT_SPAWN_ID = "_ambient_spawn"

_SPAWN_KEYS = (
    "mode",
    "species_pool",
    "target_population",
    "spawn_rate_per_dt",
    "radius",
    "max_spawns_per_tick",
    "position_attempts",
    "nest_exclusion_radius",
    "use_biome_weight",
    "margin",
    "label",
)


def _resolve_spawn_entry(
    entry: Dict[str, Any],
    *,
    global_defaults: Dict[str, Any],
    type_defaults: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    spawn_type = str(entry.get("type", global_defaults.get("type", "micro_fauna")))
    merged = dict(global_defaults)
    merged.update(type_defaults.get(spawn_type, {}))
    merged.update(entry)
    merged["type"] = spawn_type
    return merged


def _spawn_instance_from_merged(
    merged: Dict[str, Any],
    *,
    instance_id: str | None = None,
    origin: str = "legacy_import",
) -> Dict[str, Any]:
    mode = str(merged.get("mode", "point")).lower()
    inst: Dict[str, Any] = {
        "layer": "spawn",
        "type": str(merged.get("type", "spawn")),
        "x": float(merged.get("x", 0.0)),
        "y": float(merged.get("y", 0.0)),
        "origin": origin,
    }
    if instance_id:
        inst["id"] = instance_id
    inst["mode"] = mode
    for key in _SPAWN_KEYS:
        if key in merged:
            inst[key] = merged[key]
    return inst


def instances_from_spawn_emitters_block(
    emitters_cfg: Dict[str, Any] | None,
    *,
    include_point_sources: bool,
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

    ambient = emitters_cfg.get("ambient")
    if isinstance(ambient, dict):
        merged = _resolve_spawn_entry(
            {**ambient, "mode": "ambient"},
            global_defaults=global_defaults,
            type_defaults=type_defaults,
        )
        out.append(
            _spawn_instance_from_merged(
                merged,
                instance_id=AMBIENT_SPAWN_ID,
                origin="legacy_ambient",
            )
        )

    if not include_point_sources:
        return out

    for entry in emitters_cfg.get("sources") or emitters_cfg.get("emitters") or []:
        if not isinstance(entry, dict):
            continue
        if "x" not in entry or "y" not in entry:
            continue
        merged = _resolve_spawn_entry(
            entry,
            global_defaults=global_defaults,
            type_defaults=type_defaults,
        )
        merged["mode"] = "point"
        out.append(_spawn_instance_from_merged(merged))
    return out
