"""ゲーム進行に固有の状態（シミュレーション層とは分離）。"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GameState:
    """プレイヤー勢力の解釈・初回フラグ・進行指標（プレースホルダ）。"""

    player_colony_id: str = "red_ant"
    danger_level: float = 0.0
    stability_level: float = 1.0
    civilization_level: int = 0
    flags: dict[str, bool] = field(default_factory=dict)

    def set_flag(self, name: str, value: bool = True) -> bool:
        """フラグを更新し、False→True への変化なら True（初回トリガー用）。"""
        was = self.flags.get(name, False)
        self.flags[name] = value
        return value and not was

    def has_flag(self, name: str) -> bool:
        return bool(self.flags.get(name, False))

    def reset_flags(self) -> None:
        self.flags.clear()
