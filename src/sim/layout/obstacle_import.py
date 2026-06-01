"""layout obstacles.sources → obstacle instances。"""
from __future__ import annotations

from typing import Any, Dict, List


def instances_from_obstacles_block(obstacles_cfg: Dict[str, Any] | None) -> List[Dict[str, Any]]:
    if not obstacles_cfg:
        return []
    global_defaults = dict(obstacles_cfg.get("defaults") or {})
    type_defaults = {
        str(key): dict(value)
        for key, value in (obstacles_cfg.get("types") or {}).items()
        if isinstance(value, dict)
    }
    out: List[Dict[str, Any]] = []
    for entry in obstacles_cfg.get("sources") or []:
        if not isinstance(entry, dict):
            continue
        if "x" not in entry or "y" not in entry:
            continue
        obs_type = str(entry.get("type", global_defaults.get("type", "rock")))
        merged = dict(global_defaults)
        merged.update(type_defaults.get(obs_type, {}))
        merged.update(entry)
        inst: Dict[str, Any] = {
            "layer": "obstacle",
            "type": obs_type,
            "x": float(merged["x"]),
            "y": float(merged["y"]),
            "origin": "legacy_import",
        }
        if entry.get("id") is not None:
            inst["id"] = entry["id"]
        for key in ("shape", "radius", "width", "height", "render", "color"):
            if key in merged:
                inst[key] = merged[key]
        out.append(inst)
    return out
