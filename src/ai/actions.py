# actions.py
import math
import random
from abc import ABC, abstractmethod

from src.utils.position_helpers import entity_xy
from src.utils.creature_helpers import (
    closeness_ratio,
    carcass_on_field,
    consume_carcass,
    consume_carried_biomass,
    contact_range,
    current_size,
    distance_to_point,
    find_nearest_edible,
    find_nearest_edible_among,
    find_nearest_edible_in_territory_among,
    find_nearest_field_carcass_among,
    find_nearest_flee_threat_among,
    find_nearest_hostile_among,
    find_nearest_hostile_in_territory_among,
    has_edible_carcass,
    hunger_ratio,
    is_beyond_nest_leash,
    is_flee_latch_active,
    is_in_creature_territory,
    needs_self_feed,
    return_toward_nest,
    update_flee_latch,
    is_trackable_target,
    move_away_from,
    move_toward,
    move_toward_contact,
    move_toward_point,
    is_at_population_cap,
    is_trackable_hostile,
    is_trackable_prey,
    nest_has_usable_food,
    needs_nest_feed,
    release_carried_carcass,
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
        colony = getattr(creature, "colony", None)
        if colony is not None and needs_self_feed(creature):
            return 0.0
        return 0.6


class ManaWanderAction(Action):
    """自由徘徊しながらマナを吸収。濃い場所は鈍く、薄い場所は活発にランダム探索。"""

    DEFAULT_PARAMS = {
        "angle_range_sparse": 32,
        "angle_range_dense": 12,
        "speed_multiplier_sparse": 1.0,
        "speed_multiplier_dense": 0.35,
        "mana_absorption_rate": 0.75,
    }

    def execute(self, creature) -> bool:
        p = self.params
        world = creature.world
        if world is None:
            wander_step(
                creature,
                p["angle_range_sparse"],
                p["speed_multiplier_sparse"],
            )
            return False

        cap = max(1.0, float(getattr(world, "mana_density_cap", 2500.0)))
        pos = creature.position
        density = world.get_mana_density(pos.x, pos.y)
        t = min(1.0, max(0.0, density / cap))

        angle = p["angle_range_sparse"] + (p["angle_range_dense"] - p["angle_range_sparse"]) * t
        speed = p["speed_multiplier_sparse"] + (
            p["speed_multiplier_dense"] - p["speed_multiplier_sparse"]
        ) * t
        wander_step(creature, angle, speed)
        return False

    def calculate_utility(self, creature) -> float:
        hunger = hunger_ratio(creature)
        return 0.75 + hunger * 0.25


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

        pad = float(self.params["contact_padding"])
        reach = contact_range(creature, target, pad)
        target_type = self.params["target_type"]

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

        if not is_trackable_target(creature, target, target_type):
            self._target = None

        return False

    def calculate_utility(self, creature) -> float:
        prey = find_nearest_edible(
            creature, self.params["target_type"], exclude=creature
        )
        if prey is None:
            return 0.0

        if not needs_self_feed(creature):
            return 0.0

        closeness = closeness_ratio(creature, prey)
        return min(1.0, 0.35 + closeness * 0.65)

    def _resolve_target(self, creature):
        target_type = self.params["target_type"]
        if is_trackable_target(creature, self._target, target_type):
            return self._target
        self._target = find_nearest_edible(
            creature, target_type, exclude=creature
        )
        return self._target


def _hunt_prey_species(params: dict) -> tuple[str, ...]:
    """HuntAction の target_types（優先）または target_type。"""
    if params.get("target_types"):
        return tuple(params["target_types"])
    return (params.get("target_type", "Amoeba"),)


class CombatAction(Action):
    """視界内の敵対種を追跡し攻撃のみ（死骸の拾い・食事は行わない）。"""

    DEFAULT_PARAMS = {
        "hostile_species": (),
        "speed_multiplier": 1.4,
        "contact_padding": 8.0,
        "attack_power": 1.3,
        "territory_only": False,
        "nest_leash_radius": None,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def _enemies(self) -> tuple[str, ...]:
        raw = self.params.get("hostile_species") or ()
        return tuple(raw)

    def _territory_only(self) -> bool:
        return bool(self.params.get("territory_only"))

    def _find_hostile(self, creature, enemies: tuple[str, ...]):
        if self._territory_only():
            return find_nearest_hostile_in_territory_among(
                creature, enemies, exclude=creature
            )
        return find_nearest_hostile_among(creature, enemies, exclude=creature)

    def _trackable(self, creature, target, enemies: tuple[str, ...]) -> bool:
        if not is_trackable_hostile(creature, target, enemies):
            return False
        if self._territory_only() and not is_in_creature_territory(creature, target):
            return False
        return True

    def _nest_leash(self):
        raw = self.params.get("nest_leash_radius")
        if raw is None:
            return None
        return float(raw)

    def execute(self, creature) -> bool:
        if not creature.world:
            return False
        colony = getattr(creature, "colony", None)
        if colony is not None and colony.is_carrying:
            return False

        leash = self._nest_leash()
        if is_beyond_nest_leash(creature, leash):
            self._target = None
            return_toward_nest(
                creature,
                speed_multiplier=float(self.params["speed_multiplier"]),
            )
            return False

        enemies = self._enemies()
        if not enemies:
            return False

        target = self._resolve_target(creature, enemies)
        if target is None:
            return False

        pad = float(self.params["contact_padding"])
        reach = contact_range(creature, target, pad)
        dist = move_toward_contact(
            creature, target, self.params["speed_multiplier"], pad
        )
        if dist <= reach:
            try_attack_only(
                creature,
                target,
                attack_power=float(self.params["attack_power"]),
            )
            if not self._trackable(creature, target, enemies):
                self._target = None

        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is not None and colony.is_carrying:
            return 0.0
        if is_beyond_nest_leash(creature, self._nest_leash()):
            return 0.0
        if self._territory_only() and needs_self_feed(creature):
            return 0.0

        enemies = self._enemies()
        if not enemies:
            return 0.0

        foe = self._find_hostile(creature, enemies)
        if foe is None:
            return 0.0

        closeness = closeness_ratio(creature, foe)
        return min(1.0, 0.55 + closeness * 0.45)

    def _resolve_target(self, creature, enemies: tuple[str, ...]):
        if self._trackable(creature, self._target, enemies):
            return self._target
        self._target = self._find_hostile(creature, enemies)
        return self._target


class FleeAction(Action):
    """指定種（兵隊蟻・クモ等）から離れる。"""

    DEFAULT_PARAMS = {
        "threat_species": (),
        "speed_multiplier": 1.5,
        "safe_distance_ratio": 0.55,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._threat = None

    def _threats(self) -> tuple[str, ...]:
        raw = self.params.get("threat_species") or ()
        return tuple(raw)

    def execute(self, creature) -> bool:
        threats = self._threats()
        if not threats or not creature.world:
            return False

        update_flee_latch(creature, threats)
        if not is_flee_latch_active(creature):
            return False

        threat = self._resolve_threat(creature, threats)
        if threat is None:
            return False

        move_away_from(
            creature,
            threat,
            speed_multiplier=float(self.params["speed_multiplier"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        threats = self._threats()
        if not threats:
            return 0.0

        update_flee_latch(creature, threats)
        if is_flee_latch_active(creature):
            return 1.0

        threat = find_nearest_flee_threat_among(
            creature, threats, exclude=creature
        )
        if threat is None:
            return 0.0

        closeness = closeness_ratio(creature, threat)
        return min(1.0, 0.7 + closeness * 0.3)

    def _resolve_threat(self, creature, threats: tuple[str, ...]):
        from src.utils.creature_helpers import is_flee_threat, is_in_vision

        if (
            self._threat is not None
            and is_flee_threat(creature, self._threat, threats)
            and is_in_vision(creature, self._threat)
        ):
            return self._threat
        self._threat = find_nearest_flee_threat_among(
            creature, threats, exclude=creature
        )
        return self._threat


class HuntAction(Action):
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
        return _hunt_prey_species(self.params)

    def _territory_only(self) -> bool:
        return bool(self.params.get("territory_only"))

    def _find_prey(self, creature, species: tuple[str, ...]):
        if self._territory_only():
            return find_nearest_edible_in_territory_among(
                creature, species, exclude=creature
            )
        return find_nearest_edible_among(creature, species, exclude=creature)

    def _trackable_prey(self, creature, target, species: tuple[str, ...]) -> bool:
        if not is_trackable_prey(creature, target, species):
            return False
        if self._territory_only() and not is_in_creature_territory(creature, target):
            return False
        return True

    def _nest_leash(self):
        raw = self.params.get("nest_leash_radius")
        if raw is None:
            return None
        return float(raw)

    def is_completed(self) -> bool:
        return self.completed

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            return False
        colony = creature.colony
        if colony.is_carrying:
            self.completed = True
            return False

        leash = self._nest_leash()
        if is_beyond_nest_leash(creature, leash):
            self._target = None
            return_toward_nest(
                creature,
                speed_multiplier=float(self.params["speed_multiplier"]),
            )
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
        if self._trackable_prey(creature, self._target, species):
            return self._target
        self._target = self._find_prey(creature, species)
        return self._target


class ScavengeCarriedAction(Action):
    """飢餓時: 運搬中チャンクをその場で食べる（巣へ持ち帰らない）。"""

    DEFAULT_PARAMS = {
        "bite_gain": 1.35,
    }

    def execute(self, creature) -> bool:
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying:
            return False

        consume_carried_biomass(
            creature,
            bite_gain=float(self.params["bite_gain"]),
        )
        if not colony.is_carrying:
            return False
        if not needs_self_feed(creature):
            release_carried_carcass(creature)
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying or not needs_self_feed(creature):
            return 0.0
        return 0.85


class ReturnToNestAction(Action):
    """運搬中の死骸を巣へ持ち帰り、貯蔵にする（飢餓時は行わない）。"""

    DEFAULT_PARAMS = {
        "speed_multiplier": 1.1,
        "deposit_radius": 30.0,
        "base_max_carry": 50.0,
    }

    def execute(self, creature) -> bool:
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying or not creature.world:
            return False
        if needs_self_feed(creature):
            return False

        ns = creature.world.nest_system
        if ns.get_creature_nest(creature) is None:
            return False

        deposit_radius = float(self.params["deposit_radius"])
        if ns.is_at_nest(creature, deposit_radius):
            ns.deposit_carried(creature)
            return False

        tx, ty = ns.nest_target_xy(creature)
        dist = move_toward_point(
            creature,
            tx,
            ty,
            float(self.params["speed_multiplier"]),
        )
        if dist <= deposit_radius:
            ns.deposit_carried(creature)

        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying:
            return 0.0
        if needs_self_feed(creature) or not creature.world:
            return 0.0

        ns = creature.world.nest_system
        if ns.get_creature_nest(creature) is None:
            return 0.0

        tx, ty = ns.nest_target_xy(creature)
        dist = distance_to_point(creature, tx, ty)
        vision = max(creature.get_current_vision(), 1.0)
        closeness = max(0.0, min(1.0, 1.0 - dist / vision))
        return 0.85 + closeness * 0.15


class FeedAtNestAction(Action):
    """巣で satiety_full_above まで食事。飢餓時は巣へ向かい、途中の死骸も食べる。"""

    DEFAULT_PARAMS = {
        "bite_gain": 1.15,
        "max_take_ratio": 0.14,
        "feed_radius": 36.0,
        "approach_speed_multiplier": 0.95,
        "min_usable_food_ratio": 0.01,
        "min_usable_satiety_gain": 1.0,
        "scavenge_species": None,
        "scavenge_contact_padding": 10.0,
        "approach_when_hungry": False,
    }

    def _has_usable_food(self, creature) -> bool:
        return nest_has_usable_food(
            creature,
            min_food_ratio=float(self.params["min_usable_food_ratio"]),
            min_satiety_gain=float(self.params["min_usable_satiety_gain"]),
        )

    def _scavenge_species(self) -> tuple[str, ...] | None:
        raw = self.params.get("scavenge_species")
        if not raw:
            return None
        return tuple(raw)

    def _try_scavenge_on_path(self, creature) -> bool:
        if not needs_self_feed(creature):
            return False
        species = self._scavenge_species()
        if species is None:
            return False
        carcass = find_nearest_field_carcass_among(
            creature, species, exclude=creature
        )
        if carcass is None:
            return False
        pad = float(self.params["scavenge_contact_padding"])
        reach = contact_range(creature, carcass, pad)
        dist = move_toward(
            creature,
            carcass,
            float(self.params.get("approach_speed_multiplier", 0.95)),
        )
        if dist <= reach * 1.05:
            consume_carcass(
                creature,
                carcass,
                bite_gain=float(self.params["bite_gain"]),
            )
        # 死骸へ向かったティックは巣接近と併用しない（逆向きで移動が相殺される）
        return True

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            return False
        if creature.colony.is_carrying:
            return False
        if not needs_nest_feed(creature):
            return False

        if self._try_scavenge_on_path(creature):
            return False

        ns = creature.world.nest_system
        if ns.get_creature_nest(creature) is None:
            return False
        tx, ty = ns.nest_target_xy(creature)

        feed_radius = float(self.params["feed_radius"])
        if not ns.is_at_nest(creature, feed_radius):
            should_approach = needs_self_feed(creature) and (
                self._has_usable_food(creature)
                or bool(self.params.get("approach_when_hungry"))
            )
            if should_approach:
                move_toward_point(
                    creature,
                    tx,
                    ty,
                    float(self.params.get("approach_speed_multiplier", 0.95)),
                )
            return False

        if not self._has_usable_food(creature):
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
        if not needs_nest_feed(creature):
            return 0.0

        ns = creature.world.nest_system
        nest = ns.get_creature_nest(creature)
        if nest is None:
            return 0.0

        usable = self._has_usable_food(creature)
        feed_radius = float(self.params["feed_radius"])
        at_nest = ns.is_at_nest(creature, feed_radius)

        if at_nest and usable:
            fill = nest.food_ratio
            base = 0.55 + fill * 0.45
            return min(1.0, base + (0.25 if needs_self_feed(creature) else 0.0))

        if needs_self_feed(creature) and usable:
            dist = ns.distance_to_nest(creature)
            vision = max(creature.get_current_vision(), 1.0)
            closeness = max(0.0, min(1.0, 1.0 - dist / vision))
            return min(1.0, 0.45 + closeness * 0.55)

        if needs_self_feed(creature) and bool(self.params.get("approach_when_hungry")):
            dist = ns.distance_to_nest(creature)
            vision = max(creature.get_current_vision(), 1.0)
            closeness = max(0.0, min(1.0, 1.0 - dist / vision))
            return min(0.85, 0.4 + closeness * 0.45)

        return 0.0


class NestPatrolAction(Action):
    """巣の周辺を巡回（コロニーの結束・観察用の拠点行動）。"""

    DEFAULT_PARAMS = {
        "angle_range": 40,
        "speed_multiplier": 0.75,
        "patrol_radius": 130.0,
        "nest_pull_strength": 0.55,
        "guard_mode": False,
        "return_speed_multiplier": 1.15,
    }

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            wander_step(
                creature,
                self.params["angle_range"],
                self.params["speed_multiplier"],
            )
            return False

        ns = creature.world.nest_system
        if ns.get_creature_nest(creature) is None:
            wander_step(
                creature,
                self.params["angle_range"],
                self.params["speed_multiplier"],
            )
            return False

        from src.utils.position_helpers import entity_xy

        cx, cy = entity_xy(creature)
        tx, ty = ns.nest_target_xy(creature)
        dist = math.hypot(tx - cx, ty - cy)
        patrol_r = float(self.params["patrol_radius"])
        hungry = needs_self_feed(creature)
        guard = bool(self.params.get("guard_mode"))

        if dist > patrol_r * 1.05 or (hungry and guard and dist > patrol_r * 0.75):
            pull = min(0.95, float(self.params["nest_pull_strength"]) + 0.25)
            if hungry and guard:
                pull = 0.95
            to_nest = math.degrees(math.atan2(ty - cy, tx - cx)) % 360
            creature.wander_angle = (
                creature.wander_angle * (1.0 - pull) + to_nest * pull
            ) % 360
            speed = float(
                self.params.get("return_speed_multiplier", self.params["speed_multiplier"])
            )
            angle = self.params["angle_range"] * (0.25 if hungry and guard else 0.35)
            wander_step(creature, angle, speed)
        else:
            angle = self.params["angle_range"] * (0.5 if hungry and guard else 1.0)
            speed = self.params["speed_multiplier"] * (0.7 if hungry and guard else 1.0)
            wander_step(creature, angle, speed)
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or colony.is_carrying or not creature.world:
            return 0.0

        if needs_self_feed(creature):
            if not bool(self.params.get("guard_mode")):
                return 0.0
            dist = creature.world.nest_system.distance_to_nest(creature)
            patrol_r = float(self.params["patrol_radius"])
            if dist > patrol_r * 1.05:
                return 0.96
            return 0.55

        hunger = hunger_ratio(creature)
        nest = creature.world.nest_system.get_creature_nest(creature)
        if nest is None:
            return 0.2

        dist = creature.world.nest_system.distance_to_nest(creature)
        patrol_r = float(self.params["patrol_radius"])
        guard = bool(self.params.get("guard_mode"))

        if guard and dist > patrol_r * 1.05:
            return 0.98
        if guard and dist > patrol_r * 0.88:
            return 0.88

        if dist <= patrol_r:
            members = creature.world.nest_system.member_count(
                nest.id, creature.species.name
            )
            social = min(0.25, (members - 1) * 0.08)
            base = 0.55 if guard else 0.35
            return base + social + (1.0 - hunger) * 0.2
        return 0.15 if not guard else 0.25


class ReproductionAction(Action):
    """繁殖系アクションの基底。卵生・交配などはサブクラスで spawn 戦略を差し替える。"""

    def _blocked_by_population_cap(self, creature) -> bool:
        return is_at_population_cap(creature)

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
        if self._blocked_by_population_cap(creature):
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


class SpawnWorkerAction(ReproductionAction):
    """巣の食料備蓄を消費して働きアリ（同種）を1匹生成する。"""

    DEFAULT_PARAMS = {
        "spawn_radius": 40.0,
        "approach_speed_multiplier": 0.9,
        "spawn_cooldown": 900,
    }

    def _colony_cfg(self, creature) -> dict:
        return creature.species.colony_data or {}

    def can_execute(self, creature) -> bool:
        if not creature.alive or not creature.world:
            return False
        if self._blocked_by_population_cap(creature):
            return False
        if getattr(creature, "colony", None) is None:
            return False
        if creature.colony.is_carrying:
            return False
        if creature.repro_cooldown > 0:
            return False
        return creature.world.nest_system.can_spawn_worker(
            creature, self._colony_cfg(creature)
        )

    def execute(self, creature) -> bool:
        if not self.can_execute(creature):
            return False

        ns = creature.world.nest_system
        spawn_radius = float(self.params["spawn_radius"])

        if not ns.is_at_nest(creature, spawn_radius):
            if ns.get_creature_nest(creature) is None:
                return False
            tx, ty = ns.nest_target_xy(creature)
            move_toward_point(
                creature,
                tx,
                ty,
                float(self.params["approach_speed_multiplier"]),
            )
            return False

        worker = ns.spawn_worker(creature, self._colony_cfg(creature))
        if worker is None:
            return False

        self._register_offspring(creature, worker)
        creature.set_repro_cooldown(int(self.params["spawn_cooldown"]))
        self.completed = True
        return True

    def calculate_utility(self, creature) -> float:
        if not self.can_execute(creature):
            return 0.0
        if needs_self_feed(creature):
            return 0.0

        ns = creature.world.nest_system
        nest = ns.get_creature_nest(creature)
        if nest is None:
            return 0.0

        cfg = self._colony_cfg(creature)
        cost = float(cfg.get("spawn_food_cost", 1))
        reserve = float(cfg.get("min_food_reserve", 0))
        max_workers = max(1, int(cfg.get("max_workers", 1)))
        members = ns.member_count(nest.id, creature.species.name)

        headroom = max(0.0, (max_workers - members) / max_workers)
        surplus = nest.stored_food - reserve - cost
        denom = max(1.0, nest.max_food - reserve - cost)
        food_factor = max(0.0, min(1.0, surplus / denom))

        at_nest = ns.is_at_nest(creature, float(self.params["spawn_radius"]))
        proximity = 1.0 if at_nest else 0.35

        return min(1.0, headroom * (0.35 + food_factor * 0.65) * proximity)
