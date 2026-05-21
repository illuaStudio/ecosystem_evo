# actions.py
from abc import ABC, abstractmethod

from creature_helpers import (
    closeness_ratio,
    contact_range,
    find_nearest_edible,
    has_edible_carcass,
    hunger_ratio,
    is_trackable_target,
    move_toward,
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


class ManaWanderAction(Action):
    """徘徊しつつ World.mana から満腹度を回復する（mind に登録した生物のみ）。"""

    SATIETY_CAP_RATIO = 0.95

    DEFAULT_PARAMS = {
        "angle_range": 30,
        "speed_multiplier": 0.85,
        "mana_absorption_rate": 0.8,
    }

    def execute(self, creature) -> bool:
        wander_step(
            creature,
            self.params["angle_range"],
            self.params["speed_multiplier"],
        )
        self._absorb_mana(creature)
        return False

    def _absorb_mana(self, creature) -> None:
        if not creature.world:
            return
        cap = creature.max_satiety * self.SATIETY_CAP_RATIO
        if creature.satiety >= cap:
            return

        # Amoeba: params.mana_absorption_rate（traits には置かない）
        rate = float(self.params["mana_absorption_rate"])
        room = cap - creature.satiety
        absorbed = min(rate, room, creature.world.mana)
        if absorbed <= 0:
            return

        creature.world.mana -= absorbed
        creature.satiety += absorbed

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
