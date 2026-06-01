"""エンジン層: utility が全て 0 のときの最小移動（ゲームルールなし）。"""
from __future__ import annotations

from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import wander_step


class IdleLocomotionAction(Action):
    """ランダムに少し動く。UtilityMind のフォールバック専用（utility 競争には出ない）。"""

    DEFAULT_PARAMS = {
        "angle_range": 30,
        "speed_multiplier": 0.85,
    }

    def execute(self, creature) -> bool:
        wander_step(
            creature,
            float(self.params["angle_range"]),
            float(self.params["speed_multiplier"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        return 0.0
