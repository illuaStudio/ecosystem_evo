"""グローバル object_types と world 内インライン types のマージ。"""
from __future__ import annotations

import copy
from typing import Any, Dict, List, Optional

_META_KEYS = frozenset({"id", "category", "label"})


def _get_registry() -> Dict[str, Dict[str, Any]]:
    from src.config import config

    return config.object_types


def type_definition(raw: Dict[str, Any]) -> Dict[str, Any]:
    """メタキーを除いた型定義ペイロード。"""
    return {key: copy.deepcopy(value) for key, value in raw.items() if key not in _META_KEYS}


def merged_types_for_category(
    category: str,
    inline_types: Optional[Dict[str, Any]] = None,
) -> Dict[str, Dict[str, Any]]:
    """グローバル catalog + world インライン types（インラインが優先）。"""
    merged: Dict[str, Dict[str, Any]] = {}
    for type_id, raw in _get_registry().items():
        if not isinstance(raw, dict):
            continue
        if str(raw.get("category", "")) != category:
            continue
        merged[str(type_id)] = type_definition(raw)

    for key, value in (inline_types or {}).items():
        if isinstance(value, dict):
            merged[str(key)] = dict(value)
    return merged


def merge_obstacle_config(cfg: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not cfg:
        return cfg
    result = dict(cfg)
    inline = dict((cfg.get("types") or {}))
    result["types"] = merged_types_for_category("obstacle", inline)
    return result


def merge_zone_config(cfg: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not cfg:
        return cfg
    result = dict(cfg)
    inline = dict((cfg.get("types") or {}))
    result["types"] = merged_types_for_category("zone", inline)
    return result


def list_type_ids(category: str, *, inline_types: Optional[Dict[str, Any]] = None) -> List[str]:
    return list(merged_types_for_category(category, inline_types).keys())


def resolve_type_def(
    category: str,
    type_ref: str,
    *,
    inline_types: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return merged_types_for_category(category, inline_types).get(type_ref, {})


def get_object_type(type_id: str) -> Dict[str, Any]:
    raw = _get_registry().get(type_id)
    if not isinstance(raw, dict):
        return {}
    return dict(raw)
