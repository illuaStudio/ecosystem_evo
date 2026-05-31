"""ワールドオブジェクト（親拠点）の備蓄。将来 ItemStack に移行。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ObjectStorage:
    stored_food: float = 0.0
    max_food: float = 400.0

    def deposit(self, amount: float) -> float:
        if amount <= 0 or self.max_food <= 0:
            return 0.0
        space = max(0.0, self.max_food - self.stored_food)
        added = min(float(amount), space)
        self.stored_food += added
        return added

    def withdraw(self, amount: float) -> float:
        if amount <= 0 or self.stored_food <= 0:
            return 0.0
        taken = min(float(amount), self.stored_food)
        self.stored_food -= taken
        return taken

    @property
    def food_ratio(self) -> float:
        if self.max_food <= 0:
            return 0.0
        return max(0.0, min(1.0, self.stored_food / self.max_food))
