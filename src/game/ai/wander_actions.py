"""ゲーム層: デフォルト徘徊（満腹帯・所属者の飢餓時は優先度ゼロ）。"""
from __future__ import annotations

from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import needs_self_feed, wander_step


class WanderAction(Action):
    DEFAULT_PARAMS = {
        "angle_range": 30,
        "speed_multiplier": 0.85,
    }

    def execute(self, creature) -> bool:
        wander_step(
            creature,
            self.params["angle_range"],
            self.params["speed_multiplier"],
        )
        return False

    def calculate_utility(self, creature) -> float:
        if getattr(creature, "affiliation", None) is not None and needs_self_feed(creature):
            return 0.0
        return 0.6
