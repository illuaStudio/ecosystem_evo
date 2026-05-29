import math
import random

from src.ai.actions.base import Action
from src.utils.creature_helpers import (
    current_size,
    is_at_population_cap,
    move_toward_point,
    needs_self_feed,
    satiety_ratio,
)
from src.utils.position_helpers import entity_xy


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
