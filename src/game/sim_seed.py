"""試験・リプレイ用: グローバル乱数の固定。"""
from __future__ import annotations

import random


def apply_simulation_seed(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(int(seed))
