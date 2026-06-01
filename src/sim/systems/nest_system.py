# nest_system.py
"""コロニー拠点のランタイム管理（colony_site / colony_access 経由）。"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from src.sim.utils.colony_config_helpers import (
    get_min_food_reserve,
    get_access_food_cost,
    get_max_access_points,
    get_min_access_spacing,
    resolve_colony_runtime_cfg,
)
from src.sim.utils.creature_helpers import (
    is_point_in_colony_territory,
    resolve_colony_id,
)
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.field_effect_cache import invalidate_field_effect_cache
from src.sim.utils.world_object_helpers import (
    colony_food_ratio,
    colony_stored_food,
    get_colony_root,
    get_creature_colony_root,
    owner_species_for_colony,
)

if TYPE_CHECKING:
    from src.sim.systems.world import World

HOLE_DESTROY_HP = 1.0


def _resolve_colony_id(target) -> str:
    if target is None:
        return ""
    if isinstance(target, str):
        return target
    cid = getattr(target, "colony_id", None)
    if cid:
        return str(cid)
    oid = getattr(target, "id", None)
    return str(oid) if oid is not None else ""


class NestSystem:
    DEFAULT_JOIN_RADIUS = 200.0
    DEFAULT_DEPOSIT_RADIUS = 30.0
    DEFAULT_SPAWN_SPREAD = 28.0
    DEFAULT_FOOD_LEAK_RATE = 0.0015
    DEFAULT_FOOD_LEAK_RESERVE_RATIO = 0.12
    WORLD_MARGIN = 30.0

    def __init__(self, world: "World") -> None:
        self.world = world
        self._sim_time = 0.0

    @property
    def nests(self) -> dict[str, object]:
        """後方互換: 非敗北 colony_site を colony_id → root で列挙。"""
        from src.sim.utils.world_object_helpers import iter_active_colony_roots

        return {root.id: root for root in iter_active_colony_roots(self.world)}

    def clear_all_colony_sites(self) -> None:
        """テスト用: 全 colony_site / colony_access を削除。"""
        ws = self.world.world_object_system
        ws.objects.clear()
        ws._children.clear()

    def bootstrap_from_world_objects(self) -> None:
        """colony_site は WorldObjectSystem 側で既に読み込み済み。"""

    def create_nest(
        self,
        x: float,
        y: float,
        species_name: str,
        *,
        colony_id: str | None = None,
        max_food: float = 400.0,
        stored_food: float = 0.0,
    ):
        """後方互換: colony_site + 既定 access を登録。"""
        cid = str(colony_id or species_name)
        self._register_colony_site(
            cid,
            float(x),
            float(y),
            max_food=float(max_food),
            stored_food=float(stored_food),
        )
        return self.get_colony_root(cid)

    def get_colony_root(self, colony_id: str):
        return get_colony_root(self.world, colony_id)

    def get_creature_colony_root(self, creature):
        return get_creature_colony_root(creature)

    def get_colony_nest(self, colony_id: str):
        """後方互換: colony_site 親 WorldObject。"""
        return self.get_colony_root(colony_id)

    def get_creature_nest(self, creature):
        """後方互換: 個体の colony_site 親 WorldObject。"""
        return self.get_creature_colony_root(creature)

    def _register_colony_site(
        self,
        colony_id: str,
        x: float,
        y: float,
        *,
        max_food: float,
        stored_food: float,
        with_default_access: bool = True,
    ) -> None:
        ws = self.world.world_object_system
        if not ws.has_colony_root(colony_id):
            ws.ensure_colony_site(
                colony_id,
                x,
                y,
                max_food=max_food,
                stored_food=stored_food,
            )
            if with_default_access and ws.find_access_at(colony_id, x, y) is None:
                ws.add_access_point(colony_id, x, y)
        invalidate_field_effect_cache(self.world)
        zone_system = getattr(self.world, "zone_system", None)
        if zone_system is not None:
            root = ws.get(colony_id)
            if root is not None:
                zone_system.sync_colony_clearing(colony_id, root.x, root.y)

    def iter_colony_access(self, colony_id: str):
        ws = self.world.world_object_system
        if not ws.has_colony_root(colony_id):
            return ()
        return ws.iter_access_points(colony_id)

    def _iter_colony_access_xy(self, colony_id: str):
        ws = self.world.world_object_system
        if ws.has_colony_root(colony_id):
            for child in ws.iter_access_points(colony_id):
                yield float(child.x), float(child.y)
            return
        root = get_colony_root(self.world, colony_id)
        if root is not None:
            yield float(root.x), float(root.y)

    def _colony_access_count(self, colony_id: str) -> int:
        ws = self.world.world_object_system
        if ws.has_colony_root(colony_id):
            return ws.count_active_access(colony_id)
        return 0

    def _colony_access_exhausted(self, colony_id: str) -> bool:
        ws = self.world.world_object_system
        if ws.has_colony_root(colony_id):
            return ws.count_active_access(colony_id) == 0
        return True

    def set_colony_stored_food(self, colony_id: str, amount: float) -> None:
        amount = max(0.0, float(amount))
        root = get_colony_root(self.world, colony_id)
        if root is None or root.storage is None:
            return
        cap = float(root.storage.max_food)
        root.storage.stored_food = min(amount, cap) if cap > 0 else amount

    def colony_food_ratio(self, colony_id: str) -> float:
        return colony_food_ratio(self.world, colony_id)

    def nest_food_ratio(self, colony_id: str) -> float:
        """後方互換。"""
        return self.colony_food_ratio(colony_id)

    def _colony_settings(self) -> dict:
        return getattr(self.world, "colony_settings", {}) or {}

    def add_hole(self, colony_id: str, x: float, y: float) -> None:
        x, y = self._clamp_to_world(float(x), float(y))
        cs = self.world.compound_system
        root = get_colony_root(self.world, colony_id)
        if root is None:
            self._register_colony_site(
                colony_id, x, y, max_food=400.0, stored_food=0.0, with_default_access=False
            )
        if cs.find_access_at(colony_id, x, y) is None:
            cs.add_access_point(colony_id, x, y)
        invalidate_field_effect_cache(self.world)

    def damage_access(
        self,
        access,
        colony_id: str,
        amount: float,
        *,
        attacker_colony_id: str,
    ) -> float:
        from src.sim.utils.colony_helpers import is_colony_defeated, is_rival_colony

        if access is None or amount <= 0 or not colony_id:
            return 0.0
        if str(access.parent_id or "") != str(colony_id):
            return 0.0
        if is_colony_defeated(self.world, colony_id):
            return 0.0
        if not is_rival_colony(self.world, attacker_colony_id, colony_id):
            return 0.0

        root = get_colony_root(self.world, colony_id)
        on_all_removed = None
        if root is not None and root.is_colony_compound:
            on_all_removed = self.defeat_colony

        return self.world.compound_system.damage_access(
            access,
            colony_id,
            float(amount),
            on_all_access_removed=on_all_removed,
        )

    def defeat_colony(self, colony_id: str) -> None:
        if not colony_id:
            return
        defeated = getattr(self.world, "defeated_colonies", None)
        if defeated is None:
            self.world.defeated_colonies = set()
        if colony_id in self.world.defeated_colonies:
            return

        self.world.compound_system.clear_access_points(colony_id)

        self.world.defeated_colonies.add(colony_id)

        from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered

        for creature in self.world.creatures:
            colony = getattr(creature, "colony", None)
            if colony is None or colony.colony_id != colony_id:
                continue
            colony.defeated = True
            from src.sim.utils.inventory_helpers import clear_inventory_biomass

            clear_inventory_biomass(creature)
            if is_creature_sheltered(creature):
                creature.become_corpse(cause="defeat")
                clear_creature_shelter(creature)

        message = f"勢力 {colony_id} が敗北しました"
        self.world.last_defeat_message = message
        from src.sim.emitters import emit_colony_defeated

        emit_colony_defeated(self.world, colony_id, message)

    def can_place_hole(self, colony_id, x: float, y: float) -> tuple[bool, str]:
        colony_id = _resolve_colony_id(colony_id)
        if not colony_id or get_colony_root(self.world, colony_id) is None:
            return False, "巣が選択されていません"

        cfg = self._colony_settings()
        max_access = get_max_access_points(cfg)
        if self._colony_access_count(colony_id) >= max_access:
            return False, f"接続点上限 ({max_access} 個)"

        x, y = self._clamp_to_world(float(x), float(y))
        if not is_point_in_colony_territory(self.world, colony_id, x, y):
            return False, "既存テリトリー外です"

        from src.sim.utils.colony_helpers import is_point_in_rival_territory

        if is_point_in_rival_territory(self.world, colony_id, x, y):
            return False, "敵テリトリーと重なります"

        min_spacing = get_min_access_spacing(cfg)
        for ax, ay in self._iter_colony_access_xy(colony_id):
            if math.hypot(ax - x, ay - y) < min_spacing:
                return False, f"既存の接続点に近すぎます (要 {min_spacing:.0f}px 以上)"

        cost = get_access_food_cost(cfg)
        reserve = get_min_food_reserve(self.world)
        needed = reserve + cost
        stored = colony_stored_food(self.world, colony_id)
        if stored < needed:
            return (
                False,
                f"食料不足 (要 {needed:.0f}, 現在 {stored:.0f})",
            )

        return True, ""

    def try_place_hole(self, colony_id, x: float, y: float) -> tuple[bool, str]:
        colony_id = _resolve_colony_id(colony_id)
        ok, reason = self.can_place_hole(colony_id, x, y)
        if not ok:
            return False, reason

        cost = get_access_food_cost(self._colony_settings())
        root = get_colony_root(self.world, colony_id)
        if root is not None and root.storage is not None:
            root.storage.stored_food = max(0.0, root.storage.stored_food - cost)
        self.add_hole(colony_id, x, y)
        return True, "接続点を設置しました"

    def _nearest_access_xy(self, colony_id: str, x: float, y: float) -> tuple[float, float]:
        best = None
        best_d = float("inf")
        for ax, ay in self._iter_colony_access_xy(colony_id):
            d = (ax - x) ** 2 + (ay - y) ** 2
            if d < best_d:
                best_d = d
                best = (ax, ay)
        if best is not None:
            return best
        root = get_colony_root(self.world, colony_id)
        if root is not None:
            return float(root.x), float(root.y)
        return x, y

    def nest_target_xy(self, creature) -> tuple[float, float]:
        from src.sim.utils.world_object_helpers import (
            get_creature_nest_parent_ids,
            resolve_deposit_target,
        )

        if get_creature_nest_parent_ids(creature):
            _parent, access = resolve_deposit_target(creature)
            if access is not None:
                return float(access.x), float(access.y)
            if _parent is not None:
                return float(_parent.x), float(_parent.y)

        from src.sim.utils.colony_helpers import get_creature_colony_id

        colony_id = get_creature_colony_id(creature)
        if not colony_id:
            return entity_xy(creature)
        cx, cy = entity_xy(creature)
        return self._nearest_access_xy(colony_id, cx, cy)

    def find_colony_at(self, x: float, y: float, pick_radius: float = 36.0) -> str | None:
        from src.sim.utils.world_object_helpers import iter_active_colony_roots

        best_id = None
        min_dist = float("inf")
        for root in iter_active_colony_roots(self.world):
            tx, ty = self._nearest_access_xy(root.id, x, y)
            dist = math.hypot(tx - x, ty - y)
            if dist <= pick_radius and dist < min_dist:
                min_dist = dist
                best_id = root.id
        return best_id

    def find_nest_at(self, x: float, y: float, pick_radius: float = 36.0):
        """後方互換: colony_site 親 WorldObject。"""
        colony_id = self.find_colony_at(x, y, pick_radius)
        if colony_id is None:
            return None
        return get_colony_root(self.world, colony_id)

    def find_nearest_colony_root(
        self,
        x: float,
        y: float,
        colony_id: str,
        max_dist: float,
    ):
        root = get_colony_root(self.world, colony_id)
        if root is None:
            return None
        dist = math.hypot(root.x - x, root.y - y)
        if dist <= max_dist:
            return root
        return None

    def find_nearest_nest(self, x: float, y: float, colony_id: str, max_dist: float):
        """後方互換。"""
        return self.find_nearest_colony_root(x, y, colony_id, max_dist)

    def spawn_position(self, species_name: str, colony_cfg: dict | None = None) -> tuple[float, float]:
        from src.sim.utils.spawn_placement import (
            SpawnAnchor,
            SpawnPlacementOptions,
            SpawnPlacementResolver,
        )

        cfg = colony_cfg or {}
        colony_id = resolve_colony_id(species_name, cfg)
        runtime_cfg = resolve_colony_runtime_cfg(self.world, colony_id, cfg)
        spread = float(runtime_cfg["spawn_spread"])
        resolver = SpawnPlacementResolver(self.world)
        anchor = SpawnAnchor(type="nest", colony_id=colony_id, spread=spread)
        pos = resolver.pick(
            anchor,
            SpawnPlacementOptions(
                respect_zones=False,
                use_biome_weight=False,
                attempts=8,
            ),
        )
        if pos is not None:
            return pos
        ax, ay = self._nest_anchor(runtime_cfg)
        return self._offset_near(ax, ay, spread)

    def _nest_anchor(self, runtime_cfg: dict) -> tuple[float, float]:
        if "nest_x" in runtime_cfg and "nest_y" in runtime_cfg:
            return float(runtime_cfg["nest_x"]), float(runtime_cfg["nest_y"])
        return self.world.width * 0.5, self.world.height * 0.5

    def _offset_near(self, x: float, y: float, spread: float) -> tuple[float, float]:
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, spread)
        sx = x + math.cos(angle) * dist
        sy = y + math.sin(angle) * dist
        return self._clamp_to_world(sx, sy)

    def _clamp_to_world(self, x: float, y: float) -> tuple[float, float]:
        m = self.WORLD_MARGIN
        x = max(m, min(self.world.width - m, x))
        y = max(m, min(self.world.height - m, y))
        return x, y

    def assign_creature(self, creature, colony_cfg: dict | None = None) -> None:
        colony = getattr(creature, "colony", None)
        if colony is None:
            return

        cfg = colony_cfg or {}
        species_name = creature.species.name
        single_colony = cfg.get("single_colony", True)
        colony_id = resolve_colony_id(species_name, cfg)
        join_species = cfg.get("join_species")

        from src.sim.utils.colony_helpers import is_colony_defeated

        if colony_id and is_colony_defeated(self.world, colony_id):
            colony.defeated = True
            colony.colony_id = colony_id
            return

        ws = self.world.world_object_system
        if single_colony and ws.has_colony_root(colony_id):
            colony.colony_id = colony_id
            return

        if not single_colony:
            cx, cy = entity_xy(creature)
            join_radius = float(cfg.get("join_radius", self.DEFAULT_JOIN_RADIUS))
            root = self.find_nearest_colony_root(cx, cy, colony_id, join_radius)
            if root is not None:
                colony.colony_id = colony_id
                return

        if join_species is not None:
            return

        cx, cy = entity_xy(creature)
        runtime_cfg = resolve_colony_runtime_cfg(self.world, colony_id, cfg)
        self._register_colony_site(
            colony_id,
            cx,
            cy,
            max_food=float(runtime_cfg["max_food"]),
            stored_food=float(runtime_cfg["initial_stored_food"]),
        )
        colony.colony_id = colony_id

    def update(self, dt: float = 1.0) -> None:
        dt = float(dt)
        self._sim_time += dt
        from src.sim.utils.world_object_helpers import iter_active_colony_roots

        for root in iter_active_colony_roots(self.world):
            if root.storage is None:
                continue
            runtime_cfg = resolve_colony_runtime_cfg(self.world, root.id, {})
            if root.storage.stored_food > 0:
                self._leak_food_storage(root.storage, runtime_cfg, dt)

    def _leak_food_storage(self, storage, colony_cfg: dict, dt: float) -> None:
        if not colony_cfg:
            return
        leak_per_tick = float(colony_cfg["food_leak_per_tick"])
        reserve_ratio = float(colony_cfg["food_leak_reserve_ratio"])
        if leak_per_tick <= 0:
            return
        reserve = storage.max_food * reserve_ratio
        leakable = max(0.0, storage.stored_food - reserve)
        if leakable <= 0:
            return
        storage.stored_food = max(reserve, storage.stored_food - leak_per_tick * dt)

    def try_consume_food(self, colony_id, amount: float) -> bool:
        colony_id = _resolve_colony_id(colony_id)
        if not colony_id or amount <= 0:
            return False
        root = get_colony_root(self.world, colony_id)
        if root is None or root.storage is None:
            return False
        if root.storage.stored_food < amount:
            return False
        root.storage.withdraw(amount)
        return True

    def count_colony_members(self, colony_id, species_names: list[str]) -> int:
        colony_id = _resolve_colony_id(colony_id)
        if not colony_id:
            return 0
        if not species_names:
            return self.total_member_count(colony_id)
        names = set(species_names)
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            if c.species.name not in names:
                continue
            colony = getattr(c, "colony", None)
            if colony is not None and colony.colony_id == colony_id:
                count += 1
        return count

    def distance_to_nest(self, creature) -> float:
        cx, cy = entity_xy(creature)
        tx, ty = self.nest_target_xy(creature)
        return math.hypot(tx - cx, ty - cy)

    def is_at_nest(self, creature, deposit_radius: float) -> bool:
        return self.distance_to_nest(creature) <= deposit_radius

    def deposit_space(self, colony_id: str) -> float:
        root = get_colony_root(self.world, colony_id)
        if root is None or root.storage is None:
            return 0.0
        return max(0.0, root.storage.max_food - root.storage.stored_food)

    def deposit_carried(self, creature) -> float:
        from src.sim.utils.inventory_helpers import clear_inventory_biomass, inventory_is_loaded
        from src.sim.utils.world_object_helpers import (
            deposit_carried_to_parent,
            get_creature_nest_parent_ids,
        )
        from src.sim.utils.colony_helpers import get_creature_colony_id

        if not inventory_is_loaded(creature):
            return 0.0

        if get_creature_nest_parent_ids(creature):
            return deposit_carried_to_parent(creature)

        colony_id = get_creature_colony_id(creature)
        if not colony_id:
            return 0.0

        amount = clear_inventory_biomass(creature)
        if amount <= 0:
            return 0.0

        root = get_colony_root(self.world, colony_id)
        if root is None or root.storage is None:
            return 0.0
        return root.storage.deposit(amount)

    def feed_creature(
        self,
        creature,
        *,
        bite_gain: float = 1.2,
        feed_per_tick: float = 11.0,
    ) -> float:
        from src.sim.utils.world_object_helpers import (
            feed_creature_from_parent,
            get_creature_nest_parent_ids,
        )
        from src.sim.utils.colony_helpers import get_creature_colony_id

        if get_creature_nest_parent_ids(creature):
            return feed_creature_from_parent(
                creature,
                bite_gain=bite_gain,
                feed_per_tick=feed_per_tick,
            )

        colony_id = get_creature_colony_id(creature)
        root = get_colony_root(self.world, colony_id) if colony_id else None
        if root is None or root.storage is None:
            return 0.0
        if root.storage.stored_food <= 0:
            return 0.0

        max_sat = float(creature.max_satiety)
        if float(creature.satiety) >= max_sat:
            return 0.0

        take = min(root.storage.stored_food, float(feed_per_tick))
        if take <= 0:
            return 0.0

        root.storage.withdraw(take)
        creature.satiety = min(
            max_sat,
            creature.satiety + take * float(bite_gain),
        )
        return take

    def member_count(self, colony_id, species_name: str) -> int:
        return self.count_colony_members(_resolve_colony_id(colony_id), [species_name])

    def total_member_count(self, colony_id) -> int:
        colony_id = _resolve_colony_id(colony_id)
        if not colony_id:
            return 0
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            colony = getattr(c, "colony", None)
            if colony is not None and colony.colony_id == colony_id:
                count += 1
        return count

    def owner_species_for_colony(self, colony_id: str) -> str:
        return owner_species_for_colony(self.world, colony_id)
