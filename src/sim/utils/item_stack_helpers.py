"""ItemStack とインベントリ間の移動（Phase 4）。"""
from __future__ import annotations

from copy import copy

from src.sim.components.inventory import BiomassItem, InventoryItem
from src.sim.components.object_storage import ObjectStorage
from src.sim.utils.inventory_helpers import get_creature_inventory


def transfer_biomass_creature_to_storage(creature, storage: ObjectStorage) -> float:
    """生物インベントリのバイオマスを storage ItemStack へ移す。"""
    inv = get_creature_inventory(creature)
    if inv is None or storage is None:
        return 0.0

    moved = 0.0
    for slot in list(inv.slots):
        item = slot.item
        if not isinstance(item, BiomassItem) or item.amount <= 0:
            continue
        chunk = float(item.amount)
        deposited = storage.stack.deposit_biomass(chunk)
        if deposited <= 0:
            break
        moved += deposited
        item.amount = max(0.0, item.amount - deposited)
        if item.amount <= 0:
            inv.clear_slot(slot)
    return moved


def transfer_biomass_storage_to_creature(
    creature,
    storage: ObjectStorage,
    amount: float,
) -> float:
    """storage から生物の空きスロットへバイオマスを移す。"""
    inv = get_creature_inventory(creature)
    if inv is None or storage is None or amount <= 0:
        return 0.0

    remaining = min(float(amount), storage.stack.biomass_amount())
    moved = 0.0
    while remaining > 1e-9:
        target = None
        for slot in inv.slots:
            if slot.can_accept("biomass"):
                target = slot
                break
            if isinstance(slot.item, BiomassItem):
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

        chunk = min(remaining, space, storage.stack.biomass_amount())
        if chunk <= 0:
            break

        withdrawn = storage.stack.withdraw_biomass(chunk)
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
    """空き storage スロットへインベントリ全アイテムを移す（非バイオマス含む）。"""
    inv = get_creature_inventory(creature)
    if inv is None or storage is None:
        return 0

    moved = 0
    for slot in list(inv.slots):
        item = slot.item
        if item is None:
            continue
        if isinstance(item, BiomassItem):
            if transfer_biomass_creature_to_storage(creature, storage) > 0:
                moved += 1
            continue
        if storage.stack.deposit_item(copy(item)):
            inv.clear_slot(slot)
            moved += 1
    return moved


def storage_biomass_amount(storage: ObjectStorage | None) -> float:
    if storage is None:
        return 0.0
    return float(storage.stored_food)
