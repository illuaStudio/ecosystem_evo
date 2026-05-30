from src.sim.ai.actions.base import Action
from src.sim.ai.actions.tracking import (
    CreatureTargetMixin,
    NestLeashMixin,
    TerritoryOnlyMixin,
)
from src.sim.combat.target_damage import apply_damage_to_target
from src.sim.combat.target_query import (
    find_nearest_hostile_creature,
    find_nearest_spawn_node,
    is_trackable_hostile_creature,
    is_valid_spawn_node,
    spawn_node_in_range,
    target_closeness,
    target_position,
)
from src.sim.utils.colony_helpers import (
    get_creature_colony_id,
    get_rival_colony_ids,
    is_creature_colony_defeated,
)
from src.sim.utils.creature_helpers import (
    closeness_ratio,
    contact_range,
    expand_faction_species,
    is_beyond_nest_leash,
    move_toward_contact,
    move_toward_point,
    needs_self_feed,
    try_attack_only,
)


class CombatAction(NestLeashMixin, TerritoryOnlyMixin, CreatureTargetMixin, Action):
    """視界内の敵対種を追跡し攻撃のみ（死骸の拾い・食事は行わない）。"""

    DEFAULT_PARAMS = {
        "hostile_species": (),
        "hostile_colony_ids": (),
        "speed_multiplier": 1.4,
        "contact_padding": 8.0,
        "attack_power": 1.3,
        "territory_only": False,
        "nest_leash_radius": None,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target = None

    def _enemies(self, creature=None) -> tuple[str, ...]:
        raw = list(self.params.get("hostile_species") or ())
        colony_ids = self.params.get("hostile_colony_ids") or ()
        if colony_ids and creature is not None and creature.world is not None:
            raw.extend(expand_faction_species(creature.world, colony_ids))
        return tuple(raw)

    def _find_hostile(self, creature, enemies: tuple[str, ...]):
        ref = find_nearest_hostile_creature(
            creature,
            enemies,
            territory_only=self._territory_only(),
            exclude=creature,
        )
        return ref.as_creature() if ref else None

    def _trackable(self, creature, target, enemies: tuple[str, ...]) -> bool:
        return is_trackable_hostile_creature(
            creature,
            target,
            enemies,
            territory_only=self._territory_only(),
        )

    def execute(self, creature) -> bool:
        if not creature.world or is_creature_colony_defeated(creature):
            return False
        colony = getattr(creature, "colony", None)
        from src.sim.utils.inventory_helpers import inventory_is_loaded

        if inventory_is_loaded(creature):
            return False

        if self._abort_if_beyond_nest_leash(creature):
            return False

        enemies = self._enemies(creature)
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
                self._clear_target()

        return False

    def calculate_utility(self, creature) -> float:
        if is_creature_colony_defeated(creature):
            return 0.0
        colony = getattr(creature, "colony", None)
        from src.sim.utils.inventory_helpers import inventory_is_loaded

        if inventory_is_loaded(creature):
            return 0.0
        if is_beyond_nest_leash(creature, self._nest_leash()):
            return 0.0
        if self._territory_only() and needs_self_feed(creature):
            return 0.0

        enemies = self._enemies(creature)
        if not enemies:
            return 0.0

        foe = self._find_hostile(creature, enemies)
        if foe is None:
            return 0.0

        closeness = closeness_ratio(creature, foe)
        return min(1.0, 0.55 + closeness * 0.45)

    def _resolve_target(self, creature, enemies: tuple[str, ...]):
        return self._resolve_creature_target(
            creature,
            find_fn=lambda c: self._find_hostile(c, enemies),
            trackable_fn=lambda c, t: self._trackable(c, t, enemies),
        )


class AttackHoleAction(NestLeashMixin, Action):
    """敵勢力の巣穴を攻撃。

    ignore_territory=False: 自テリ内の敵穴 or 敵テリへの侵攻時のみ。
    ignore_territory=True（先兵）: 視界内の敵穴をどこでも攻撃。
    yield_to_intruders=True かつ防衛時: 自テリ侵入者がいれば utility 0。
    """

    DEFAULT_PARAMS = {
        "hostile_colony_ids": (),
        "speed_multiplier": 1.25,
        "attack_power": 1.15,
        "contact_padding": 14.0,
        "nest_leash_radius": None,
        "max_search_radius": None,
        "ignore_territory": False,
        "yield_to_intruders": True,
    }

    def __init__(self, **params):
        super().__init__(**params)
        self._target_ref = None

    def _hostile_colonies(self, creature) -> tuple[str, ...]:
        raw = list(self.params.get("hostile_colony_ids") or ())
        if not raw and creature is not None and creature.world is not None:
            cid = get_creature_colony_id(creature)
            if cid:
                raw = list(get_rival_colony_ids(creature.world, cid))
        return tuple(raw)

    def _enemy_species(self, creature) -> tuple[str, ...]:
        if creature is None or creature.world is None:
            return ()
        return expand_faction_species(creature.world, self._hostile_colonies(creature))

    def _ignore_territory(self) -> bool:
        return bool(self.params.get("ignore_territory"))

    def _yield_to_intruders(self) -> bool:
        return bool(self.params.get("yield_to_intruders"))

    def _max_search_distance(self, creature) -> float:
        """敵穴を認識できる距離。既定は視界（全マップ把握はしない）。"""
        raw = self.params.get("max_search_radius")
        if raw is not None:
            return float(raw)
        if hasattr(creature, "get_current_vision"):
            return float(creature.get_current_vision())
        return float(creature.traits.get("base_vision", 200))

    def _spawn_filter_kwargs(self, creature) -> dict:
        return {
            "hostile_colony_ids": self._hostile_colonies(creature),
            "unrestricted": self._ignore_territory(),
        }

    def _find_spawn_target(self, creature):
        colonies = self._hostile_colonies(creature)
        if not colonies:
            return None
        return find_nearest_spawn_node(
            creature,
            colonies,
            unrestricted=self._ignore_territory(),
            max_distance=self._max_search_distance(creature),
        )

    def _spawn_target_valid(self, creature, ref) -> bool:
        if ref is None:
            return False
        return is_valid_spawn_node(creature, ref, **self._spawn_filter_kwargs(creature))

    def calculate_utility(self, creature) -> float:
        if is_creature_colony_defeated(creature):
            return 0.0
        if is_beyond_nest_leash(creature, self._nest_leash()):
            return 0.0

        if self._yield_to_intruders():
            enemy_species = self._enemy_species(creature)
            if enemy_species:
                intruder_ref = find_nearest_hostile_creature(
                    creature,
                    enemy_species,
                    territory_only=True,
                    exclude=creature,
                )
                if intruder_ref is not None:
                    return 0.0

        ref = self._find_spawn_target(creature)
        if ref is None:
            return 0.0

        max_d = max(self._max_search_distance(creature), 1.0)
        closeness = target_closeness(creature, ref, max_distance=max_d)
        return min(1.0, 0.4 + closeness * 0.5)

    def execute(self, creature) -> bool:
        if not creature.world or is_creature_colony_defeated(creature):
            return False

        if self._abort_if_beyond_nest_leash(creature):
            return False

        max_d = self._max_search_distance(creature)
        if self._target_ref and not self._spawn_target_valid(creature, self._target_ref):
            self._target_ref = None
        if self._target_ref and not spawn_node_in_range(
            creature, self._target_ref, max_d
        ):
            self._target_ref = None

        ref = self._target_ref if self._target_ref else self._find_spawn_target(creature)
        if ref is None or not self._spawn_target_valid(creature, ref):
            self._target_ref = None
            return False

        self._target_ref = ref
        tx, ty = target_position(ref)

        pad = float(self.params["contact_padding"])
        reach = pad + 12.0
        dist = move_toward_point(
            creature, tx, ty, float(self.params["speed_multiplier"])
        )
        if dist <= reach:
            apply_damage_to_target(
                creature,
                ref,
                float(self.params["attack_power"]),
                attacker_colony_id=get_creature_colony_id(creature) or "",
            )
            if not self._spawn_target_valid(creature, self._target_ref):
                self._target_ref = None
        return False
