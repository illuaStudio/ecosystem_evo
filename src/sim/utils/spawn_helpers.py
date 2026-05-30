"""個体生成直後のシミュレーション層初期状態。"""
from __future__ import annotations


def apply_creature_spawn_state(creature) -> None:
    """add_creature 直後にシミュ層が担う初期化（ゲーム層の処理は含まない）。"""
    _ = creature
