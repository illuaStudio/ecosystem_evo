"""マップエディタ → Web エディタ共有状態（ファイル）。"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Dict, Optional

_TOOLS = Path(__file__).resolve().parent.parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

from editor_server.shared_state import clear_map_selection, set_map_selection  # noqa: E402


def publish_map_selection(
    *,
    uid: Optional[str],
    layer: Optional[str] = None,
    type_id: Optional[str] = None,
    x: Optional[float] = None,
    y: Optional[float] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        if uid is None:
            clear_map_selection()
        else:
            set_map_selection(
                uid=uid,
                layer=layer,
                type_id=type_id,
                x=x,
                y=y,
                extra=extra,
            )
    except OSError:
        pass
