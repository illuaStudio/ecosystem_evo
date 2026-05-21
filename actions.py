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
    def __init__(self, target_type: str = "Amoeba", speed_multiplier: float = 1.25):
        super().__init__()
        self.target_type = target_type
        self.speed_multiplier = speed_multiplier
        self.target = None

    def execute(self, creature) -> bool:
        if not creature.world:
            return False

        # ターゲットを探す or 更新
        if self.target is None or not getattr(self.target, 'alive', True):
            self.target = self._find_nearest_target(creature)

        if self.target:
            dx = self.target.pos[0] - creature.pos[0]
            dy = self.target.pos[1] - creature.pos[1]
            dist = math.hypot(dx, dy)

            if dist > 0:
                speed = creature.get_current_speed() * self.speed_multiplier
                creature.pos[0] += (dx / dist) * speed
                creature.pos[1] += (dy / dist) * speed

            # 接触判定
            contact_dist = creature.traits["base_size"] + self.target.traits.get("base_size", 9) + 8
            if dist < contact_dist:
                self._eat_target(creature, self.target)
                self.completed = True
        else:
            # 獲物がいなければ軽く徘徊
            creature.wander_angle += random.uniform(-25, 25)
            move = creature.get_current_speed() * 0.7
            creature.pos[0] += math.cos(math.radians(creature.wander_angle)) * move
            creature.pos[1] += math.sin(math.radians(creature.wander_angle)) * move

        return False

    def _find_nearest_target(self, creature):
        """Worldを使って検索"""
        return creature.world.get_nearest_creature(
            creature.pos,
            species_name=self.target_type,
            max_dist=creature.get_current_vision()
        )

    def _eat_target(self, creature, target):
        eat = min(45, target.energy * 0.8)
        target.energy -= eat
        creature.energy += eat * 1.1
        if target.energy <= 0:
            target.alive = False

    def calculate_utility(self, creature) -> float:
        hunger = max(0.0, 1.0 - (creature.energy / creature.traits.get("max_energy", 400)))
        
        target = self._find_nearest_target(creature)
        proximity_bonus = 0.0
        if target:
            dist = math.hypot(target.pos[0] - creature.pos[0], target.pos[1] - creature.pos[1])
            proximity_bonus = max(0.0, 1.0 - (dist / creature.get_current_vision())) * 0.85

        utility = hunger * 1.55 + proximity_bonus * 1.1
        return min(1.0, utility)