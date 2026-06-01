from src.sim.ai.actions.base import Action
from src.sim.ai.actions.tracking import (
    AffiliationLeashMixin,
    CreatureTargetMixin,
    TerritoryOnlyMixin,
)
from src.sim.combat.target_query import (
    find_nearest_hostile_creature,
    is_trackable_hostile_creature,
)
from src.sim.utils.affiliation_group_helpers import (
    is_creature_affiliation_defeated as is_creature_affiliation_defeated,
)
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    contact_range,
    expand_affiliation_species,
    is_beyond_nest_leash,
    move_toward_contact,
    needs_self_feed,
    try_attack_only,
)


class CombatAction(AffiliationLeashMixin, TerritoryOnlyMixin, CreatureTargetMixin, Action):
    """視界内の敵対種を追跡し攻撃のみ（死骸の拾い・食事は行わない）。"""

    DEFAULT_PARAMS = {
        "hostile_species": (),
        "hostile_affiliation_ids": (),
        "speed_multiplier": 1.4,
        "contact_padding": 8.0,
        "attack_power": 1.3,
        "territory_only": False,
        "nest_leash_radius": None,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def _enemies(self, creature=None) -> tuple[str, ...]:
        raw = list(self.params.get("hostile_species") or ())
        colony_ids = self.params.get("hostile_affiliation_ids") or ()
        if colony_ids and creature is not None and creature.world is not None:
            raw.extend(expand_affiliation_species(creature.world, colony_ids))
        return tuple(raw)

    def _find_hostile(self, creature, enemies: tuple[str, ...]):
        ref = find_nearest_hostile_creature(
            creature,
            enemies,
            territory_only=self._territory_only(),
            exclude=creature,
        )
        return ref.as_creature() if ref else None

    def _trackable(self, creature, target, enemies: tuple[str, ...]) -> bool:
        return is_trackable_hostile_creature(
            creature,
            target,
            enemies,
            territory_only=self._territory_only(),
        )

    def execute(self, creature) -> bool:
        if not creature.world or is_creature_affiliation_defeated(creature):
            return False
        from src.sim.utils.inventory_helpers import inventory_is_loaded

        if inventory_is_loaded(creature):
            return False

        if self._abort_if_beyond_nest_leash(creature):
            return False

        enemies = self._enemies(creature)
        if not enemies:
            return False

        target = self._resolve_target(creature, enemies)
        if target is None:
            return False

        pad = float(self.params["contact_padding"])
        reach = contact_range(creature, target, pad)
        dist = move_toward_contact(
            creature, target, self.params["speed_multiplier"], pad
        )
        if dist <= reach:
            try_attack_only(
                creature,
                target,
                attack_power=float(self.params["attack_power"]),
            )
            if not self._trackable(creature, target, enemies):
                self._clear_target()

        return False

    def calculate_utility(self, creature) -> float:
        if is_creature_affiliation_defeated(creature):
            return 0.0
        from src.sim.utils.inventory_helpers import inventory_is_loaded

        if inventory_is_loaded(creature):
            return 0.0
        if is_beyond_nest_leash(creature, self._nest_leash()):
            return 0.0
        if self._territory_only() and needs_self_feed(creature):
            return 0.0

        enemies = self._enemies(creature)
        if not enemies:
            return 0.0

        foe = self._find_hostile(creature, enemies)
        if foe is None:
            return 0.0

        closeness = closeness_ratio(creature, foe)
        return min(1.0, 0.55 + closeness * 0.45)

    def _resolve_target(self, creature, enemies: tuple[str, ...]):
        return self._resolve_creature_target(
            creature,
            find_fn=lambda c: self._find_hostile(c, enemies),
            trackable_fn=lambda c, t: self._trackable(c, t, enemies),
        )
