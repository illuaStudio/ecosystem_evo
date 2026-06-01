"""ゲーム層: コロニー繁殖（女王産卵など）。"""
from __future__ import annotations

import random

from src.game.colony_session import get_colony_orchestrator
from src.sim.ai.actions.reproduction import ReproductionAction
from src.sim.utils.creature_helpers import (
    count_alive_by_species,
    get_species_population_cap,
    is_species_at_population_cap,
    move_toward_point,
    needs_self_feed,
)
from src.sim.utils.position_helpers import entity_xy


def _orch(world):
    return get_colony_orchestrator(world)


class AffiliationReproduceAction(ReproductionAction):
    """拠点備蓄を消費してコロニー子個体を生成する（女王など個体の AI 判断）。"""

    DEFAULT_PARAMS = {
        "offspring": [],
        "food_cost": 55,
        "max_affiliation_members": 10,
        "member_species": [],
        "spawn_cooldown": 900,
        "spawn_radius": 40.0,
        "approach_speed_multiplier": 0.9,
    }

    def _min_storage_reserve(self, creature) -> float:
        world = getattr(creature, "world", None)
        if world is None:
            raise RuntimeError("AffiliationReproduceAction: world が未設定です")
        from src.game.colony_config import get_min_storage_reserve

        return get_min_storage_reserve(world)

    def _member_species(self) -> list[str]:
        return [str(s) for s in self.params["member_species"]]

    def _pick_offspring_species(self, world, affiliation_id: str) -> str | None:
        entries = self.params.get("offspring") or []
        owner = (
            _orch(world).owner_species_for_affiliation(affiliation_id) if world else affiliation_id
        )
        if not entries:
            return owner

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
            return owner
        return str(sp)

    def _creature_affiliation_id(self, creature) -> str | None:
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        return get_creature_affiliation_id(creature)

    def reproduction_readiness(self, creature) -> tuple[bool, str]:
        if not creature.alive or creature.world is None:
            return False, "無効"
        if getattr(creature, "affiliation", None) is None:
            return False, "所属なし"

        affiliation_id = self._creature_affiliation_id(creature)
        if not affiliation_id:
            return False, "拠点なし"

        cost = float(self.params["food_cost"])
        if cost <= 0:
            return False, "繁殖未設定"

        max_members = int(self.params["max_affiliation_members"])
        if max_members <= 0:
            return False, "繁殖未設定"

        offspring_species = self._pick_offspring_species(creature.world, affiliation_id)
        if offspring_species and is_species_at_population_cap(
            creature.world, offspring_species
        ):
            alive = count_alive_by_species(creature.world, offspring_species)
            cap = get_species_population_cap(creature.world, offspring_species)
            return False, f"種族上限 ({alive}/{cap})"

        member_species = self._member_species()
        ns = _orch(creature.world)
        if member_species:
            members = ns.count_affiliation_members(affiliation_id, member_species)
        else:
            members = ns.total_member_count(affiliation_id)

        if members >= max_members:
            return False, f"個体数上限 ({members}/{max_members})"

        reserve = self._min_storage_reserve(creature)
        needed = reserve + cost
        from src.sim.utils.world_object_helpers import affiliation_stored_mass

        stored = affiliation_stored_mass(creature.world, affiliation_id)
        if stored < needed:
            return (
                False,
                f"備蓄不足 (要 {needed:.0f}, 現在 {stored:.0f})",
            )

        return True, f"繁殖可能 ({members}/{max_members})"

    def can_execute(self, creature) -> bool:
        if not creature.alive or not creature.world:
            return False
        if self._blocked_by_population_cap(creature):
            return False
        if getattr(creature, "affiliation", None) is None:
            return False
        from src.sim.utils.inventory_helpers import inventory_is_loaded

        if inventory_is_loaded(creature):
            return False
        if creature.repro_cooldown > 0:
            return False

        ok, _ = self.reproduction_readiness(creature)
        return ok

    def _spawn_offspring(self, creature):
        if not self.can_execute(creature):
            return None

        ns = _orch(creature.world)
        affiliation_id = self._creature_affiliation_id(creature)
        if not affiliation_id:
            return None

        cost = float(self.params["food_cost"])
        if not ns.try_consume_food(affiliation_id, cost):
            return None

        from src.config import config
        from src.sim.entities.creature_factory import CreatureFactory

        offspring_species = self._pick_offspring_species(creature.world, affiliation_id)
        if not offspring_species:
            from src.sim.utils.world_object_helpers import get_affiliation_root

            root = get_affiliation_root(creature.world, affiliation_id)
            if root is not None and root.storage is not None:
                root.storage.deposit(cost)
            return None

        data = config.get_species(offspring_species) or {}
        offspring_cfg = data.get("affiliation") or {}
        x, y = ns.spawn_position(offspring_species, offspring_cfg)
        return CreatureFactory.create(offspring_species, world=creature.world, x=x, y=y)

    def execute(self, creature) -> bool:
        if not self.can_execute(creature):
            world = creature.world
            ns = _orch(world) if world else None
            affiliation_id = self._creature_affiliation_id(creature)
            spawn_radius = float(self.params["spawn_radius"])

            if ns is not None and affiliation_id and not ns.is_at_affiliation_site(
                creature, spawn_radius
            ):
                tx, ty = ns.affiliation_target_xy(creature)
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

        ns = _orch(creature.world)
        affiliation_id = self._creature_affiliation_id(creature)
        if not affiliation_id:
            return 0.0

        cost = float(self.params["food_cost"])
        reserve = self._min_storage_reserve(creature)
        max_members = max(1, int(self.params["max_affiliation_members"]))
        member_species = self._member_species()
        if member_species:
            members = ns.count_affiliation_members(affiliation_id, member_species)
        else:
            members = ns.total_member_count(affiliation_id)

        headroom = max(0.0, (max_members - members) / max_members)
        from src.sim.utils.world_object_helpers import (
            affiliation_capacity,
            affiliation_stored_mass,
        )

        stored = affiliation_stored_mass(creature.world, affiliation_id)
        cap = affiliation_capacity(creature.world, affiliation_id)
        surplus = stored - reserve - cost
        denom = max(1.0, cap - reserve - cost)
        food_factor = max(0.0, min(1.0, surplus / denom))

        at_site = ns.is_at_affiliation_site(creature, float(self.params["spawn_radius"]))
        proximity = 1.0 if at_site else 0.35

        return min(1.0, headroom * (0.35 + food_factor * 0.65) * proximity)


class SpawnWorkerAction(AffiliationReproduceAction):
    """後方互換: offspring 未指定時は拠点 owner_species と同種を生成。"""
