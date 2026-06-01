from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.entities.ground_loot import GroundLoot
from src.sim.utils.loot_helpers import (
    find_nearest_field_biomass_among,
    is_biomass_field_target,
    is_trackable_biomass_target,
    loot_on_field,
    move_toward_biomass_target,
    consume_biomass_target,
    try_pickup_biomass_target,
)
from src.sim.ai.actions.base import Action
from src.sim.ai.actions.tracking import (
    CreatureTargetMixin,
    NestLeashMixin,
    TerritoryOnlyMixin,
)
from src.sim.combat.target_query import (
    find_nearest_prey_creature,
    is_trackable_prey_creature,
)
from src.sim.utils.creature_helpers import is_creature_threatening_territory
from src.sim.utils.movement_helpers import is_beyond_nest_leash
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.creature_helpers import (
    carcass_on_field,
    closeness_ratio,
    consume_carcass,
    contact_range,
    distance_between,
    find_nearest_edible_among,
    find_nearest_field_carcass_among,
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


_MICRO_FAUNA_DEFAULT = DEFAULT_MICRO_FAUNA_SPECIES[0]


class ChaseAction(Action):
    """視界内の指定種族を追跡し、接触時に bite → consume_carcass で捕食する。"""

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
        if isinstance(target, GroundLoot):
            reach = float(target.pickup_radius) + pad
        else:
            reach = contact_range(creature, target, pad)
        prey_species = self._prey_species()

        if isinstance(target, GroundLoot) or not target.alive:
            if not is_biomass_field_target(creature.world, target):
                self._target = None
                return False
            dist = move_toward_biomass_target(
                creature,
                target,
                float(self.params["speed_multiplier"]),
            )
            if dist <= reach * 1.05:
                consume_biomass_target(
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
        if isinstance(target, GroundLoot) or (target is not None and not getattr(target, "alive", True)):
            return is_trackable_biomass_target(creature, target, species)
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
    return (params.get("target_type", _MICRO_FAUNA_DEFAULT),)


def hunt_prey_species(params: dict) -> tuple[str, ...]:
    """HuntAction の target_types（優先）または target_type。"""
    if params.get("target_types"):
        return tuple(params["target_types"])
    return (params.get("target_type", _MICRO_FAUNA_DEFAULT),)


class HuntAction(NestLeashMixin, TerritoryOnlyMixin, CreatureTargetMixin, Action):
    """獲物を追跡し攻撃・殺害。満腹時は死骸を拾って巣へ、飢餓時はその場で食べる。"""

    DEFAULT_PARAMS = {
        "target_type": _MICRO_FAUNA_DEFAULT,
        "target_types": None,
        "speed_multiplier": 1.3,
        "contact_padding": 8.0,
        "attack_power": 1.2,
        "pickup_on_kill": True,
        "bite_gain": 1.35,
        "affiliation_hoard_strength": 0.8,
        "territory_only": False,
        "territory_threat": False,
        "territory_approach_margin": 80.0,
        "territory_threat_score_mult": 1.25,
        "defense_hunt": False,
        "living_only": False,
        "carcass_only_species": None,
        "carcass_utility_mult": 1.35,
        "nest_leash_radius": None,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def _defense_hunt(self) -> bool:
        return bool(self.params.get("defense_hunt"))

    def _territory_threat(self) -> bool:
        return bool(self.params.get("territory_threat"))

    def _territory_approach_margin(self) -> float:
        return float(self.params.get("territory_approach_margin", 80.0))

    def _prey_species(self) -> tuple[str, ...]:
        return hunt_prey_species(self.params)

    def _living_only(self) -> bool:
        if self._defense_hunt():
            return True
        return bool(self.params.get("living_only"))

    def _carcass_only_species(self) -> tuple[str, ...]:
        raw = self.params.get("carcass_only_species")
        if not raw:
            return ()
        return tuple(raw)

    def _prey_query_kwargs(self) -> dict:
        return {
            "territory_only": self._territory_only() and not self._defense_hunt(),
            "territory_threat": self._territory_threat() and not self._defense_hunt(),
            "territory_approach_margin": self._territory_approach_margin(),
            "living_only": self._living_only(),
            "carcass_only_species": self._carcass_only_species(),
        }

    def _is_carcass_only_prey(self, target) -> bool:
        if target is None or target.alive:
            return False
        return target.species.name in self._carcass_only_species()

    def _is_field_carcass_prey(self, creature, target) -> bool:
        """Hunt 対象種の現場バイオマス（地面ルート／旧死骸）。"""
        if isinstance(target, GroundLoot):
            world = getattr(creature, "world", None)
            return (
                target.source_species in self._prey_species()
                and loot_on_field(world, target)
            )
        if target is None or target.alive:
            return False
        if target.species.name not in self._prey_species():
            return False
        return carcass_on_field(getattr(creature, "world", None), target)

    def _find_living_prey(self, creature, species: tuple[str, ...]):
        """生きた獲物のみ（carcass_only_species は狩り対象外）。"""
        if self._defense_hunt():
            kwargs = self._prey_query_kwargs()
        else:
            kwargs = {
                **self._prey_query_kwargs(),
                "living_only": True,
            }
        living_species = tuple(s for s in species if s not in self._carcass_only_species())
        if not living_species:
            return None
        ref = find_nearest_prey_creature(
            creature,
            living_species,
            exclude=creature,
            **kwargs,
        )
        return ref.as_creature() if ref else None

    def _find_prey(self, creature, species: tuple[str, ...]):
        """視界内: 近い現場死骸を生きた獲物より優先。死骸がなければ狩り（防衛狩りは生きた個体のみ）。"""
        if self._defense_hunt():
            return self._find_living_prey(creature, species)

        carcass = find_nearest_field_biomass_among(
            creature, species, exclude=creature
        )
        living = self._find_living_prey(creature, species)

        if carcass is None:
            return living
        if living is None:
            return carcass
        if distance_between(creature, carcass) <= distance_between(creature, living):
            return carcass
        return living

    def _trackable_prey(self, creature, target, species: tuple[str, ...]) -> bool:
        if isinstance(target, GroundLoot) or (target is not None and not getattr(target, "alive", True)):
            return is_trackable_biomass_target(creature, target, species)
        return is_trackable_prey_creature(
            creature,
            target,
            species,
            **self._prey_query_kwargs(),
        )

    def is_completed(self) -> bool:
        return self.completed

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "affiliation", None) is None:
            return False
        if inventory_is_loaded(creature):
            self.completed = True
            return False

        if not self._defense_hunt() and self._abort_if_beyond_nest_leash(creature):
            return False

        target = self._resolve_target(creature)
        if target is None:
            return False

        if self._living_only() and (
            isinstance(target, GroundLoot) or not getattr(target, "alive", True)
        ):
            self._target = None
            return False

        if (
            not self._defense_hunt()
            and needs_self_feed(creature)
            and self._nest_blocks_hunt(creature)
            and not self._is_field_carcass_prey(creature, target)
        ):
            self._target = None
            return False

        pad = float(self.params["contact_padding"])
        if isinstance(target, GroundLoot):
            reach = float(target.pickup_radius) + pad
        else:
            reach = contact_range(creature, target, pad)

        if isinstance(target, GroundLoot) or not getattr(target, "alive", True):
            if not is_biomass_field_target(creature.world, target):
                self._target = None
                return False
            dist = move_toward_biomass_target(
                creature,
                target,
                float(self.params["speed_multiplier"]),
            )
            if dist <= reach * 1.05:
                if needs_self_feed(creature):
                    consume_biomass_target(
                        creature,
                        target,
                        bite_gain=float(self.params["bite_gain"]),
                    )
                elif not needs_self_feed(creature) and self.params.get("pickup_on_kill", True):
                    if try_pickup_biomass_target(creature, target, pad):
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

        if (
            not self._defense_hunt()
            and needs_self_feed(creature)
            and self._nest_blocks_hunt(creature)
            and not self._is_field_carcass_prey(creature, target)
        ):
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
        if self._defense_hunt() or self._territory_only():
            return False
        return nest_has_usable_food(creature)

    def _nest_hunt_dampening(self, creature) -> float:
        """備蓄が十分な巣のすぐ近くでは狩り優先度を下げ、巣際の Hunt↔Return 往復を抑える。"""
        if needs_self_feed(creature) or not creature.world:
            return 1.0
        ns = creature.world.nest_system
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        affiliation_id = get_creature_affiliation_id(creature)
        if not affiliation_id or ns.get_affiliation_root(affiliation_id) is None:
            return 1.0
        if ns.distance_to_nest(creature) > float(self.params.get("nest_hunt_dampen_radius", 55.0)):
            return 1.0
        if ns.affiliation_food_ratio(affiliation_id) < float(
            self.params.get("nest_hunt_dampen_food_ratio", 0.75)
        ):
            return 1.0
        return float(self.params.get("nest_hunt_dampen_factor", 0.2))

    def _hunt_drive(self, creature, prey=None) -> float:
        """飢餓時: 巣で食べられるなら狩らない。通常・満腹帯: 備蓄狩り。防衛狩りは常に最優先。"""
        if self._defense_hunt():
            return 1.0
        if self._territory_only():
            if needs_self_feed(creature):
                return 0.0
            return 1.0

        if needs_self_feed(creature):
            if self._nest_blocks_hunt(creature) and not self._is_field_carcass_prey(creature, prey):
                return 0.0
            return 1.0

        if not creature.world:
            return 0.0

        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        if not get_creature_affiliation_id(creature):
            return 0.0

        return float(self.params["affiliation_hoard_strength"])

    def calculate_utility(self, creature) -> float:
        if is_flee_latch_active(creature):
            return 0.0
        if inventory_is_loaded(creature):
            return 0.0
        if not self._territory_only() and getattr(creature, "affiliation", None) is None:
            return 0.0
        if not self._defense_hunt() and is_beyond_nest_leash(creature, self._nest_leash()):
            return 0.0

        prey = self._find_prey(creature, self._prey_species())
        if prey is None:
            return 0.0

        drive = self._hunt_drive(creature, prey)
        if drive <= 0.0:
            return 0.0

        closeness = closeness_ratio(creature, prey)
        base = 0.55 + closeness * 0.45 if self._defense_hunt() else 0.4 + closeness * 0.6
        score = min(1.0, drive * base)
        if self._defense_hunt() and self._territory_threat():
            margin = self._territory_approach_margin()
            if is_creature_threatening_territory(creature, prey, margin):
                score = min(
                    1.0,
                    score * float(self.params.get("territory_threat_score_mult", 1.25)),
                )
        if self._is_field_carcass_prey(creature, prey):
            return min(
                1.0,
                score * float(self.params.get("carcass_utility_mult", 1.35)),
            )
        if self._territory_only() or self._defense_hunt():
            return score
        return score * self._nest_hunt_dampening(creature)

    def _resolve_target(self, creature):
        species = self._prey_species()
        return self._resolve_creature_target(
            creature,
            find_fn=lambda c: self._find_prey(c, species),
            trackable_fn=lambda c, t: self._trackable_prey(c, t, species),
        )
