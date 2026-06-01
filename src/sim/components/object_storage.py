"""ワールドオブジェクト（親拠点）の ItemStack 備蓄。"""
from __future__ import annotations

from src.sim.components.item_stack import ItemStack


class ObjectStorage:
    """スロット型 storage。stored_food / max_food はバイオマス量の互換 API。"""

    stack: ItemStack

    def __init__(
        self,
        stored_food: float = 0.0,
        max_food: float = 400.0,
        *,
        stack: ItemStack | None = None,
    ) -> None:
        if stack is not None:
            self.stack = stack
        else:
            self.stack = ItemStack.from_biomass_capacity(max_food, stored_food)

    @classmethod
    def from_config(cls, config: dict) -> ObjectStorage:
        return cls(stack=ItemStack.from_storage_config(config))

    @property
    def stored_food(self) -> float:
        return self.stack.biomass_amount()

    @stored_food.setter
    def stored_food(self, amount: float) -> None:
        self.stack.set_biomass_amount(amount)

    @property
    def max_food(self) -> float:
        return self.stack.biomass_capacity()

    @max_food.setter
    def max_food(self, cap: float) -> None:
        self.stack.set_biomass_capacity(cap)

    def deposit(self, amount: float) -> float:
        return self.stack.deposit_biomass(amount)

    def withdraw(self, amount: float) -> float:
        return self.stack.withdraw_biomass(amount)

    @property
    def food_ratio(self) -> float:
        return self.stack.food_ratio
