"""インベントリの構築・拾得・預け・消費・表示。"""
from __future__ import annotations

from src.sim.components.inventory import BiomassItem, InventoryComponent, InventorySlot
from src.sim.utils.geo_helpers import distance_between
from src.sim.utils.movement_helpers import contact_range
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.target_helpers import has_edible_carcass


def _legacy_max_carry_from_mind(species, default: float = 50.0) -> float:
    """ReturnToNestAction.params.base_max_carry（移行前の JSON）。"""
    mind_data = getattr(species, "mind_data", {}) or {}
    for action_def in mind_data.get("actions", []):
        if action_def.get("name") != "ReturnToNestAction":
            continue
        params = action_def.get("params", {}) or {}
        if "base_max_carry" in params:
            return max(0.0, float(params["base_max_carry"]))
    return default


def build_inventory_from_species(species) -> InventoryComponent:
    """種定義から InventoryComponent を構築。"""
    raw = getattr(species, "inventory_data", None) or {}
    if not raw:
        max_mass = _legacy_max_carry_from_mind(species, default=0.0)
        if max_mass <= 0:
            return InventoryComponent(slots=[])
        raw = {
            "slot_count": 1,
            "slots": [{"max_mass": max_mass, "allowed_kinds": ["biomass"]}],
            "biomass_weight_per_unit": 1.0,
            "carry_speed_reference_weight": 80.0,
        }

    slot_count = int(raw.get("slot_count", 0))
    slot_defs = list(raw.get("slots") or [])
    slots: list[InventorySlot] = []
    for i in range(slot_count):
        spec = slot_defs[i] if i < len(slot_defs) else {}
        kinds = spec.get("allowed_kinds", ["biomass"])
        slots.append(
            InventorySlot(
                max_mass=max(0.0, float(spec.get("max_mass", 50.0))),
                allowed_kinds=frozenset(kinds),
            )
        )

    return InventoryComponent(
        slots=slots,
        biomass_weight_per_unit=float(raw.get("biomass_weight_per_unit", 1.0)),
        carry_speed_reference_weight=float(
            raw.get("carry_speed_reference_weight", 80.0)
        ),
    )


def get_creature_inventory(creature) -> InventoryComponent | None:
    return getattr(creature, "inventory", None)


def inventory_is_loaded(creature) -> bool:
    inv = get_creature_inventory(creature)
    return inv is not None and inv.is_loaded


def get_haul_max_carry(creature, default: float = 50.0) -> float:
    """先頭スロットのバイオマス入力量上限（HUD・テスト互換）。"""
    inv = get_creature_inventory(creature)
    if inv is None or not inv.slots:
        return default
    return inv.slot_max_mass(0)


def _remove_depleted_carcass(world, carcass) -> None:
    if world is None or carcass is None:
        return
    if carcass.remaining_biomass <= 0 and carcass in world.creatures:
        world.remove_creature(carcass)


def _detach_carcass_from_inventory(inv: InventoryComponent, carcass) -> None:
    """フィールドから消えた死骸への参照を外す（復活防止）。"""
    if inv is None or carcass is None:
        return
    for slot in inv.slots:
        item = slot.item
        if isinstance(item, BiomassItem) and item.source_carcass is carcass:
            item.source_carcass = None


def _return_biomass_chunk(
    world,
    carrier,
    chunk: float,
    carcass,
    *,
    cx: float,
    cy: float,
) -> None:
    """チャンクを死骸へ戻す。死骸がフィールドに無い場合はマナ還元のみ（復活させない）。"""
    if chunk <= 0:
        return
    if (
        carcass is not None
        and not getattr(carcass, "alive", True)
        and world is not None
        and carcass in world.creatures
    ):
        carcass.remaining_biomass += chunk
        return
    if world is not None:
        world.mana_layer.return_from_decomposition(chunk * 0.65, cx, cy)


def try_pickup_carcass(carrier, carcass, contact_padding: float = 8.0) -> bool:
    """接触した死骸から、空きスロット数ぶんチャンクを切り出す。"""
    inv = get_creature_inventory(carrier)
    if inv is None or inv.empty_slot_count <= 0:
        return False
    world = carrier.world
    if not has_edible_carcass(carcass):
        return False

    dist = distance_between(carrier, carcass)
    reach = contact_range(carrier, carcass, contact_padding)
    if dist > reach * 1.05:
        return False

    picked = False
    picked_amount = 0.0
    for slot in inv.slots:
        if not slot.can_accept("biomass"):
            continue
        if carcass.remaining_biomass <= 0:
            break
        chunk = min(float(carcass.remaining_biomass), slot.max_mass)
        if chunk <= 0:
            continue
        carcass.remaining_biomass -= chunk
        slot.item = BiomassItem(amount=chunk, source_carcass=carcass)
        picked = True
        picked_amount += chunk

    if picked and world is not None:
        _remove_depleted_carcass(world, carcass)
        if carcass.remaining_biomass <= 0 or carcass not in world.creatures:
            _detach_carcass_from_inventory(inv, carcass)
        from src.sim.emitters import emit_item_found

        emit_item_found(world, carrier, item_kind="biomass", amount=picked_amount)
    return picked


def release_inventory_biomass(carrier) -> None:
    """インベントリ内の全バイオマスを元死骸へ戻すかマナ還元。"""
    inv = get_creature_inventory(carrier)
    if inv is None or not inv.is_loaded:
        return

    world = carrier.world
    cx, cy = entity_xy(carrier)

    for slot in list(inv.slots):
        item = slot.item
        if not isinstance(item, BiomassItem) or item.amount <= 0:
            inv.clear_slot(slot)
            continue
        chunk = float(item.amount)
        carcass = item.source_carcass
        inv.clear_slot(slot)
        if chunk <= 0:
            continue
        _return_biomass_chunk(world, carrier, chunk, carcass, cx=cx, cy=cy)


def consume_inventory_biomass(creature, bite_gain: float = 1.35) -> float:
    """先頭のバイオマススロットをその場で消費（満腹度回復）。"""
    inv = get_creature_inventory(creature)
    if inv is None:
        return 0.0
    slot = inv.first_biomass_slot()
    if slot is None or not isinstance(slot.item, BiomassItem):
        return 0.0
    item = slot.item
    if item.amount <= 0:
        inv.clear_slot(slot)
        return 0.0

    base_size = float(creature.traits.get("base_size", 9.0))
    bite_gain = float(bite_gain)
    amount = min(
        item.amount * 0.45,
        base_size * bite_gain * 1.6,
    )
    item.amount = max(0.0, item.amount - amount * 0.9)

    gained = amount * bite_gain
    creature.satiety = min(creature.max_satiety, creature.satiety + gained)

    if item.amount <= 1.0:
        leftover = item.amount
        inv.clear_slot(slot)
        world = creature.world
        if world is not None and leftover > 0:
            cx, cy = entity_xy(creature)
            world.mana_layer.return_from_decomposition(leftover * 0.8, cx, cy)

    return gained


def total_biomass_amount(creature) -> float:
    inv = get_creature_inventory(creature)
    if inv is None:
        return 0.0
    return sum(
        s.item.amount
        for s in inv.iter_biomass_slots()
        if isinstance(s.item, BiomassItem)
    )


def clear_inventory_biomass(creature) -> float:
    """全バイオマススロットを空にし、合計量を返す（預け入れ用）。"""
    inv = get_creature_inventory(creature)
    if inv is None:
        return 0.0
    total = 0.0
    for slot in inv.slots:
        item = slot.item
        if isinstance(item, BiomassItem):
            total += float(item.amount)
        inv.clear_slot(slot)
    return total


def format_inventory_status(creature) -> str | None:
    """HUD 用: インベントリ内容と総重量。"""
    inv = get_creature_inventory(creature)
    if inv is None or inv.slot_count == 0:
        return None
    if not inv.is_loaded:
        return "インベントリ: 空\n総重量: 0.0"

    lines = ["インベントリ:"]
    for i, slot in enumerate(inv.slots):
        if slot.is_empty():
            continue
        item = slot.item
        if isinstance(item, BiomassItem):
            w = item.weight(biomass_weight_per_unit=inv.biomass_weight_per_unit)
            src = ""
            if item.source_carcass is not None:
                src = f"（元: {item.source_carcass.species.name}）"
            lines.append(
                f"  [{i + 1}] バイオマス {item.amount:.1f} / {slot.max_mass:.1f}  "
                f"(重量 {w:.1f}){src}"
            )
        else:
            w = item.weight(biomass_weight_per_unit=inv.biomass_weight_per_unit)
            lines.append(f"  [{i + 1}] {item.kind} (重量 {w:.1f})")
    lines.append(f"総重量: {inv.total_weight:.1f}")
    return "\n".join(lines)
