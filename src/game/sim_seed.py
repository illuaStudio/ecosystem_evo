"""試験・リプレイ用: グローバル乱数の固定。"""
from __future__ import annotations

import random


def apply_simulation_seed(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(int(seed))


def apply_config_simulation_seed() -> bool:
    """config/sim/engine.json の seed を適用。World 生成の前に呼ぶ。"""
    from src.config import config

    raw = config.sim.get("seed")
    if raw is None:
        return False
    apply_simulation_seed(int(raw))
    return True
