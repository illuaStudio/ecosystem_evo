"""地面に落ちた量アイテム（バイオマス等）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple

from src.sim.components.item_stack import ItemStack


@dataclass
class GroundLoot:
    """量アイテムのフィールド上インスタンス。生物死骸の代替。"""

    id: str
    x: float
    y: float
    stack: ItemStack
    initial_biomass: float = 0.0
    decompose_rate: float = 0.00003
    source_species: str = ""
    color: Tuple[int, int, int] = (140, 120, 90)
    pickup_radius: float = 12.0

    def biomass_amount(self) -> float:
        return self.stack.biomass_amount()

    def is_depleted(self) -> bool:
        return self.biomass_amount() <= 0

    def biomass_ratio(self) -> float:
        initial = max(float(self.initial_biomass), 1.0)
        return max(0.0, min(1.0, self.biomass_amount() / initial))
