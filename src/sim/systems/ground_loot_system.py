"""地面ルートの生成・減衰・削除。"""
from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Dict, Iterable, List, Optional

from src.sim.components.item_stack import ItemStack
from src.sim.entities.ground_loot import GroundLoot

if TYPE_CHECKING:
    from src.sim.systems.world import World


class GroundLootSystem:
    def __init__(self, world: "World") -> None:
        self.world = world
        self.loots: Dict[str, GroundLoot] = {}

    def spawn_biomass(
        self,
        x: float,
        y: float,
        amount: float,
        *,
        decompose_rate: float = 0.00003,
        source_species: str = "",
        color: tuple[int, int, int] = (140, 120, 90),
        pickup_radius: float = 12.0,
    ) -> GroundLoot:
        amount = max(0.0, float(amount))
        loot_id = f"loot_{uuid.uuid4().hex[:10]}"
        stack = ItemStack.from_biomass_capacity(amount, amount)
        loot = GroundLoot(
            id=loot_id,
            x=float(x),
            y=float(y),
            stack=stack,
            initial_biomass=amount,
            decompose_rate=float(decompose_rate),
            source_species=str(source_species),
            color=tuple(color),
            pickup_radius=float(pickup_radius),
        )
        self.loots[loot_id] = loot
        return loot

    def get(self, loot_id: str) -> Optional[GroundLoot]:
        return self.loots.get(str(loot_id))

    def remove(self, loot: GroundLoot) -> None:
        if loot is None:
            return
        self.loots.pop(loot.id, None)

    def iter_in_radius(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        species_names: Iterable[str] | None = None,
    ) -> List[GroundLoot]:
        names = set(species_names) if species_names is not None else None
        r = float(radius)
        out: List[GroundLoot] = []
        for loot in self.loots.values():
            if loot.is_depleted():
                continue
            if names is not None and loot.source_species not in names:
                continue
            dist = math.hypot(loot.x - x, loot.y - y)
            if dist <= r:
                out.append(loot)
        return out

    def update(self, dt: float = 1.0) -> None:
        dt = float(dt)
        depleted: List[GroundLoot] = []
        for loot in list(self.loots.values()):
            if loot.is_depleted():
                depleted.append(loot)
                continue
            initial = max(float(loot.initial_biomass), 1.0)
            rate = max(0.0, float(loot.decompose_rate))
            decay = min(loot.biomass_amount(), initial * rate * dt)
            if decay > 0:
                loot.stack.withdraw_biomass(decay)
            if loot.is_depleted():
                depleted.append(loot)
        for loot in depleted:
            self.remove(loot)
