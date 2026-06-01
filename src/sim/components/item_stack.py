"""スロット型アイテム容器（生物インベントリ・オブジェクト storage 共通）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.sim.components.inventory import BiomassItem, InventoryItem, InventorySlot


def _slot_defs_from_config(
    *,
    max_food: float | None = None,
    slot_count: int | None = None,
    slot_specs: Iterable[dict] | None = None,
) -> list[InventorySlot]:
    specs = list(slot_specs or [])
    if specs:
        slots: list[InventorySlot] = []
        for spec in specs:
            kinds = spec.get("allowed_kinds", ["biomass"])
            slots.append(
                InventorySlot(
                    max_mass=max(0.0, float(spec.get("max_mass", 50.0))),
                    allowed_kinds=frozenset(str(k) for k in kinds),
                )
            )
        return slots

    count = int(slot_count if slot_count is not None else 1)
    cap = max(0.0, float(max_food if max_food is not None else 400.0))
    if count <= 1:
        return [InventorySlot(max_mass=cap, allowed_kinds=frozenset({"biomass"}))]
    per = cap / count if count > 0 else cap
    return [
        InventorySlot(max_mass=per, allowed_kinds=frozenset({"biomass"}))
        for _ in range(count)
    ]


@dataclass
class ItemStack:
    slots: list[InventorySlot] = field(default_factory=list)
    biomass_weight_per_unit: float = 1.0

    @classmethod
    def from_biomass_capacity(
        cls,
        max_food: float,
        stored_food: float = 0.0,
        *,
        biomass_weight_per_unit: float = 1.0,
    ) -> ItemStack:
        stack = cls(
            slots=_slot_defs_from_config(max_food=max_food),
            biomass_weight_per_unit=float(biomass_weight_per_unit),
        )
        if stored_food > 0:
            stack.set_biomass_amount(stored_food)
        return stack

    @classmethod
    def from_storage_config(cls, config: dict) -> ItemStack:
        cfg = dict(config or {})
        slots = _slot_defs_from_config(
            max_food=cfg.get("max_food"),
            slot_count=cfg.get("slot_count"),
            slot_specs=cfg.get("slots"),
        )
        stack = cls(
            slots=slots,
            biomass_weight_per_unit=float(cfg.get("biomass_weight_per_unit", 1.0)),
        )
        initial = float(cfg.get("initial_stored_food", cfg.get("stored_food", 0.0)))
        if initial > 0:
            stack.set_biomass_amount(initial)
        return stack

    @property
    def slot_count(self) -> int:
        return len(self.slots)

    @property
    def is_empty(self) -> bool:
        return all(s.is_empty() for s in self.slots)

    @property
    def total_mass(self) -> float:
        total = 0.0
        for slot in self.slots:
            if slot.item is not None:
                total += slot.item.weight(
                    biomass_weight_per_unit=self.biomass_weight_per_unit
                )
        return total

    def iter_biomass_slots(self):
        for slot in self.slots:
            if isinstance(slot.item, BiomassItem):
                yield slot

    def biomass_amount(self) -> float:
        return sum(float(s.item.amount) for s in self.iter_biomass_slots() if s.item)

    def biomass_capacity(self) -> float:
        return sum(
            float(s.max_mass)
            for s in self.slots
            if "biomass" in s.allowed_kinds
        )

    def biomass_free_space(self) -> float:
        return max(0.0, self.biomass_capacity() - self.biomass_amount())

    def set_biomass_amount(self, amount: float) -> None:
        amount = max(0.0, float(amount))
        for slot in self.slots:
            if isinstance(slot.item, BiomassItem):
                slot.item = None
        if amount <= 0:
            return
        slot = self._primary_biomass_slot(create=True)
        cap = float(slot.max_mass)
        slot.item = BiomassItem(amount=min(amount, cap) if cap > 0 else amount)

    def set_biomass_capacity(self, cap: float) -> None:
        cap = max(0.0, float(cap))
        if not self.slots:
            self.slots = _slot_defs_from_config(max_food=cap)
            return
        biomass_slots = [s for s in self.slots if "biomass" in s.allowed_kinds]
        if len(biomass_slots) == 1:
            biomass_slots[0].max_mass = cap
            stored = self.biomass_amount()
            if stored > cap:
                self.set_biomass_amount(cap)
            return
        self.slots = _slot_defs_from_config(max_food=cap)
        self.set_biomass_amount(min(self.biomass_amount(), cap))

    def deposit_biomass(self, amount: float) -> float:
        amount = float(amount)
        if amount <= 0:
            return 0.0
        space = self.biomass_free_space()
        added = min(amount, space)
        if added <= 0:
            return 0.0
        slot = self._primary_biomass_slot(create=True)
        if slot.item is None:
            slot.item = BiomassItem(amount=added)
        else:
            slot.item.amount = float(slot.item.amount) + added
        return added

    def withdraw_biomass(self, amount: float) -> float:
        amount = float(amount)
        if amount <= 0 or self.biomass_amount() <= 0:
            return 0.0
        taken = min(amount, self.biomass_amount())
        remaining = self.biomass_amount() - taken
        self.set_biomass_amount(remaining)
        return taken

    def first_empty_slot(self) -> InventorySlot | None:
        for slot in self.slots:
            if slot.is_empty():
                return slot
        return None

    def deposit_item(self, item: InventoryItem) -> bool:
        if item is None:
            return False
        for slot in self.slots:
            if not slot.can_accept(item.kind):
                continue
            slot.item = item
            return True
        return False

    def _primary_biomass_slot(self, *, create: bool = False) -> InventorySlot:
        for slot in self.slots:
            if "biomass" in slot.allowed_kinds:
                return slot
        if create:
            slot = InventorySlot(max_mass=400.0, allowed_kinds=frozenset({"biomass"}))
            self.slots.append(slot)
            return slot
        raise ValueError("no biomass slot")

    @property
    def food_ratio(self) -> float:
        cap = self.biomass_capacity()
        if cap <= 0:
            return 0.0
        return max(0.0, min(1.0, self.biomass_amount() / cap))
