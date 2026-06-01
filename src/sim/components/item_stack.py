"""スロット型アイテム容器（生物インベントリ・オブジェクト storage 共通）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from src.sim.components.inventory import BiomassItem, InventoryItem, InventorySlot


def _slot_defs_from_config(
    *,
    max_mass: float | None = None,
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
    cap = max(0.0, float(max_mass if max_mass is not None else 400.0))
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
    mass_per_unit: float = 1.0

    @classmethod
    def from_kind_capacity(
        cls,
        kind: str,
        max_mass: float,
        stored_mass: float = 0.0,
        *,
        mass_per_unit: float = 1.0,
    ) -> ItemStack:
        stack = cls(
            slots=_slot_defs_from_config(max_mass=max_mass),
            mass_per_unit=float(mass_per_unit),
        )
        if stored_mass > 0:
            stack.set_amount_for_kind(kind, stored_mass)
        return stack

    @classmethod
    def from_storage_config(cls, config: dict) -> ItemStack:
        cfg = dict(config or {})
        slots = _slot_defs_from_config(
            max_mass=cfg.get("max_mass"),
            slot_count=cfg.get("slot_count"),
            slot_specs=cfg.get("slots"),
        )
        stack = cls(
            slots=slots,
            mass_per_unit=float(cfg.get("mass_per_unit", 1.0)),
        )
        initial = float(cfg.get("initial_mass", cfg.get("stored_mass", 0.0)))
        default_kind = str(cfg.get("default_kind", "biomass"))
        if initial > 0:
            stack.set_amount_for_kind(default_kind, initial)
        return stack

    @property
    def slot_count(self) -> int:
        return len(self.slots)

    @property
    def is_empty(self) -> bool:
        return all(s.is_empty() for s in self.slots)

    @property
    def capacity_mass(self) -> float:
        return sum(float(s.max_mass) for s in self.slots)

    @property
    def total_mass(self) -> float:
        total = 0.0
        for slot in self.slots:
            if slot.item is not None:
                total += slot.item.weight(mass_per_unit=self.mass_per_unit)
        return total

    @property
    def fill_ratio(self) -> float:
        cap = self.capacity_mass
        if cap <= 0:
            return 0.0
        return max(0.0, min(1.0, self.total_mass / cap))

    def iter_slots_for_kind(self, kind: str):
        for slot in self.slots:
            if kind not in slot.allowed_kinds:
                continue
            if isinstance(slot.item, BiomassItem) and slot.item.kind == kind:
                yield slot
            elif slot.item is None:
                yield slot

    def amount_for_kind(self, kind: str) -> float:
        if kind == "biomass":
            return sum(
                float(s.item.amount)
                for s in self.slots
                if isinstance(s.item, BiomassItem) and s.item.kind == kind
            )
        return 0.0

    def capacity_for_kind(self, kind: str) -> float:
        return sum(
            float(s.max_mass) for s in self.slots if kind in s.allowed_kinds
        )

    def free_space_for_kind(self, kind: str) -> float:
        return max(0.0, self.capacity_for_kind(kind) - self.amount_for_kind(kind))

    def set_amount_for_kind(self, kind: str, amount: float) -> None:
        amount = max(0.0, float(amount))
        if kind != "biomass":
            raise ValueError(f"unsupported kind for set_amount: {kind!r}")
        for slot in self.slots:
            if isinstance(slot.item, BiomassItem) and slot.item.kind == kind:
                slot.item = None
        if amount <= 0:
            return
        slot = self._primary_slot_for_kind(kind, create=True)
        cap = float(slot.max_mass)
        slot.item = BiomassItem(amount=min(amount, cap) if cap > 0 else amount)

    def set_capacity_for_kind(self, kind: str, cap: float) -> None:
        cap = max(0.0, float(cap))
        if kind != "biomass":
            raise ValueError(f"unsupported kind for set_capacity: {kind!r}")
        if not self.slots:
            self.slots = _slot_defs_from_config(max_mass=cap)
            return
        kind_slots = [s for s in self.slots if kind in s.allowed_kinds]
        if len(kind_slots) == 1:
            kind_slots[0].max_mass = cap
            stored = self.amount_for_kind(kind)
            if stored > cap:
                self.set_amount_for_kind(kind, cap)
            return
        self.slots = _slot_defs_from_config(max_mass=cap)
        self.set_amount_for_kind(kind, min(self.amount_for_kind(kind), cap))

    def deposit_kind(self, kind: str, amount: float) -> float:
        amount = float(amount)
        if amount <= 0:
            return 0.0
        if kind != "biomass":
            return 0.0
        space = self.free_space_for_kind(kind)
        added = min(amount, space)
        if added <= 0:
            return 0.0
        slot = self._primary_slot_for_kind(kind, create=True)
        if slot.item is None:
            slot.item = BiomassItem(amount=added)
        else:
            slot.item.amount = float(slot.item.amount) + added
        return added

    def withdraw_kind(self, kind: str, amount: float) -> float:
        amount = float(amount)
        if amount <= 0 or self.amount_for_kind(kind) <= 0:
            return 0.0
        taken = min(amount, self.amount_for_kind(kind))
        remaining = self.amount_for_kind(kind) - taken
        self.set_amount_for_kind(kind, remaining)
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

    def _primary_slot_for_kind(self, kind: str, *, create: bool = False) -> InventorySlot:
        for slot in self.slots:
            if kind in slot.allowed_kinds:
                return slot
        if create:
            slot = InventorySlot(max_mass=400.0, allowed_kinds=frozenset({kind}))
            self.slots.append(slot)
            return slot
        raise ValueError(f"no slot for kind {kind!r}")
