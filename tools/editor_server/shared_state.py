"""マップエディタと Web UI の軽量共有状態（ファイル）。"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

from editor_server.paths import SHARED_STATE_PATH


def _read_raw() -> Dict[str, Any]:
    if not SHARED_STATE_PATH.exists():
        return {}
    try:
        with open(SHARED_STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def _write_raw(data: Dict[str, Any]) -> None:
    SHARED_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = SHARED_STATE_PATH.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    tmp.replace(SHARED_STATE_PATH)


def get_map_selection() -> Dict[str, Any]:
    raw = _read_raw()
    sel = raw.get("map_selection")
    return sel if isinstance(sel, dict) else {}


def set_map_selection(
    *,
    uid: Optional[str],
    layer: Optional[str] = None,
    type_id: Optional[str] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "uid": uid,
        "layer": layer,
        "type_id": type_id,
        "x": x,
        "y": y,
        "updated_at": time.time(),
    }
    if extra:
        payload["extra"] = extra
    raw = _read_raw()
    raw["map_selection"] = payload
    _write_raw(raw)
    return payload


def clear_map_selection() -> None:
    raw = _read_raw()
    raw["map_selection"] = {"uid": None, "updated_at": time.time()}
    _write_raw(raw)
