from src.ai.actions.base import Action
from src.ai.actions.tracking import (
    CreatureTargetMixin,
    NestLeashMixin,
    TerritoryOnlyMixin,
)
from src.combat.target_query import (
    find_nearest_prey_creature,
    is_trackable_prey_creature,
)
from src.utils.movement_helpers import is_beyond_nest_leash
from src.utils.creature_helpers import (
    carcass_on_field,
    closeness_ratio,
    consume_carcass,
    contact_range,
    find_nearest_edible_among,
    is_flee_latch_active,
    is_trackable_prey,
    move_toward,
    move_toward_contact,
    needs_self_feed,
    nest_has_usable_food,
    try_attack_only,
    try_pickup_carcass,
    try_predate,
    wander_step,
)


class ChaseAction(Action):
    """視界内の指定種族を追跡し、接触時に bite → consume_carcass で捕食する。"""

    DEFAULT_PARAMS = {
        "target_type": "Amoeba",
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
        reach = contact_range(creature, target, pad)
        prey_species = self._prey_species()

        if not target.alive:
            if not carcass_on_field(creature.world, target):
                self._target = None
                return False
            dist = move_toward(
                creature,
                target,
                float(self.params["speed_multiplier"]),
            )
            if dist <= reach * 1.05:
                consume_carcass(
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


def chase_prey_species(params: dict) -> tuple[str, ...]:
    """ChaseAction の target_types（優先）または target_type。"""
    if params.get("target_types"):
        return tuple(params["target_types"])
    return (params.get("target_type", "Amoeba"),)


def hunt_prey_species(params: dict) -> tuple[str, ...]:
    """HuntAction の target_types（優先）または target_type。"""
    if params.get("target_types"):
        return tuple(params["target_types"])
    return (params.get("target_type", "Amoeba"),)


class HuntAction(NestLeashMixin, TerritoryOnlyMixin, CreatureTargetMixin, Action):
    """獲物を追跡し攻撃・殺害。満腹時は死骸を拾って巣へ、飢餓時はその場で食べる。"""

    DEFAULT_PARAMS = {
        "target_type": "Amoeba",
        "target_types": None,
        "speed_multiplier": 1.3,
        "contact_padding": 8.0,
        "attack_power": 1.2,
        "pickup_on_kill": True,
        "bite_gain": 1.35,
        "colony_hoard_strength": 0.8,
        "min_usable_food_ratio": 0.01,
        "min_usable_satiety_gain": 1.0,
        "territory_only": False,
        "nest_leash_radius": None,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def _prey_species(self) -> tuple[str, ...]:
        return hunt_prey_species(self.params)

    def _find_prey(self, creature, species: tuple[str, ...]):
        ref = find_nearest_prey_creature(
            creature,
            species,
            territory_only=self._territory_only(),
            exclude=creature,
        )
        return ref.as_creature() if ref else None

    def _trackable_prey(self, creature, target, species: tuple[str, ...]) -> bool:
        return is_trackable_prey_creature(
            creature,
            target,
            species,
            territory_only=self._territory_only(),
        )

    def is_completed(self) -> bool:
        return self.completed

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            return False
        colony = creature.colony
        if colony.is_carrying:
            self.completed = True
            return False

        if self._abort_if_beyond_nest_leash(creature):
            return False

        target = self._resolve_target(creature)
        if target is None:
            return False

        if needs_self_feed(creature) and self._nest_blocks_hunt(creature):
            self._target = None
            return False

        pad = float(self.params["contact_padding"])
        reach = contact_range(creature, target, pad)

        if not target.alive:
            if not carcass_on_field(creature.world, target):
                self._target = None
                return False
            dist = move_toward(creature, target, self.params["speed_multiplier"])
            if dist <= reach * 1.05:
                if needs_self_feed(creature):
                    consume_carcass(
                        creature,
                        target,
                        bite_gain=float(self.params["bite_gain"]),
                    )
                elif not needs_self_feed(creature) and self.params.get("pickup_on_kill", True):
                    if try_pickup_carcass(creature, target, pad):
                        self.completed = True
                        self._target = None
                    else:
                        self._target = None
                        wander_step(
                            creature,
                            angle_range=40.0,
                            speed_multiplier=0.55,
                        )
            if not self._trackable_prey(creature, target, self._prey_species()):
                self._target = None
            return False

        if needs_self_feed(creature) and self._nest_blocks_hunt(creature):
            self._target = None
            return False

        dist = move_toward_contact(
            creature, target, self.params["speed_multiplier"], pad
        )
        if dist <= reach:
            try_attack_only(
                creature,
                target,
                attack_power=float(self.params["attack_power"]),
            )
            if not self._trackable_prey(creature, target, self._prey_species()):
                self._target = None

        return False

    def _nest_blocks_hunt(self, creature) -> bool:
        if self._territory_only():
            return False
        return nest_has_usable_food(
            creature,
            min_food_ratio=float(self.params["min_usable_food_ratio"]),
            min_satiety_gain=float(self.params["min_usable_satiety_gain"]),
        )

    def _nest_hunt_dampening(self, creature) -> float:
        """備蓄が十分な巣のすぐ近くでは狩り優先度を下げ、巣際の Hunt↔Return 往復を抑える。"""
        if needs_self_feed(creature) or not creature.world:
            return 1.0
        ns = creature.world.nest_system
        nest = ns.get_creature_nest(creature)
        if nest is None:
            return 1.0
        if ns.distance_to_nest(creature) > float(self.params.get("nest_hunt_dampen_radius", 55.0)):
            return 1.0
        if nest.food_ratio < float(self.params.get("nest_hunt_dampen_food_ratio", 0.75)):
            return 1.0
        return float(self.params.get("nest_hunt_dampen_factor", 0.2))

    def _hunt_drive(self, creature) -> float:
        """飢餓時: 巣で食べられるなら狩らない。通常・満腹帯: 備蓄狩り。テリトリー防衛は満腹時のみ。"""
        if self._territory_only():
            if needs_self_feed(creature):
                return 0.0
            return 1.0

        if needs_self_feed(creature):
            if self._nest_blocks_hunt(creature):
                return 0.0
            return 1.0

        if not creature.world:
            return 0.0

        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None:
            return 0.0

        return float(self.params["colony_hoard_strength"])

    def calculate_utility(self, creature) -> float:
        if is_flee_latch_active(creature):
            return 0.0
        colony = getattr(creature, "colony", None)
        if colony is not None and colony.is_carrying:
            return 0.0
        if not self._territory_only() and colony is None:
            return 0.0
        if is_beyond_nest_leash(creature, self._nest_leash()):
            return 0.0

        prey = self._find_prey(creature, self._prey_species())
        if prey is None:
            return 0.0

        drive = self._hunt_drive(creature)
        if drive <= 0.0:
            return 0.0

        closeness = closeness_ratio(creature, prey)
        score = min(1.0, drive * (0.4 + closeness * 0.6))
        if self._territory_only():
            return score
        return score * self._nest_hunt_dampening(creature)

    def _resolve_target(self, creature):
        species = self._prey_species()
        return self._resolve_creature_target(
            creature,
            find_fn=lambda c: self._find_prey(c, species),
            trackable_fn=lambda c, t: self._trackable_prey(c, t, species),
        )
