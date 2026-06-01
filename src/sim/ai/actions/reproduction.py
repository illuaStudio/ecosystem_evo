import math
import random

from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import is_at_population_cap
from src.sim.utils.position_helpers import entity_xy


class ReproductionAction(Action):
    """繁殖系アクションの基底。卵生・交配などはサブクラスで spawn 戦略を差し替える。"""

    def _blocked_by_population_cap(self, creature) -> bool:
        return is_at_population_cap(creature)

    def _offspring_position(self, parent, distance: float) -> tuple[float, float]:
        angle = random.uniform(0, 360)
        px, py = entity_xy(parent)
        x = px + math.cos(math.radians(angle)) * distance
        y = py + math.sin(math.radians(angle)) * distance
        if parent.world:
            margin = 30
            x = max(margin, min(parent.world.width - margin, x))
            y = max(margin, min(parent.world.height - margin, y))
        return x, y

    def _register_offspring(self, parent, offspring, *, spawn_source: str = "reproduction") -> None:
        if parent.world:
            parent.world.add_creature(
                offspring, spawn_source=spawn_source, parent=parent
            )
