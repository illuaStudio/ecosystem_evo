# inventory.py
"""全生物共通のインベントリ（スロットとアイテム）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class InventoryItem:
    """アイテム基底（BiomassItem / StackItem 等）。"""

    kind: str

    def weight(self, *, biomass_weight_per_unit: float) -> float:
        raise NotImplementedError


@dataclass
class BiomassItem(InventoryItem):
    kind: str = "biomass"
    amount: float = 0.0
    source_carcass: Any = None
    source_loot: Any = None

    def weight(self, *, biomass_weight_per_unit: float) -> float:
        return max(0.0, float(self.amount)) * max(0.0, float(biomass_weight_per_unit))


@dataclass
class StackItem(InventoryItem):
    """汎用スタックアイテム（剣・道具など将来用）。"""

    kind: str = "item"
    item_type: str = ""
    quantity: int = 1
    mass_per_unit: float = 1.0

    def weight(self, *, biomass_weight_per_unit: float) -> float:
        return max(0.0, float(self.quantity)) * max(0.0, float(self.mass_per_unit))


@dataclass
class InventorySlot:
    max_mass: float
    allowed_kinds: frozenset[str] = frozenset({"biomass"})
    item: InventoryItem | None = None

    def is_empty(self) -> bool:
        return self.item is None

    def can_accept(self, kind: str) -> bool:
        return self.is_empty() and kind in self.allowed_kinds


@dataclass
class InventoryComponent:
    slots: list[InventorySlot] = field(default_factory=list)
    biomass_weight_per_unit: float = 1.0
    carry_speed_reference_weight: float = 80.0

    @property
    def slot_count(self) -> int:
        return len(self.slots)

    @property
    def is_loaded(self) -> bool:
        return any(not s.is_empty() for s in self.slots)

    @property
    def total_weight(self) -> float:
        total = 0.0
        for slot in self.slots:
            if slot.item is not None:
                total += slot.item.weight(
                    biomass_weight_per_unit=self.biomass_weight_per_unit
                )
        return total

    @property
    def empty_slot_count(self) -> int:
        return sum(1 for s in self.slots if s.is_empty())

    def first_empty_index(self) -> int | None:
        for i, slot in enumerate(self.slots):
            if slot.is_empty():
                return i
        return None

    def carry_speed_multiplier(self) -> float:
        ref = max(1e-6, float(self.carry_speed_reference_weight))
        return 1.0 / (1.0 + self.total_weight / ref)

    def slot_max_mass(self, index: int) -> float:
        if index < 0 or index >= len(self.slots):
            return 0.0
        return float(self.slots[index].max_mass)

    def iter_biomass_slots(self):
        for slot in self.slots:
            if isinstance(slot.item, BiomassItem):
                yield slot

    def first_biomass_slot(self) -> InventorySlot | None:
        for slot in self.slots:
            if isinstance(slot.item, BiomassItem):
                return slot
        return None

    def clear_slot(self, slot: InventorySlot) -> None:
        slot.item = None

    def clear_all(self) -> None:
        for slot in self.slots:
            slot.item = None
