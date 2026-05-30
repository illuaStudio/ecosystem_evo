import math
import random

from src.sim.ai.actions.base import Action
from src.sim.utils.creature_helpers import (
    count_alive_by_species,
    current_size,
    is_at_population_cap,
    is_species_at_population_cap,
    move_toward_point,
    needs_self_feed,
    satiety_ratio,
)
from src.sim.utils.position_helpers import entity_xy


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

    def _register_offspring(self, parent, offspring, *, spawn_source: str = "reproduction") -> None:
        if parent.world:
            parent.world.add_creature(
                offspring, spawn_source=spawn_source, parent=parent
            )


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

        from src.sim.entities.creature_factory import CreatureFactory

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
        self._register_offspring(creature, offspring, spawn_source="split")

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


class ColonyReproduceAction(ReproductionAction):
    """巣の食料備蓄を消費してコロニー子個体を生成する（女王など個体の AI 判断）。"""

    DEFAULT_PARAMS = {
        "offspring": [],
        "food_cost": 55,
        "max_colony_members": 10,
        "member_species": [],
        "spawn_cooldown": 900,
        "spawn_radius": 40.0,
        "approach_speed_multiplier": 0.9,
    }

    def _min_food_reserve(self, creature) -> float:
        """最低備蓄は world.json colony.min_food_reserve（巣穴設置と共通）。"""
        world = getattr(creature, "world", None)
        if world is not None:
            from src.sim.utils.colony_config_helpers import get_min_food_reserve

            return get_min_food_reserve(world)
        return 72.0

    def _member_species(self) -> list[str]:
        explicit = self.params.get("member_species") or []
        if explicit:
            return [str(s) for s in explicit]
        names: list[str] = []
        for entry in self.params.get("offspring") or []:
            sp = entry.get("species")
            if sp and sp not in ("__owner__", "") and sp not in names:
                names.append(str(sp))
        return names

    def _pick_offspring_species(self, nest) -> str | None:
        entries = self.params.get("offspring") or []
        if not entries:
            return nest.owner_species if nest is not None else None

        total = sum(float(e.get("weight", 1.0)) for e in entries)
        if total <= 0:
            return None

        r = random.uniform(0, total)
        acc = 0.0
        chosen = entries[-1]
        for entry in entries:
            acc += float(entry.get("weight", 1.0))
            if r <= acc:
                chosen = entry
                break

        sp = chosen.get("species")
        if sp in (None, "", "__owner__"):
            return nest.owner_species if nest is not None else None
        return str(sp)

    def _creature_nest(self, creature):
        if creature.world is None:
            return None
        return creature.world.nest_system.get_creature_nest(creature)

    def reproduction_readiness(self, creature) -> tuple[bool, str]:
        """繁殖可否と理由（UI・テスト用）。"""
        if not creature.alive or creature.world is None:
            return False, "無効"
        if getattr(creature, "colony", None) is None:
            return False, "コロニー未所属"

        nest = self._creature_nest(creature)
        if nest is None:
            return False, "巣なし"

        cost = float(self.params["food_cost"])
        if cost <= 0:
            return False, "繁殖未設定"

        max_members = int(self.params["max_colony_members"])
        if max_members <= 0:
            return False, "繁殖未設定"

        offspring_species = self._pick_offspring_species(nest)
        if offspring_species and is_species_at_population_cap(
            creature.world, offspring_species
        ):
            alive = count_alive_by_species(creature.world, offspring_species)
            from src.sim.utils.creature_helpers import get_species_population_cap

            cap = get_species_population_cap(creature.world, offspring_species)
            return False, f"種族上限 ({alive}/{cap})"

        member_species = self._member_species()
        ns = creature.world.nest_system
        if member_species:
            members = ns.count_colony_members(nest.id, member_species)
        else:
            members = ns.total_member_count(nest.id)

        if members >= max_members:
            return False, f"個体数上限 ({members}/{max_members})"

        reserve = self._min_food_reserve(creature)
        needed = reserve + cost
        if nest.stored_food < needed:
            return (
                False,
                f"備蓄不足 (要 {needed:.0f}, 現在 {nest.stored_food:.0f})",
            )

        return True, f"繁殖可能 ({members}/{max_members})"

    def can_execute(self, creature) -> bool:
        if not creature.alive or not creature.world:
            return False
        if self._blocked_by_population_cap(creature):
            return False
        if getattr(creature, "colony", None) is None:
            return False
        from src.sim.utils.inventory_helpers import inventory_is_loaded

        if inventory_is_loaded(creature):
            return False
        if creature.repro_cooldown > 0:
            return False

        ok, _ = self.reproduction_readiness(creature)
        return ok

    def _spawn_offspring(self, creature):
        """子個体を生成する。失敗時は None。ワールドへの登録は呼び出し側。"""
        if not self.can_execute(creature):
            return None

        ns = creature.world.nest_system
        nest = self._creature_nest(creature)
        if nest is None:
            return None

        cost = float(self.params["food_cost"])
        if not ns.try_consume_food(nest, cost):
            return None

        from src.config import config
        from src.sim.entities.creature_factory import CreatureFactory

        offspring_species = self._pick_offspring_species(nest)
        if not offspring_species:
            nest.stored_food += cost
            return None

        offspring_cfg = config.get_species(offspring_species).get("colony", {})
        x, y = ns.spawn_position(offspring_species, offspring_cfg)
        return CreatureFactory.create(offspring_species, world=creature.world, x=x, y=y)

    def execute(self, creature) -> bool:
        if not self.can_execute(creature):
            ns = creature.world.nest_system if creature.world else None
            nest = self._creature_nest(creature)
            spawn_radius = float(self.params["spawn_radius"])

            if ns is not None and nest is not None and not ns.is_at_nest(
                creature, spawn_radius
            ):
                tx, ty = ns.nest_target_xy(creature)
                move_toward_point(
                    creature,
                    tx,
                    ty,
                    float(self.params["approach_speed_multiplier"]),
                )
            return False

        offspring = self._spawn_offspring(creature)
        if offspring is None:
            return False

        self._register_offspring(creature, offspring)
        creature.set_repro_cooldown(int(self.params["spawn_cooldown"]))
        self.completed = True
        return True

    def calculate_utility(self, creature) -> float:
        if not self.can_execute(creature):
            return 0.0
        if needs_self_feed(creature):
            return 0.0

        ns = creature.world.nest_system
        nest = self._creature_nest(creature)
        if nest is None:
            return 0.0

        cost = float(self.params["food_cost"])
        reserve = self._min_food_reserve(creature)
        max_members = max(1, int(self.params["max_colony_members"]))
        member_species = self._member_species()
        if member_species:
            members = ns.count_colony_members(nest.id, member_species)
        else:
            members = ns.total_member_count(nest.id)

        headroom = max(0.0, (max_members - members) / max_members)
        surplus = nest.stored_food - reserve - cost
        denom = max(1.0, nest.max_food - reserve - cost)
        food_factor = max(0.0, min(1.0, surplus / denom))

        at_nest = ns.is_at_nest(creature, float(self.params["spawn_radius"]))
        proximity = 1.0 if at_nest else 0.35

        return min(1.0, headroom * (0.35 + food_factor * 0.65) * proximity)


class SpawnWorkerAction(ColonyReproduceAction):
    """後方互換: offspring 未指定時は巣 owner_species と同種を生成。"""
