# actions.py
import math
import random
from abc import ABC, abstractmethod


class Action(ABC):
    def __init__(self):
        self.completed = False

    @abstractmethod
    def execute(self, creature) -> bool:
        pass

    def is_completed(self) -> bool:
        return self.completed

    def calculate_utility(self, creature) -> float:
        return 0.5

class WanderAction(Action):
    def __init__(self, angle_range: int = 30, speed_multiplier: float = 0.85):
        super().__init__()
        self.angle_range = angle_range
        self.speed_multiplier = speed_multiplier

    def execute(self, creature) -> bool:
        creature.wander_angle += random.uniform(-self.angle_range, self.angle_range)
        move = creature.get_current_speed() * self.speed_multiplier
        creature.pos[0] += math.cos(math.radians(creature.wander_angle)) * move
        creature.pos[1] += math.sin(math.radians(creature.wander_angle)) * move
        return False

    def calculate_utility(self, creature) -> float:
        return 0.6


class ChaseAction(Action):
    """視界内の指定種族を追跡し、接触時に捕食する。"""

    def __init__(
        self,
        target_type: str = "Amoeba",
        speed_multiplier: float = 1.25,
        contact_padding: float = 8.0,
    ):
        super().__init__()
        self.target_type = target_type
        self.speed_multiplier = speed_multiplier
        self.contact_padding = contact_padding
        self._target = None

    def execute(self, creature) -> bool:
        if not creature.world:
            return False

        target = self._resolve_target(creature)
        if target is None:
            return False

        dist_after_move = self._approach(creature, target)
        if dist_after_move <= self._reach(creature, target):
            self._feed(creature, target)
            self._target = None

        return False

    def calculate_utility(self, creature) -> float:
        prey = self._find_prey(creature)
        if prey is None:
            return 0.0

        hunger = self._hunger_ratio(creature)
        if hunger < 0.2:
            return 0.0

        closeness = self._closeness_ratio(creature, prey)
        return min(1.0, hunger * (0.35 + closeness * 0.65))

    def _resolve_target(self, creature):
        if self._is_trackable(creature, self._target):
            return self._target
        self._target = self._find_prey(creature)
        return self._target

    def _is_trackable(self, creature, target) -> bool:
        if target is None or not target.alive:
            return False
        if target.species.name != self.target_type:
            return False
        return self._distance(creature, target) <= creature.get_current_vision()

    def _find_prey(self, creature):
        if not creature.world:
            return None
        return creature.world.get_nearest_creature(
            creature.pos,
            species_name=self.target_type,
            max_dist=creature.get_current_vision(),
            exclude=creature,
        )

    @staticmethod
    def _distance(creature, other) -> float:
        return math.hypot(
            other.pos[0] - creature.pos[0],
            other.pos[1] - creature.pos[1],
        )

    def _approach(self, creature, target) -> float:
        """ターゲットへ移動し、移動後の距離を返す。"""
        dx = target.pos[0] - creature.pos[0]
        dy = target.pos[1] - creature.pos[1]
        dist = math.hypot(dx, dy)
        if dist == 0:
            return 0.0

        step = creature.get_current_speed() * self.speed_multiplier
        creature.pos[0] += (dx / dist) * step
        creature.pos[1] += (dy / dist) * step
        return self._distance(creature, target)

    def _reach(self, creature, target) -> float:
        return (
            creature.traits["base_size"]
            + target.traits.get("base_size", 9)
            + self.contact_padding
        )

    @staticmethod
    def _feed(creature, target) -> None:
        stolen = min(45, target.energy * 0.8)
        target.energy -= stolen
        cap = creature.traits.get("max_energy", 400)
        creature.energy = min(cap, creature.energy + stolen * 1.1)
        if target.energy <= 0:
            target.alive = False

    @staticmethod
    def _hunger_ratio(creature) -> float:
        cap = creature.traits.get("max_energy", 400)
        if cap <= 0:
            return 1.0
        return max(0.0, min(1.0, 1.0 - creature.energy / cap))

    def _closeness_ratio(self, creature, prey) -> float:
        vision = creature.get_current_vision()
        if vision <= 0:
            return 0.0
        return max(0.0, min(1.0, 1.0 - self._distance(creature, prey) / vision))