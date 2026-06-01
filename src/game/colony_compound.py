"""ゲーム層: 勢力拠点 storage への預け入れ・給餌。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.sim.utils.world_object_helpers import (
    get_affiliation_root,
    owner_species_for_affiliation,
)

if TYPE_CHECKING:
    from src.sim.systems.world import World


class ColonyCompoundRuntime:
    def __init__(self, world: "World") -> None:
        self.world = world

    def deposit_space(self, affiliation_id: str) -> float:
        root = get_affiliation_root(self.world, affiliation_id)
        if root is None or root.storage is None:
            return 0.0
        return max(0.0, root.storage.capacity - root.storage.stored_mass)

    def deposit_carried(self, creature) -> float:
        from src.sim.utils.inventory_helpers import clear_inventory_for_kind, inventory_is_loaded
        from src.sim.utils.world_object_helpers import (
            deposit_carried_to_parent,
            get_creature_compound_parent_ids,
        )
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        if not inventory_is_loaded(creature):
            return 0.0
        if get_creature_compound_parent_ids(creature):
            return deposit_carried_to_parent(creature)

        affiliation_id = get_creature_affiliation_id(creature)
        if not affiliation_id:
            return 0.0
        root = get_affiliation_root(self.world, affiliation_id)
        if root is None or root.storage is None:
            return 0.0
        amount = clear_inventory_for_kind(creature)
        if amount <= 0:
            return 0.0
        return root.storage.deposit(amount)

    def feed_creature(
        self,
        creature,
        *,
        bite_gain: float = 1.2,
        feed_per_tick: float = 11.0,
    ) -> float:
        from src.sim.utils.world_object_helpers import (
            feed_creature_from_parent,
            get_creature_compound_parent_ids,
        )
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        if get_creature_compound_parent_ids(creature):
            return feed_creature_from_parent(
                creature,
                bite_gain=bite_gain,
                feed_per_tick=feed_per_tick,
            )

        affiliation_id = get_creature_affiliation_id(creature)
        root = get_affiliation_root(self.world, affiliation_id) if affiliation_id else None
        if root is None or root.storage is None:
            return 0.0
        if root.storage.stored_mass <= 0:
            return 0.0

        max_sat = float(creature.max_satiety)
        if float(creature.satiety) >= max_sat:
            return 0.0

        take = min(root.storage.stored_mass, float(feed_per_tick))
        if take <= 0:
            return 0.0

        root.storage.withdraw(take)
        creature.satiety = min(
            max_sat,
            creature.satiety + take * float(bite_gain),
        )
        return take

    def owner_species(self, affiliation_id: str) -> str:
        return owner_species_for_affiliation(self.world, affiliation_id)
