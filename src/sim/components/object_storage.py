"""ワールドオブジェクトの ItemStack 容器。"""
from __future__ import annotations

from src.sim.components.item_stack import ItemStack


class ObjectStorage:
    """スロット型 storage。"""

    stack: ItemStack

    def __init__(
        self,
        stored_mass: float = 0.0,
        max_mass: float = 400.0,
        *,
        default_kind: str = "biomass",
        stack: ItemStack | None = None,
    ) -> None:
        if stack is not None:
            self.stack = stack
        else:
            self.stack = ItemStack.from_kind_capacity(
                default_kind, max_mass, stored_mass
            )

    @classmethod
    def from_config(cls, config: dict) -> ObjectStorage:
        return cls(stack=ItemStack.from_storage_config(config))

    @property
    def stored_mass(self) -> float:
        return self.stack.total_mass

    @stored_mass.setter
    def stored_mass(self, amount: float) -> None:
        self.stack.set_amount_for_kind("biomass", amount)

    @property
    def capacity(self) -> float:
        return self.stack.capacity_mass

    @capacity.setter
    def capacity(self, cap: float) -> None:
        self.stack.set_capacity_for_kind("biomass", cap)

    @property
    def fill_ratio(self) -> float:
        return self.stack.fill_ratio

    def deposit(self, amount: float, *, kind: str = "biomass") -> float:
        return self.stack.deposit_kind(kind, amount)

    def withdraw(self, amount: float, *, kind: str = "biomass") -> float:
        return self.stack.withdraw_kind(kind, amount)
