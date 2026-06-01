"""巣などの避難所へ逃げて隠れる。"""
from __future__ import annotations

from src.sim.ai.actions.base import Action
from src.sim.shelter.helpers import (
    enter_creature_shelter,
    get_hide_radius,
    is_at_shelter,
    move_toward_shelter_avoiding_threat,
    nearest_shelter_threat,
    resolve_creature_shelter,
    shelter_distance,
)
from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.movement_helpers import (
    is_flee_latch_active,
    update_flee_latch,
)


class SeekShelterAction(Action):
    """脅威検知時に所属巣穴へ逃げ、到着後は隠れる（標的から除外）。"""

    DEFAULT_PARAMS = {
        "threat_species": (),
        "speed_multiplier": 1.55,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target_ref = None

    def _threats(self) -> tuple[str, ...]:
        raw = self.params.get("threat_species") or ()
        return tuple(raw)

    def _leave_if_safe(self, creature, threats: tuple[str, ...]) -> None:
        if is_flee_latch_active(creature):
            return
        clear_creature_shelter(creature)
        self._target_ref = None

    def execute(self, creature) -> bool:
        threats = self._threats()
        if not threats or not creature.world:
            return False

        colony = getattr(creature, "colony", None)
        if colony is None or inventory_is_loaded(creature):
            return False

        update_flee_latch(creature, threats)
        self._leave_if_safe(creature, threats)

        if is_creature_sheltered(creature):
            return False

        if not is_flee_latch_active(creature):
            return False

        threat = nearest_shelter_threat(creature, threats)
        ref = resolve_creature_shelter(creature, threat)
        if ref is None:
            if threat is not None:
                from src.sim.utils.movement_helpers import move_away_from

                move_away_from(
                    creature,
                    threat,
                    float(self.params["speed_multiplier"]),
                )
            return False

        hide_r = get_hide_radius(creature)

        if is_at_shelter(creature, ref, hide_r):
            enter_creature_shelter(creature, ref)
            self._target_ref = ref
            return False

        move_toward_shelter_avoiding_threat(
            creature,
            ref,
            threat,
            speed_multiplier=float(self.params["speed_multiplier"]),
        )
        if is_at_shelter(creature, ref, hide_r):
            enter_creature_shelter(creature, ref)
            self._target_ref = ref
        return False

    def calculate_utility(self, creature) -> float:
        threats = self._threats()
        if not threats:
            return 0.0

        colony = getattr(creature, "colony", None)
        if colony is None or inventory_is_loaded(creature) or not creature.world:
            return 0.0

        if creature.world.nest_system.get_creature_nest(creature) is None:
            return 0.0

        update_flee_latch(creature, threats)
        if not is_flee_latch_active(creature):
            if is_creature_sheltered(creature):
                clear_creature_shelter(creature)
            return 0.0

        if is_creature_sheltered(creature):
            from src.sim.utils.creature_helpers import needs_nest_feed, nest_has_usable_storage

            if needs_nest_feed(creature) and nest_has_usable_storage(creature):
                return 0.0
            return 0.88

        threat = nearest_shelter_threat(creature, threats)
        ref = resolve_creature_shelter(creature, threat)
        if ref is None:
            return 0.75

        hide_r = get_hide_radius(creature)
        dist = shelter_distance(creature, ref)
        vision = max(creature.get_current_vision(), 1.0)
        closeness = max(0.0, min(1.0, 1.0 - dist / vision))
        return min(1.0, 0.82 + closeness * 0.18)
