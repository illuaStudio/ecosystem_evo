# actions.py
import math
import random
from abc import ABC, abstractmethod

from src.utils.position_helpers import entity_xy
from src.utils.creature_helpers import (
    closeness_ratio,
    contact_range,
    current_size,
    distance_to_point,
    move_toward_point,
    find_nearest_edible,
    has_edible_carcass,
    hunger_ratio,
    is_trackable_target,
    move_toward,
    satiety_ratio,
    try_attack_only,
    try_pickup_carcass,
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
        "depletion_rate_threshold": 0.08,
        "no_absorb_escape_ticks": 4,
        "crowd_radius": 42.0,
        "crowd_escape_neighbors": 3,
        "crowd_sample_penalty": 28.0,
        "crowd_repulsion_strength": 0.35,
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


class HuntAction(Action):
    """獲物を追跡し攻撃・殺害。死骸はその場で食べず拾って巣へ運ぶ。"""

    HUNGER_THRESHOLD = 0.18

    DEFAULT_PARAMS = {
        "target_type": "Amoeba",
        "speed_multiplier": 1.3,
        "contact_padding": 8.0,
        "attack_power": 1.2,
        "pickup_on_kill": True,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            return False
        if creature.colony.is_carrying:
            return False

        target = self._resolve_target(creature)
        if target is None:
            return False

        dist = move_toward(creature, target, self.params["speed_multiplier"])
        pad = float(self.params["contact_padding"])
        if dist <= contact_range(creature, target, pad):
            if target.alive:
                try_attack_only(
                    creature,
                    target,
                    attack_power=float(self.params["attack_power"]),
                )
            if (
                not target.alive
                and has_edible_carcass(target)
                and self.params.get("pickup_on_kill", True)
            ):
                try_pickup_carcass(creature, target, pad)
            if not is_trackable_target(
                creature, target, self.params["target_type"]
            ):
                self._target = None

        return False

    def calculate_utility(self, creature) -> float:
        if getattr(creature, "colony", None) is None or creature.colony.is_carrying:
            return 0.0

        prey = find_nearest_edible(
            creature, self.params["target_type"], exclude=creature
        )
        if prey is None:
            return 0.0

        hunger = hunger_ratio(creature)
        if hunger < self.HUNGER_THRESHOLD:
            return 0.0

        closeness = closeness_ratio(creature, prey)
        return min(1.0, hunger * (0.4 + closeness * 0.6))

    def _resolve_target(self, creature):
        target_type = self.params["target_type"]
        if is_trackable_target(creature, self._target, target_type):
            return self._target
        self._target = find_nearest_edible(
            creature, target_type, exclude=creature
        )
        return self._target


class ReturnToNestAction(Action):
    """運搬中の死骸を巣へ持ち帰り、貯蔵にする。"""

    DEFAULT_PARAMS = {
        "speed_multiplier": 1.1,
        "deposit_radius": 30.0,
    }

    def execute(self, creature) -> bool:
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying or not creature.world:
            return False

        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None:
            return False

        dist = move_toward_point(
            creature,
            nest.x,
            nest.y,
            float(self.params["speed_multiplier"]),
        )
        if dist <= float(self.params["deposit_radius"]):
            creature.world.nest_system.deposit_carried(creature)

        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying:
            return 0.0
        if not creature.world:
            return 0.0

        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None:
            return 0.0

        dist = distance_to_point(creature, nest.x, nest.y)
        vision = max(creature.get_current_vision(), 1.0)
        closeness = max(0.0, min(1.0, 1.0 - dist / vision))
        return 0.85 + closeness * 0.15


class FeedAtNestAction(Action):
    """巣の貯蔵から食事する（コロニー共有の餌）。"""

    HUNGER_THRESHOLD = 0.25

    DEFAULT_PARAMS = {
        "bite_gain": 1.2,
        "max_take_ratio": 0.4,
        "feed_radius": 36.0,
    }

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            return False
        if creature.colony.is_carrying:
            return False

        ns = creature.world.nest_system
        if not ns.is_at_nest(creature, float(self.params["feed_radius"])):
            return False

        ns.feed_creature(
            creature,
            bite_gain=float(self.params["bite_gain"]),
            max_take_ratio=float(self.params["max_take_ratio"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or colony.is_carrying or not creature.world:
            return 0.0

        hunger = hunger_ratio(creature)
        if hunger < self.HUNGER_THRESHOLD:
            return 0.0

        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None or nest.stored_biomass <= 8.0:
            return 0.0

        if not creature.world.nest_system.is_at_nest(
            creature, float(self.params["feed_radius"])
        ):
            dist = creature.world.nest_system.distance_to_nest(creature)
            vision = max(creature.get_current_vision(), 1.0)
            if dist > vision * 1.2:
                return 0.0
            closeness = max(0.0, min(1.0, 1.0 - dist / vision))
            return hunger * closeness * 0.45

        fill = nest.stored_biomass / max(nest.max_storage, 1.0)
        return min(1.0, hunger * (0.5 + fill * 0.5))


class NestPatrolAction(Action):
    """巣の周辺を巡回（コロニーの結束・観察用の拠点行動）。"""

    DEFAULT_PARAMS = {
        "angle_range": 40,
        "speed_multiplier": 0.75,
        "patrol_radius": 130.0,
        "nest_pull_strength": 0.55,
    }

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            wander_step(
                creature,
                self.params["angle_range"],
                self.params["speed_multiplier"],
            )
            return False

        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None:
            wander_step(
                creature,
                self.params["angle_range"],
                self.params["speed_multiplier"],
            )
            return False

        from src.utils.position_helpers import entity_xy

        cx, cy = entity_xy(creature)
        dist = math.hypot(nest.x - cx, nest.y - cy)
        patrol_r = float(self.params["patrol_radius"])

        if dist > patrol_r * 1.15:
            pull = float(self.params["nest_pull_strength"])
            to_nest = math.degrees(math.atan2(nest.y - cy, nest.x - cx)) % 360
            creature.wander_angle = (
                creature.wander_angle * (1.0 - pull) + to_nest * pull
            ) % 360
            wander_step(creature, self.params["angle_range"] * 0.5, self.params["speed_multiplier"])
        else:
            wander_step(
                creature,
                self.params["angle_range"],
                self.params["speed_multiplier"],
            )
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or colony.is_carrying or not creature.world:
            return 0.0

        hunger = hunger_ratio(creature)
        if hunger > 0.55:
            return 0.0

        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None:
            return 0.2

        dist = creature.world.nest_system.distance_to_nest(creature)
        patrol_r = float(self.params["patrol_radius"])
        if dist <= patrol_r:
            members = creature.world.nest_system.member_count(
                nest.id, creature.species.name
            )
            social = min(0.25, (members - 1) * 0.08)
            return 0.35 + social + (1.0 - hunger) * 0.2
        return 0.15


class ReproductionAction(Action):
    """繁殖系アクションの基底。卵生・交配などはサブクラスで spawn 戦略を差し替える。"""

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
