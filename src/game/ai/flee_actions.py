"""ゲーム層: 脅威種からの逃走。"""
from __future__ import annotations

from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    find_nearest_flee_threat_among,
    is_flee_latch_active,
    is_flee_threat,
    is_in_vision,
    move_away_from,
    update_flee_latch,
)


class FleeAction(Action):
    """指定種（兵隊蟻・クモ等）から離れる。"""

    DEFAULT_PARAMS = {
        "threat_species": (),
        "speed_multiplier": 1.5,
        "safe_distance_ratio": 0.55,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._threat = None

    def _threats(self) -> tuple[str, ...]:
        return tuple(self.params.get("threat_species") or ())

    def execute(self, creature) -> bool:
        threats = self._threats()
        if not threats or not creature.world:
            return False

        update_flee_latch(creature, threats)
        if not is_flee_latch_active(creature):
            return False

        threat = self._resolve_threat(creature, threats)
        if threat is None:
            return False

        move_away_from(
            creature,
            threat,
            speed_multiplier=float(self.params["speed_multiplier"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        threats = self._threats()
        if not threats:
            return 0.0

        update_flee_latch(creature, threats)
        if is_flee_latch_active(creature):
            return 1.0

        threat = find_nearest_flee_threat_among(
            creature, threats, exclude=creature
        )
        if threat is None:
            return 0.0

        closeness = closeness_ratio(creature, threat)
        return min(1.0, 0.7 + closeness * 0.3)

    def _resolve_threat(self, creature, threats: tuple[str, ...]):
        if (
            self._threat is not None
            and is_flee_threat(creature, self._threat, threats)
            and is_in_vision(creature, self._threat)
        ):
            return self._threat
        self._threat = find_nearest_flee_threat_among(
            creature, threats, exclude=creature
        )
        return self._threat
