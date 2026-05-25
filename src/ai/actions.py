# actions.py
import math
import random
from abc import ABC, abstractmethod

from src.utils.creature_helpers import (
    closeness_ratio,
    contact_range,
    current_size,
    find_nearest_edible,
    has_edible_carcass,
    hunger_ratio,
    is_trackable_target,
    move_toward,
    satiety_ratio,
    try_predate,
    wander_step,
)


class Action(ABC):
    """全アクション共通: JSON の params を self.params にマージして保持する。"""

    DEFAULT_PARAMS: dict = {}

    def __init__(self, **params):
        self.completed = False
        self.params = {**self.DEFAULT_PARAMS, **params}

    @abstractmethod
    def execute(self, creature) -> bool:
        pass

    def is_completed(self) -> bool:
        return self.completed

    def calculate_utility(self, creature) -> float:
        return 0.5


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
        return 0.6


class ManaGradientWanderAction(Action):
    """マナの濃い方向へ移動傾向を強めた徘徊行動。
    局所勾配に従い、周囲の残量変化を見ながら少しずつ移動する。"""

    SATIETY_CAP_RATIO = 0.95

    DEFAULT_PARAMS = {
        "angle_range": 45,
        "speed_multiplier": 0.9,
        "mana_absorption_rate": 0.75,
        "gradient_strength": 0.65,
        "local_gradient_radius": 35.0,
        "local_gradient_samples": 8,
        "escape_radius": 96.0,
        "depleted_ratio": 0.12,
    }

    def execute(self, creature) -> bool:
        world = creature.world
        if world is None or getattr(world, "mana_system", None) is None:
            wander_step(creature, self.params["angle_range"], self.params["speed_multiplier"])
            return False

        world.mana_system.apply_gradient_steering(creature, world, self.params)
        return False

    def calculate_utility(self, creature) -> float:
        hunger = hunger_ratio(creature)
        return 0.75 + hunger * 0.25


class ChaseAction(Action):
    """視界内の指定種族を追跡し、接触時に bite → consume_carcass で捕食する。"""

    HUNGER_THRESHOLD = 0.2

    DEFAULT_PARAMS = {
        "target_type": "Amoeba",
        "speed_multiplier": 1.25,
        "contact_padding": 8.0,
        "bite_gain": 1.35,
        "attack_power": 1.0,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def execute(self, creature) -> bool:
        if not creature.world:
            return False

        target = self._resolve_target(creature)
        if target is None:
            return False

        dist = move_toward(creature, target, self.params["speed_multiplier"])
        if dist <= contact_range(creature, target, self.params["contact_padding"]):
            try_predate(
                creature,
                target,
                attack_power=float(self.params["attack_power"]),
                bite_gain=float(self.params["bite_gain"]),
            )
            if target.alive or not has_edible_carcass(target):
                self._target = None

        return False

    def calculate_utility(self, creature) -> float:
        prey = find_nearest_edible(
            creature, self.params["target_type"], exclude=creature
        )
        if prey is None:
            return 0.0

        hunger = hunger_ratio(creature)
        if hunger < self.HUNGER_THRESHOLD:
            return 0.0

        closeness = closeness_ratio(creature, prey)
        return min(1.0, hunger * (0.35 + closeness * 0.65))

    def _resolve_target(self, creature):
        target_type = self.params["target_type"]
        if is_trackable_target(creature, self._target, target_type):
            return self._target
        self._target = find_nearest_edible(
            creature, target_type, exclude=creature
        )
        return self._target


class ReproductionAction(Action):
    """繁殖系アクションの基底。卵生・交配などはサブクラスで spawn 戦略を差し替える。"""

    def _offspring_position(self, parent, distance: float) -> tuple[float, float]:
        angle = random.uniform(0, 360)
        x = parent.pos[0] + math.cos(math.radians(angle)) * distance
        y = parent.pos[1] + math.sin(math.radians(angle)) * distance
        if parent.world:
            margin = 30
            x = max(margin, min(parent.world.width - margin, x))
            y = max(margin, min(parent.world.height - margin, y))
        return x, y

    def _register_offspring(self, parent, offspring) -> None:
        if parent.world:
            parent.world.add_creature(offspring)


class SplitAction(ReproductionAction):
    """無性分裂: 満腹・成熟・十分なサイズ・クールダウンを満たすと1子を隣接生成。"""

    DEFAULT_PARAMS = {
        "satiety_threshold": 0.75,
        "energy_cost": 0.39,
        "min_reproduce_size": 8.5,
        "size_reduction": 0.75,
        "offspring_size_ratio": 0.48,
        "offspring_satiety_ratio": 0.60,
        "cooldown": 160,
        "separation_distance": 13.0,
    }

    def can_execute(self, creature) -> bool:
        if not creature.alive or not creature.world:
            return False
        if creature.repro_cooldown > 0:
            return False

        mature_age = creature.life_cycle.get("mature")
        if mature_age is None or creature.age < int(mature_age):
            return False

        if current_size(creature) < float(self.params["min_reproduce_size"]):
            return False

        return satiety_ratio(creature) >= float(self.params["satiety_threshold"])

    def execute(self, creature) -> bool:
        if not self.can_execute(creature):
            return False

        from src.entities.creature_factory import CreatureFactory

        p = self.params
        parent_size = float(creature.traits["base_size"])
        parent_satiety = creature.satiety

        offspring_size = parent_size * float(p["offspring_size_ratio"])
        offspring_satiety = parent_satiety * float(p["offspring_satiety_ratio"])

        creature.satiety -= float(p["energy_cost"]) * creature.max_satiety
        creature.satiety = max(0.0, creature.satiety)
        creature.scale_size(float(p["size_reduction"]))

        ox, oy = self._offspring_position(creature, float(p["separation_distance"]))
        offspring = CreatureFactory.create_offspring(
            creature,
            ox,
            oy,
            base_size=offspring_size,
            satiety=offspring_satiety,
        )
        self._register_offspring(creature, offspring)

        creature.set_repro_cooldown(int(p["cooldown"]))
        self.completed = True
        return True

    def calculate_utility(self, creature) -> float:
        if not self.can_execute(creature):
            return 0.0

        sat = satiety_ratio(creature)
        threshold = float(self.params["satiety_threshold"])
        if sat < threshold:
            return 0.0

        headroom = max(1e-6, 1.0 - threshold)
        excess = (sat - threshold) / headroom
        return min(1.0, 0.55 + excess * 0.45)
