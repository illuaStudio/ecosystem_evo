"""ゲーム層: 拠点避難（SeekShelter）。"""
from __future__ import annotations

from src.sim.ai.actions.base import Action
from src.game.shelter_helpers import resolve_creature_shelter
from src.sim.shelter.helpers import (
    enter_creature_shelter,
    get_hide_radius,
    is_at_shelter,
    move_toward_shelter_avoiding_threat,
    nearest_shelter_threat,
    shelter_distance,
)
from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.movement_helpers import (
    is_flee_latch_active,
    update_flee_latch,
)
from src.sim.utils.world_object_helpers import get_creature_affiliation_root


class SeekShelterAction(Action):
    """脅威検知時に所属拠点へ逃げ、到着後は隠れる（標的から除外）。"""

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

        if getattr(creature, "affiliation", None) is None or inventory_is_loaded(creature):
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

        if getattr(creature, "affiliation", None) is None or inventory_is_loaded(creature):
            return 0.0
        if not creature.world:
            return 0.0

        if get_creature_affiliation_root(creature) is None:
            return 0.0

        update_flee_latch(creature, threats)
        if not is_flee_latch_active(creature):
            if is_creature_sheltered(creature):
                clear_creature_shelter(creature)
            return 0.0

        if is_creature_sheltered(creature):
            from src.game.affiliation_feed import (
                affiliation_has_usable_storage,
                needs_affiliation_feed,
            )

            if needs_affiliation_feed(creature) and affiliation_has_usable_storage(creature):
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
