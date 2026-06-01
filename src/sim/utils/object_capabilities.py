"""object_types の capabilities スキーマ正規化（Phase 0）。

レガシー flat フィールドと capabilities ブロックの両方を読み、
統一された能力 dict にマージする。実行時システムはこの出力だけを参照する。
"""
from __future__ import annotations

import copy
from typing import Any, Dict, Mapping, Optional, Tuple

from src.sim.systems.zone_system import ZoneEffects, _normalize_tags

_META_KEYS = frozenset({"id", "category", "label", "capabilities"})
_LEGACY_ZONE_KEYS = frozenset(
    {
        "hp_regen_per_dt",
        "hp_drain_per_dt",
        "field_tags",
        "tags",
        "spawn_rate_multiplier",
    }
)
_LEGACY_COLLISION_KEYS = frozenset({"shape", "radius", "width", "height"})
_LEGACY_STORAGE_KEYS = frozenset({"max_food", "initial_stored_food"})
_LEGACY_ACCESS_KEYS = frozenset({"shelter", "deposit_access", "deposit", "role"})
_LEGACY_COMBAT_KEYS = frozenset({"hp", "max_hp"})
_LEGACY_RENDER_KEYS = frozenset({"render", "color"})


def type_definition(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """メタキーを除いた型定義ペイロード（capabilities 正規化済み）。"""
    return normalize_capabilities(dict(raw))


def normalize_capabilities(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """raw 型定義 → { capabilities: {...}, ...残りの非メタ }。"""
    result = {
        key: copy.deepcopy(value)
        for key, value in raw.items()
        if key not in _META_KEYS
    }
    caps: Dict[str, Any] = copy.deepcopy(raw.get("capabilities") or {})

    category = str(raw.get("category", ""))
    _merge_legacy_collision(caps, raw, category)
    _merge_legacy_zone(caps, raw, category)
    _merge_legacy_storage(caps, raw, category)
    _merge_legacy_access(caps, raw, category)
    _merge_legacy_combat(caps, raw, category)
    _merge_legacy_render(caps, raw)

    if caps:
        result["capabilities"] = caps
    _flatten_for_legacy(result)
    return result


def _flatten_for_legacy(result: Dict[str, Any]) -> None:
    """レガシー読み込み経路が top-level キーを参照できるよう鏡写しする。"""
    caps = result.get("capabilities") or {}

    collision = caps.get("collision") or {}
    for key in ("shape", "radius", "width", "height"):
        if key in collision and key not in result:
            result[key] = copy.deepcopy(collision[key])

    zone = caps.get("zone") or {}
    for key in (
        "shape",
        "radius",
        "width",
        "height",
        "hp_regen_per_dt",
        "hp_drain_per_dt",
        "field_tags",
        "tags",
        "spawn_rate_multiplier",
    ):
        if key in zone and key not in result:
            result[key] = copy.deepcopy(zone[key])

    storage = caps.get("storage") or {}
    for key in ("max_food", "initial_stored_food"):
        if key in storage and key not in result:
            result[key] = copy.deepcopy(storage[key])

    access = caps.get("access") or {}
    for key in ("role", "shelter", "deposit", "deposit_access"):
        if key in access and key not in result:
            result[key] = copy.deepcopy(access[key])

    combat = caps.get("combat") or {}
    for key in ("hp", "max_hp"):
        if key in combat and key not in result:
            result[key] = copy.deepcopy(combat[key])

    render = caps.get("render") or {}
    if render and "render" not in result:
        result["render"] = copy.deepcopy(render)
    return result


def capabilities_of(raw: Mapping[str, Any]) -> Dict[str, Any]:
    """正規化済み capabilities dict を返す。"""
    return normalize_capabilities(raw).get("capabilities") or {}


def has_capability(raw: Mapping[str, Any], name: str) -> bool:
    return name in capabilities_of(raw)


def capability_block(raw: Mapping[str, Any], name: str) -> Dict[str, Any]:
    block = capabilities_of(raw).get(name)
    return dict(block) if isinstance(block, dict) else {}


def merge_type_with_instance(
    type_raw: Mapping[str, Any],
    instance: Mapping[str, Any],
    *,
    reserved_keys: frozenset[str] | None = None,
) -> Dict[str, Any]:
    """型定義 + instances エントリ（インライン上書き）をマージ。"""
    reserved = reserved_keys or frozenset()
    merged = normalize_capabilities(type_raw)
    caps = dict(merged.get("capabilities") or {})

    instance_caps = instance.get("capabilities")
    if isinstance(instance_caps, dict):
        caps = _deep_merge_dict(caps, instance_caps)

    for key, value in instance.items():
        if key in reserved or key in _META_KEYS or key == "capabilities":
            continue
        placed = _place_instance_override(caps, key, value)
        if not placed:
            merged[key] = copy.deepcopy(value)

    if caps:
        merged["capabilities"] = caps
    _flatten_for_legacy(merged)
    return merged


def resolve_geometry(
    data: Mapping[str, Any],
    *,
    capability: str,
    global_defaults: Optional[Mapping[str, Any]] = None,
) -> Tuple[str, float, float, float]:
    """collision / zone 能力から shape, radius, half_w, half_h を解決。"""
    block = capability_block(data, capability)
    if not block:
        block = dict(data)

    defaults = dict(global_defaults or {})
    shape = str(block.get("shape", data.get("shape", defaults.get("shape", "circle")))).lower()
    if shape == "rect":
        width = float(block.get("width", data.get("width", defaults.get("width", 160.0))))
        height = float(block.get("height", data.get("height", defaults.get("height", 80.0))))
        return (
            "rect",
            0.0,
            max(1.0, width * 0.5),
            max(1.0, height * 0.5),
        )
    radius = float(
        block.get(
            "radius",
            data.get("radius", defaults.get("radius", 80.0)),
        )
    )
    return ("circle", max(0.0, radius), 0.0, 0.0)


def resolve_render_color(
    data: Mapping[str, Any],
    default: Tuple[int, int, int],
) -> Tuple[int, int, int]:
    render = capability_block(data, "render")
    if not render:
        render_raw = data.get("render")
        render = render_raw if isinstance(render_raw, dict) else {}
    raw = render.get("color", data.get("color"))
    return _parse_color(raw, default)


def zone_effects_from_data(data: Mapping[str, Any]) -> ZoneEffects:
    """zone 能力またはレガシー flat から ZoneEffects を構築。"""
    block = capability_block(data, "zone")
    inline = data.get("effects")
    if isinstance(inline, dict):
        base = dict(inline)
    elif block:
        base = dict(block)
    else:
        base = {
            key: data[key]
            for key in _LEGACY_ZONE_KEYS
            if key in data
        }

    tags = base.get("field_tags", base.get("tags"))
    spawn_raw = base.get("spawn_rate_multiplier")
    spawn: Optional[float] = None
    if spawn_raw is not None:
        spawn = float(spawn_raw)

    return ZoneEffects(
        hp_regen_per_dt=max(0.0, float(base.get("hp_regen_per_dt", 0.0))),
        hp_drain_per_dt=max(0.0, float(base.get("hp_drain_per_dt", 0.0))),
        field_tags=_normalize_tags(tags),
        spawn_rate_multiplier=spawn,
    )


def point_in_shape(
    x: float,
    y: float,
    *,
    shape: str,
    cx: float,
    cy: float,
    radius: float = 0.0,
    half_w: float = 0.0,
    half_h: float = 0.0,
) -> bool:
    px, py = float(x), float(y)
    if str(shape).lower() == "rect":
        if half_w <= 0 or half_h <= 0:
            return False
        return abs(px - cx) <= half_w and abs(py - cy) <= half_h
    if radius <= 0:
        return False
    dx = px - cx
    dy = py - cy
    return dx * dx + dy * dy <= radius * radius


def _merge_legacy_collision(caps: Dict[str, Any], raw: Mapping[str, Any], category: str) -> None:
    if "collision" in caps:
        return
    if category != "obstacle" and not any(key in raw for key in _LEGACY_COLLISION_KEYS):
        return
    if category != "obstacle" and "shape" not in raw:
        return
    block: Dict[str, Any] = {}
    for key in _LEGACY_COLLISION_KEYS:
        if key in raw:
            block[key] = raw[key]
    if block:
        caps["collision"] = block


def _merge_legacy_zone(caps: Dict[str, Any], raw: Mapping[str, Any], category: str) -> None:
    if "zone" in caps:
        return
    has_zone_data = category == "zone" or any(key in raw for key in _LEGACY_ZONE_KEYS)
    if not has_zone_data:
        return
    block: Dict[str, Any] = {}
    for key in ("shape", "radius", "width", "height"):
        if key in raw:
            block[key] = raw[key]
    for key in _LEGACY_ZONE_KEYS:
        if key in raw:
            block[key] = raw[key]
    if block:
        caps["zone"] = block


def _merge_legacy_storage(caps: Dict[str, Any], raw: Mapping[str, Any], category: str) -> None:
    if "storage" in caps:
        return
    if not any(key in raw for key in _LEGACY_STORAGE_KEYS):
        if category != "affiliation" or raw.get("role") != "root":
            return
    block = {key: raw[key] for key in _LEGACY_STORAGE_KEYS if key in raw}
    if block or (category == "affiliation" and str(raw.get("role", "")) == "root"):
        caps.setdefault("storage", block)


def _merge_legacy_access(caps: Dict[str, Any], raw: Mapping[str, Any], category: str) -> None:
    if "access" in caps:
        return
    if not any(key in raw for key in _LEGACY_ACCESS_KEYS):
        if not (category == "affiliation" and str(raw.get("role", "")) == "access"):
            return
    block: Dict[str, Any] = {}
    for key in _LEGACY_ACCESS_KEYS:
        if key in raw:
            block[key] = raw[key]
    if "deposit" in block and "deposit_access" not in block:
        block["deposit_access"] = block.pop("deposit")
    if block or (category == "affiliation" and str(raw.get("role", "")) == "access"):
        caps.setdefault("access", block)


def _merge_legacy_combat(caps: Dict[str, Any], raw: Mapping[str, Any], category: str) -> None:
    if "combat" in caps:
        return
    if not any(key in raw for key in _LEGACY_COMBAT_KEYS):
        return
    block = {key: raw[key] for key in _LEGACY_COMBAT_KEYS if key in raw}
    if block:
        caps["combat"] = block


def _merge_legacy_render(caps: Dict[str, Any], raw: Mapping[str, Any]) -> None:
    if "render" in caps:
        return
    if "render" in raw:
        caps["render"] = copy.deepcopy(raw["render"])
    elif "color" in raw:
        caps["render"] = {"color": copy.deepcopy(raw["color"])}


def _place_instance_override(caps: Dict[str, Any], key: str, value: Any) -> bool:
    if key in ("shape", "radius", "width", "height"):
        placed = False
        if "zone" in caps:
            caps.setdefault("zone", {})[key] = copy.deepcopy(value)
            placed = True
        if "collision" in caps:
            caps.setdefault("collision", {})[key] = copy.deepcopy(value)
            placed = True
        if not placed:
            caps.setdefault("zone", {})[key] = copy.deepcopy(value)
        return True
    if key in _LEGACY_COLLISION_KEYS:
        caps.setdefault("collision", {})[key] = copy.deepcopy(value)
        return True
    if key in _LEGACY_STORAGE_KEYS:
        caps.setdefault("storage", {})[key] = copy.deepcopy(value)
        return True
    if key in _LEGACY_ACCESS_KEYS or key == "deposit":
        block = caps.setdefault("access", {})
        if key == "deposit":
            block["deposit_access"] = copy.deepcopy(value)
        else:
            block[key] = copy.deepcopy(value)
        return True
    if key in _LEGACY_ZONE_KEYS:
        caps.setdefault("zone", {})[key] = copy.deepcopy(value)
        return True
    if key in _LEGACY_COMBAT_KEYS:
        caps.setdefault("combat", {})[key] = copy.deepcopy(value)
        return True
    if key == "render":
        caps["render"] = copy.deepcopy(value)
        return True
    return False


def _deep_merge_dict(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    result = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge_dict(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def _parse_color(raw: Any, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        return (
            max(0, min(255, int(raw[0]))),
            max(0, min(255, int(raw[1]))),
            max(0, min(255, int(raw[2]))),
        )
    if isinstance(raw, str) and raw.startswith("#") and len(raw) >= 7:
        try:
            return (
                int(raw[1:3], 16),
                int(raw[3:5], 16),
                int(raw[5:7], 16),
            )
        except ValueError:
            pass
    return default
