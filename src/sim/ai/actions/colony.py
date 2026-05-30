import math

from src.sim.ai.actions.base import Action
from src.sim.shelter.state import is_creature_sheltered
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.sim.utils.creature_helpers import (
    consume_carcass,
    consume_carried_biomass,
    contact_range,
    distance_to_point,
    find_nearest_field_carcass_among,
    hunger_ratio,
    is_hungry,
    move_toward,
    move_toward_point,
    needs_nest_feed,
    needs_self_feed,
    nest_has_usable_food,
    wander_step,
)
from src.sim.utils.position_helpers import entity_xy


class ScavengeCarriedAction(Action):
    """回復中かつ運搬中: 持ち帰り予定のバイオマスをその場で1口食べる。残りは巣へ運ぶ。"""

    DEFAULT_PARAMS = {
        "bite_gain": 1.35,
    }

    def execute(self, creature) -> bool:
        colony = getattr(creature, "colony", None)
        if colony is None or not inventory_is_loaded(creature):
            return False

        consume_carried_biomass(
            creature,
            bite_gain=float(self.params["bite_gain"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or not inventory_is_loaded(creature) or not needs_self_feed(creature):
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
        if colony is None or not inventory_is_loaded(creature) or not creature.world:
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
        if colony is None or not inventory_is_loaded(creature):
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
        "feed_per_tick": 11.0,
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

    def _wants_nest_feed(self, creature) -> bool:
        """巣食事を能動的に選ぶ条件（回復モードまたは飢餓）。満腹閾値付近の代謝ドリフトでは選ばない。"""
        return needs_self_feed(creature) or is_hungry(creature)

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "colony", None) is None:
            return False
        if inventory_is_loaded(creature):
            return False

        ns = creature.world.nest_system
        if ns.get_creature_nest(creature) is None:
            return False

        feed_radius = float(self.params["feed_radius"])

        if is_creature_sheltered(creature):
            if not needs_nest_feed(creature) or not self._has_usable_food(creature):
                return False
            if not ns.is_at_nest(creature, feed_radius):
                return False
            ns.feed_creature(
                creature,
                bite_gain=float(self.params["bite_gain"]),
                feed_per_tick=float(self.params["feed_per_tick"]),
            )
            return False

        if not self._wants_nest_feed(creature):
            return False
        if not needs_nest_feed(creature):
            return False

        if self._try_scavenge_on_path(creature):
            return False

        tx, ty = ns.nest_target_xy(creature)

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
            feed_per_tick=float(self.params["feed_per_tick"]),
        )
        return False

    def calculate_utility(self, creature) -> float:
        colony = getattr(creature, "colony", None)
        if colony is None or inventory_is_loaded(creature) or not creature.world:
            return 0.0

        ns = creature.world.nest_system
        nest = ns.get_creature_nest(creature)
        if nest is None:
            return 0.0

        usable = self._has_usable_food(creature)
        feed_radius = float(self.params["feed_radius"])
        at_nest = ns.is_at_nest(creature, feed_radius)

        if is_creature_sheltered(creature):
            if not needs_nest_feed(creature) or not usable or not at_nest:
                return 0.0
            return 1.0

        if not self._wants_nest_feed(creature):
            return 0.0
        if not needs_nest_feed(creature):
            return 0.0

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
        if colony is None or inventory_is_loaded(creature) or not creature.world:
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
