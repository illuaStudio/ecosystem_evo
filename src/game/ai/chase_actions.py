"""ゲーム層: 単独捕食（クモ等）。"""
from __future__ import annotations

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.combat.pickup_target import (
    consume_forage_target,
    is_forage_field_target,
    is_trackable_forage_target,
    move_toward_forage_target,
)
from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    contact_range,
    find_nearest_edible_among,
    is_trackable_prey,
    move_toward_contact,
    needs_self_feed,
    try_predate,
)
from src.sim.utils.field_pickup_helpers import is_field_pickup, pickup_radius

_MICRO_FAUNA_DEFAULT = DEFAULT_MICRO_FAUNA_SPECIES[0]


def chase_prey_species(params: dict) -> tuple[str, ...]:
    if params.get("target_types"):
        return tuple(params["target_types"])
    return (params.get("target_type", _MICRO_FAUNA_DEFAULT),)


class ChaseAction(Action):
    """視界内の指定種族を追跡し、接触時に bite → 地面バイオマス消費で捕食する。"""

    DEFAULT_PARAMS = {
        "target_type": _MICRO_FAUNA_DEFAULT,
        "target_types": None,
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

        pad = float(self.params["contact_padding"])
        if is_field_pickup(target):
            reach = pickup_radius(target) + pad
        else:
            reach = contact_range(creature, target, pad)
        prey_species = self._prey_species()

        if is_field_pickup(target) or not target.alive:
            if not is_forage_field_target(creature.world, target):
                self._target = None
                return False
            dist = move_toward_forage_target(
                creature,
                target,
                float(self.params["speed_multiplier"]),
            )
            if dist <= reach * 1.05:
                consume_forage_target(
                    creature,
                    target,
                    bite_gain=float(self.params["bite_gain"]),
                )
        else:
            dist = move_toward_contact(
                creature, target, self.params["speed_multiplier"], pad
            )
            if dist <= reach:
                try_predate(
                    creature,
                    target,
                    attack_power=float(self.params["attack_power"]),
                    bite_gain=float(self.params["bite_gain"]),
                )

        if not self._trackable_prey(creature, target, prey_species):
            self._target = None

        return False

    def _prey_species(self) -> tuple[str, ...]:
        return chase_prey_species(self.params)

    def _trackable_prey(self, creature, target, species: tuple[str, ...]) -> bool:
        if is_field_pickup(target) or (
            target is not None and not getattr(target, "alive", True)
        ):
            return is_trackable_forage_target(creature, target, species)
        return is_trackable_prey(creature, target, species)

    def calculate_utility(self, creature) -> float:
        prey = find_nearest_edible_among(
            creature, self._prey_species(), exclude=creature
        )
        if prey is None:
            return 0.0
        if not needs_self_feed(creature):
            return 0.0
        closeness = closeness_ratio(creature, prey)
        return min(1.0, 0.35 + closeness * 0.65)

    def _resolve_target(self, creature):
        species = self._prey_species()
        if self._trackable_prey(creature, self._target, species):
            return self._target
        self._target = find_nearest_edible_among(
            creature, species, exclude=creature
        )
        return self._target
