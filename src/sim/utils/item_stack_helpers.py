"""ItemStack とインベントリ間の移動。"""
from __future__ import annotations

from copy import copy

from src.sim.components.inventory import BiomassItem, InventoryItem
from src.sim.components.object_storage import ObjectStorage
from src.sim.utils.inventory_helpers import get_creature_inventory


def transfer_kind_creature_to_storage(
    creature,
    storage: ObjectStorage,
    *,
    kind: str = "biomass",
) -> float:
    inv = get_creature_inventory(creature)
    if inv is None or storage is None:
        return 0.0

    moved = 0.0
    for slot in list(inv.slots):
        item = slot.item
        if not isinstance(item, BiomassItem) or item.kind != kind or item.amount <= 0:
            continue
        chunk = float(item.amount)
        deposited = storage.stack.deposit_kind(kind, chunk)
        if deposited <= 0:
            break
        moved += deposited
        item.amount = max(0.0, item.amount - deposited)
        if item.amount <= 0:
            inv.clear_slot(slot)
    return moved


def transfer_kind_storage_to_creature(
    creature,
    storage: ObjectStorage,
    amount: float,
    *,
    kind: str = "biomass",
) -> float:
    inv = get_creature_inventory(creature)
    if inv is None or storage is None or amount <= 0:
        return 0.0

    remaining = min(float(amount), storage.stack.amount_for_kind(kind))
    moved = 0.0
    while remaining > 1e-9:
        target = None
        for slot in inv.slots:
            if slot.can_accept(kind):
                target = slot
                break
            if isinstance(slot.item, BiomassItem) and slot.item.kind == kind:
                space = max(0.0, slot.max_mass - float(slot.item.amount))
                if space > 0:
                    target = slot
                    break
        if target is None:
            break

        if isinstance(target.item, BiomassItem):
            space = max(0.0, target.max_mass - float(target.item.amount))
        else:
            space = float(target.max_mass)

        chunk = min(remaining, space, storage.stack.amount_for_kind(kind))
        if chunk <= 0:
            break

        withdrawn = storage.stack.withdraw_kind(kind, chunk)
        if withdrawn <= 0:
            break

        if target.item is None:
            target.item = BiomassItem(amount=withdrawn)
        else:
            target.item.amount = float(target.item.amount) + withdrawn
        moved += withdrawn
        remaining -= withdrawn

    return moved


def transfer_item_creature_to_storage(creature, storage: ObjectStorage) -> int:
    inv = get_creature_inventory(creature)
    if inv is None or storage is None:
        return 0

    moved = 0
    for slot in list(inv.slots):
        item = slot.item
        if item is None:
            continue
        if isinstance(item, BiomassItem):
            if transfer_kind_creature_to_storage(creature, storage, kind=item.kind) > 0:
                moved += 1
            continue
        if storage.stack.deposit_item(copy(item)):
            inv.clear_slot(slot)
            moved += 1
    return moved


def storage_amount_for_kind(storage: ObjectStorage | None, kind: str = "biomass") -> float:
    if storage is None:
        return 0.0
    return float(storage.stack.amount_for_kind(kind))
