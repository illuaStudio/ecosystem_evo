"""繁殖クールダウンと将来の繁殖ロジック置き場。"""
from typing import Any


class ReproductionComponent:
    """分裂・産卵・交配など繁殖系アクション共通のクールダウン（ティック）。"""

    def __init__(self, owner: Any) -> None:
        self.owner = owner
        self.cooldown = 0

    def update(self) -> None:
        if self.cooldown > 0:
            self.cooldown -= 1

    def set_cooldown(self, ticks: int) -> None:
        self.cooldown = max(0, int(ticks))
