"""ゲーム層: 所属拠点向け狩り（備蓄・給餌抑止・拠点リーシュ）。"""
from __future__ import annotations

from src.game.affiliation_feed import affiliation_blocks_hunt
from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.combat.pickup_target import (
    consume_forage_target,
    find_nearest_forage_among,
    is_forage_field_target,
    is_trackable_forage_target,
    move_toward_forage_target,
    try_pickup_forage_target,
)
from src.sim.combat.target_query import (
    find_nearest_prey_creature,
    is_trackable_prey_creature,
)
from src.sim.ai.actions.base import Action
from src.game.ai.tracking import (
    AffiliationLeashMixin,
    CreatureTargetMixin,
    TerritoryOnlyMixin,
)
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    contact_range,
    distance_between,
    is_creature_threatening_territory,
    is_flee_latch_active,
    move_toward_contact,
    needs_self_feed,
    try_attack_only,
    wander_step,
)
from src.sim.utils.field_pickup_helpers import (
    is_field_pickup,
    pickup_on_field,
    pickup_radius,
)
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.movement_helpers import is_beyond_nest_leash

_MICRO_FAUNA_DEFAULT = DEFAULT_MICRO_FAUNA_SPECIES[0]


def hunt_prey_species(params: dict) -> tuple[str, ...]:
    """HuntAction の target_types（優先）または target_type。"""
    if params.get("target_types"):
        return tuple(params["target_types"])
    return (params.get("target_type", _MICRO_FAUNA_DEFAULT),)


class HuntAction(AffiliationLeashMixin, TerritoryOnlyMixin, CreatureTargetMixin, Action):
    """獲物を追跡し攻撃・殺害。満腹時は地面バイオマスを拾って拠点へ、飢餓時はその場で食べる。"""

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
        if is_field_pickup(target):
            world = getattr(creature, "world", None)
            return (
                target.pickup_species_filter in self._prey_species()
                and pickup_on_field(world, target)
            )
        if target is None or target.alive:
            return False
        return False

    def _find_living_prey(self, creature, species: tuple[str, ...]):
        if self._defense_hunt():
            kwargs = self._prey_query_kwargs()
        else:
            kwargs = {**self._prey_query_kwargs(), "living_only": True}
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
        if self._defense_hunt():
            return self._find_living_prey(creature, species)

        carcass = find_nearest_forage_among(creature, species, exclude=creature)
        living = self._find_living_prey(creature, species)

        if carcass is None:
            return living
        if living is None:
            return carcass
        if distance_between(creature, carcass) <= distance_between(creature, living):
            return carcass
        return living

    def _trackable_prey(self, creature, target, species: tuple[str, ...]) -> bool:
        if is_field_pickup(target) or (
            target is not None and not getattr(target, "alive", True)
        ):
            return is_trackable_forage_target(creature, target, species)
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
            is_field_pickup(target) or not getattr(target, "alive", True)
        ):
            self._target = None
            return False

        if (
            not self._defense_hunt()
            and needs_self_feed(creature)
            and affiliation_blocks_hunt(creature)
            and not self._is_field_carcass_prey(creature, target)
        ):
            self._target = None
            return False

        pad = float(self.params["contact_padding"])
        if is_field_pickup(target):
            reach = pickup_radius(target) + pad
        else:
            reach = contact_range(creature, target, pad)

        if is_field_pickup(target) or not getattr(target, "alive", True):
            if not is_forage_field_target(creature.world, target):
                self._target = None
                return False
            dist = move_toward_forage_target(
                creature,
                target,
                float(self.params["speed_multiplier"]),
            )
            if dist <= reach * 1.05:
                if needs_self_feed(creature):
                    consume_forage_target(
                        creature,
                        target,
                        bite_gain=float(self.params["bite_gain"]),
                    )
                elif not needs_self_feed(creature) and self.params.get("pickup_on_kill", True):
                    if try_pickup_forage_target(creature, target, pad):
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
            and affiliation_blocks_hunt(creature)
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

    def _hunt_dampen_radius(self) -> float:
        raw = self.params.get("affiliation_hunt_dampen_radius")
        if raw is None:
            raw = self.params.get("nest_hunt_dampen_radius")
        return float(raw if raw is not None else 55.0)

    def _hunt_dampen_fill_ratio(self) -> float:
        raw = self.params.get("affiliation_hunt_dampen_fill_ratio")
        if raw is None:
            raw = self.params.get("nest_hunt_dampen_fill_ratio")
        return float(raw if raw is not None else 0.75)

    def _hunt_dampen_factor(self) -> float:
        raw = self.params.get("affiliation_hunt_dampen_factor")
        if raw is None:
            raw = self.params.get("nest_hunt_dampen_factor")
        return float(raw if raw is not None else 0.2)

    def _affiliation_hunt_dampening(self, creature) -> float:
        if needs_self_feed(creature) or not creature.world:
            return 1.0
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id
        from src.sim.utils.affiliation_site_helpers import distance_to_affiliation_site
        from src.sim.utils.world_object_helpers import (
            affiliation_fill_ratio,
            get_affiliation_root,
        )

        affiliation_id = get_creature_affiliation_id(creature)
        if not affiliation_id or get_affiliation_root(creature.world, affiliation_id) is None:
            return 1.0
        if distance_to_affiliation_site(creature) > self._hunt_dampen_radius():
            return 1.0
        if affiliation_fill_ratio(creature.world, affiliation_id) < self._hunt_dampen_fill_ratio():
            return 1.0
        return self._hunt_dampen_factor()

    def _hunt_drive(self, creature, prey=None) -> float:
        if self._defense_hunt():
            return 1.0
        if self._territory_only():
            if needs_self_feed(creature):
                return 0.0
            return 1.0

        if needs_self_feed(creature):
            if affiliation_blocks_hunt(creature) and not self._is_field_carcass_prey(
                creature, prey
            ):
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
        return score * self._affiliation_hunt_dampening(creature)

    def _resolve_target(self, creature):
        species = self._prey_species()
        return self._resolve_creature_target(
            creature,
            find_fn=lambda c: self._find_prey(c, species),
            trackable_fn=lambda c, t: self._trackable_prey(c, t, species),
        )
