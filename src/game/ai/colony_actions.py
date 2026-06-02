"""ゲーム層: 勢力拠点（colony_site）向け AI 行動。"""
from __future__ import annotations

import math

from src.game.colony_session import get_colony_orchestrator
from src.sim.ai.action_config import get_mind_action_param
from src.sim.ai.actions.base import Action
from src.sim.shelter.state import is_creature_sheltered
from src.sim.utils.creature_helpers import (
    consume_carried_for_kind,
    contact_range,
    distance_to_point,
    hunger_ratio,
    is_hungry,
    move_toward,
    move_toward_point,
    needs_self_feed,
    wander_step,
)
from src.sim.utils.inventory_helpers import inventory_is_loaded
from src.game.affiliation_feed import (
    affiliation_has_usable_storage,
    get_affiliation_feed_config,
    needs_affiliation_feed,
    sync_nutrition_recovery_for_affiliation_feed,
)
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.world_object_helpers import (
    creature_has_affiliation_target,
    get_creature_compound_parent_ids,
    parent_stored_mass,
)


def _orch(creature):
    return get_colony_orchestrator(creature.world)


class ScavengeCarriedAction(Action):
    """回復中かつ運搬中: 持ち帰り予定のバイオマスをその場で1口食べる。"""

    def execute(self, creature) -> bool:
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None or not inventory_is_loaded(creature):
            return False
        consume_carried_for_kind(
            creature,
            bite_gain=get_mind_action_param(creature, "HuntAction", "bite_gain"),
        )
        return False

    def calculate_utility(self, creature) -> float:
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None or not inventory_is_loaded(creature) or not needs_self_feed(creature):
            return 0.0
        return 0.85


class ReturnToAffiliationDepositAction(Action):
    """運搬中の死骸を拠点へ持ち帰り、貯蔵にする（飢餓時は行わない）。"""

    @classmethod
    def continues_while_carrying(cls) -> bool:
        return True

    DEFAULT_PARAMS = {
        "speed_multiplier": 1.1,
        "deposit_radius": 30.0,
        "base_max_carry": 50.0,
    }

    def execute(self, creature) -> bool:
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None or not inventory_is_loaded(creature) or not creature.world:
            return False
        if needs_self_feed(creature):
            return False
        colony = _orch(creature)
        if not creature_has_affiliation_target(creature):
            return False
        deposit_radius = float(self.params["deposit_radius"])
        if colony.is_at_affiliation_site(creature, deposit_radius):
            colony.deposit_carried(creature)
            return False
        tx, ty = colony.affiliation_target_xy(creature)
        dist = move_toward_point(
            creature, tx, ty, float(self.params["speed_multiplier"])
        )
        if dist <= deposit_radius:
            colony.deposit_carried(creature)
        return False

    def calculate_utility(self, creature) -> float:
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None or not inventory_is_loaded(creature):
            return 0.0
        if needs_self_feed(creature) or not creature.world:
            return 0.0
        colony = _orch(creature)
        if not creature_has_affiliation_target(creature):
            return 0.0
        tx, ty = colony.affiliation_target_xy(creature)
        dist = distance_to_point(creature, tx, ty)
        vision = max(creature.get_current_vision(), 1.0)
        closeness = max(0.0, min(1.0, 1.0 - dist / vision))
        return 0.85 + closeness * 0.15


class FeedAtAffiliationSiteAction(Action):
    """拠点備蓄で satiety_full_above まで食事。"""

    DEFAULT_PARAMS = {
        "feed_radius": 36.0,
        "approach_speed_multiplier": 0.95,
        "scavenge_species": None,
        "scavenge_contact_padding": 10.0,
        "approach_when_hungry": False,
    }

    def _has_usable_food(self, creature) -> bool:
        return affiliation_has_usable_storage(creature)

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
        from src.sim.combat.pickup_target import find_nearest_field_pickup_among
        from src.sim.utils.field_pickup_helpers import is_field_pickup, pickup_radius
        from src.sim.utils.loot_helpers import consume_loot_biomass

        pickup = find_nearest_field_pickup_among(creature, species)
        if pickup is None or not is_field_pickup(pickup):
            return False
        pad = float(self.params["scavenge_contact_padding"])
        reach = pickup_radius(pickup) + pad
        dist = move_toward_point(
            creature,
            pickup.x,
            pickup.y,
            float(self.params.get("approach_speed_multiplier", 0.95)),
        )
        if dist <= reach * 1.05:
            feed_cfg = get_affiliation_feed_config(creature)
            consume_loot_biomass(creature, pickup, bite_gain=feed_cfg["bite_gain"])
        return True

    def _wants_affiliation_feed(self, creature) -> bool:
        return needs_self_feed(creature) or is_hungry(creature)

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "affiliation", None) is None:
            return False
        if inventory_is_loaded(creature):
            return False
        colony = _orch(creature)
        if not creature_has_affiliation_target(creature):
            return False
        feed_radius = float(self.params["feed_radius"])
        if is_creature_sheltered(creature):
            if not self._wants_affiliation_feed(creature):
                return False
            if not needs_affiliation_feed(creature) or not self._has_usable_food(creature):
                return False
            if not colony.is_at_affiliation_site(creature, feed_radius):
                return False
            feed_cfg = get_affiliation_feed_config(creature)
            colony.feed_creature(
                creature,
                bite_gain=feed_cfg["bite_gain"],
                feed_per_tick=feed_cfg["feed_per_tick"],
            )
            sync_nutrition_recovery_for_affiliation_feed(creature)
            return False
        if not self._wants_affiliation_feed(creature):
            return False
        if not needs_affiliation_feed(creature):
            return False
        if self._try_scavenge_on_path(creature):
            return False
        tx, ty = colony.affiliation_target_xy(creature)
        if not colony.is_at_affiliation_site(creature, feed_radius):
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
        feed_cfg = get_affiliation_feed_config(creature)
        colony.feed_creature(
            creature,
            bite_gain=feed_cfg["bite_gain"],
            feed_per_tick=feed_cfg["feed_per_tick"],
        )
        sync_nutrition_recovery_for_affiliation_feed(creature)
        return False

    def calculate_utility(self, creature) -> float:
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None or inventory_is_loaded(creature) or not creature.world:
            return 0.0
        colony = _orch(creature)
        if not creature_has_affiliation_target(creature):
            return 0.0
        usable = self._has_usable_food(creature)
        feed_radius = float(self.params["feed_radius"])
        at_site = colony.is_at_affiliation_site(creature, feed_radius)
        if is_creature_sheltered(creature):
            if not self._wants_affiliation_feed(creature):
                return 0.0
            if not needs_affiliation_feed(creature) or not usable or not at_site:
                return 0.0
            return 1.0
        if not self._wants_affiliation_feed(creature):
            return 0.0
        if not needs_affiliation_feed(creature):
            return 0.0
        if at_site and usable:
            from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

            cid = get_creature_affiliation_id(creature)
            if cid:
                fill = colony.affiliation_fill_ratio(cid)
            else:
                ws = creature.world.world_object_system
                parent_ids = get_creature_compound_parent_ids(creature)
                root = ws.get(parent_ids[0]) if parent_ids else None
                cap = float(root.storage.capacity) if root and root.storage else 1.0
                fill = min(1.0, parent_stored_mass(creature) / max(cap, 1.0))
            base = 0.55 + fill * 0.45
            return min(1.0, base + (0.25 if needs_self_feed(creature) else 0.0))
        if needs_self_feed(creature) and usable:
            dist = colony.distance_to_affiliation_site(creature)
            vision = max(creature.get_current_vision(), 1.0)
            closeness = max(0.0, min(1.0, 1.0 - dist / vision))
            return min(1.0, 0.45 + closeness * 0.55)
        if needs_self_feed(creature) and bool(self.params.get("approach_when_hungry")):
            dist = colony.distance_to_affiliation_site(creature)
            vision = max(creature.get_current_vision(), 1.0)
            closeness = max(0.0, min(1.0, 1.0 - dist / vision))
            return min(0.85, 0.4 + closeness * 0.45)
        return 0.0


class AffiliationPatrolAction(Action):
    """拠点周辺を巡回。"""

    DEFAULT_PARAMS = {
        "angle_range": 40,
        "speed_multiplier": 0.75,
        "patrol_radius": 130.0,
        "nest_pull_strength": 0.55,
        "guard_mode": False,
        "return_speed_multiplier": 1.15,
    }

    def execute(self, creature) -> bool:
        if not creature.world or getattr(creature, "affiliation", None) is None:
            wander_step(creature, self.params["angle_range"], self.params["speed_multiplier"])
            return False
        colony = _orch(creature)
        if not creature_has_affiliation_target(creature):
            wander_step(creature, self.params["angle_range"], self.params["speed_multiplier"])
            return False
        cx, cy = entity_xy(creature)
        tx, ty = colony.affiliation_target_xy(creature)
        dist = math.hypot(tx - cx, ty - cy)
        patrol_r = float(self.params["patrol_radius"])
        hungry = needs_self_feed(creature)
        guard = bool(self.params.get("guard_mode"))
        pull_strength = float(self.params["nest_pull_strength"])
        if dist > patrol_r * 1.05 or (hungry and guard and dist > patrol_r * 0.75):
            pull = min(0.95, pull_strength + 0.25)
            if hungry and guard:
                pull = 0.95
            to_site = math.degrees(math.atan2(ty - cy, tx - cx)) % 360
            creature.wander_angle = (
                creature.wander_angle * (1.0 - pull) + to_site * pull
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
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None or inventory_is_loaded(creature) or not creature.world:
            return 0.0
        colony = _orch(creature)
        if needs_self_feed(creature):
            if not bool(self.params.get("guard_mode")):
                return 0.0
            dist = colony.distance_to_affiliation_site(creature)
            patrol_r = float(self.params["patrol_radius"])
            if dist > patrol_r * 1.05:
                return 0.96
            return 0.55
        hunger = hunger_ratio(creature)
        if not creature_has_affiliation_target(creature):
            return 0.2
        dist = colony.distance_to_affiliation_site(creature)
        patrol_r = float(self.params["patrol_radius"])
        guard = bool(self.params.get("guard_mode"))
        if guard and dist > patrol_r * 1.05:
            return 0.98
        if guard and dist > patrol_r * 0.88:
            return 0.88
        if dist <= patrol_r:
            from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

            cid = get_creature_affiliation_id(creature) or ""
            members = colony.member_count(cid, creature.species.name)
            social = min(0.25, (members - 1) * 0.08)
            base = 0.55 if guard else 0.35
            return base + social + (1.0 - hunger) * 0.2
        return 0.15 if not guard else 0.25


# 種 JSON の既存 action 名との互換
ReturnToNestAction = ReturnToAffiliationDepositAction
FeedAtNestAction = FeedAtAffiliationSiteAction
NestPatrolAction = AffiliationPatrolAction
