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
        wander_step(creature, self.angle_range, self.speed_multiplier)
        return False

    def calculate_utility(self, creature) -> float:
        return 0.6


class ManaWanderAction(Action):
    """生産者専用: 徘徊しつつ World.mana から満腹度を回復する。"""

    SATIETY_CAP_RATIO = 0.95

    def __init__(self, angle_range: int = 30, speed_multiplier: float = 0.85):
        super().__init__()
        self.angle_range = angle_range
        self.speed_multiplier = speed_multiplier

    def execute(self, creature) -> bool:
        wander_step(creature, self.angle_range, self.speed_multiplier)
        self._absorb_mana(creature)
        return False

    def _absorb_mana(self, creature) -> None:
        if not creature.world:
            return
        cap = creature.max_satiety * self.SATIETY_CAP_RATIO
        if creature.satiety >= cap:
            return

        rate = float(creature.traits.get("mana_absorption_rate", 0.8))
        room = cap - creature.satiety
        absorbed = min(rate, room, creature.world.mana)
        if absorbed <= 0:
            return

        creature.world.mana -= absorbed
        creature.satiety += absorbed

    def calculate_utility(self, creature) -> float:
        if not creature.traits.get("is_producer", False):
            return 0.0
        hunger = hunger_ratio(creature)
        return 0.75 + hunger * 0.25


class ChaseAction(Action):
    """視界内の指定種族を追跡し、接触時に bite → consume_carcass で捕食する。"""

    HUNGER_THRESHOLD = 0.2

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

        dist = move_toward(creature, target, self.speed_multiplier)
        if dist <= contact_range(creature, target, self.contact_padding):
            try_predate(creature, target)
            if target.alive or not has_edible_carcass(target):
                self._target = None

        return False

    def calculate_utility(self, creature) -> float:
        prey = find_nearest_edible(
            creature, self.target_type, exclude=creature
        )
        if prey is None:
            return 0.0

        hunger = hunger_ratio(creature)
        if hunger < self.HUNGER_THRESHOLD:
            return 0.0

        closeness = closeness_ratio(creature, prey)
        return min(1.0, hunger * (0.35 + closeness * 0.65))

    def _resolve_target(self, creature):
        if is_trackable_target(creature, self._target, self.target_type):
            return self._target
        self._target = find_nearest_edible(
            creature, self.target_type, exclude=creature
        )
        return self._target
