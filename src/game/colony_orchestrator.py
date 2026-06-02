"""ゲーム層: 勢力コロニー（colony_site / access）の進行・経済・敗北。"""
from __future__ import annotations

import math
import random
from typing import TYPE_CHECKING

from src.game.colony_config import (
    get_access_deposit_cost,
    get_max_access_points,
    get_min_access_spacing,
    get_min_storage_reserve,
    resolve_affiliation_runtime_cfg as _resolve_affiliation_runtime_cfg,
)
from src.game.colony_compound import ColonyCompoundRuntime
from src.sim.utils.creature_helpers import (
    is_point_in_affiliation_territory,
)
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.field_effect_cache import invalidate_field_effect_cache
from src.sim.utils.world_object_helpers import (
    affiliation_stored_mass,
    get_affiliation_root,
    get_compound_root,
    get_creature_affiliation_root,
    owner_species_for_affiliation,
)

if TYPE_CHECKING:
    from src.sim.systems.world import World

HOLE_DESTROY_HP = 1.0


def resolve_affiliation_id(species_name: str, cfg: dict | None = None) -> str:
    from src.sim.utils.territory_helpers import resolve_affiliation_id as _resolve

    return _resolve(species_name, cfg or {})


def resolve_affiliation_runtime_cfg(world, affiliation_id: str, cfg: dict | None = None) -> dict:
    return _resolve_affiliation_runtime_cfg(world, affiliation_id, cfg or {})


def is_affiliation_defeated(world, affiliation_id: str) -> bool:
    from src.game.colony_session import get_colony_runtime

    runtime = get_colony_runtime(world)
    if runtime is None:
        return False
    return runtime.is_defeated(str(affiliation_id))


def _resolve_affiliation_id(target) -> str:
    if target is None:
        return ""
    if isinstance(target, str):
        return target
    cid = getattr(target, "affiliation_id", None)
    if cid:
        return str(cid)
    oid = getattr(target, "id", None)
    return str(oid) if oid is not None else ""


class ColonyOrchestrator:
    DEFAULT_JOIN_RADIUS = 200.0
    DEFAULT_DEPOSIT_RADIUS = 30.0
    DEFAULT_SPAWN_SPREAD = 28.0
    DEFAULT_FOOD_LEAK_RATE = 0.0015
    DEFAULT_FOOD_LEAK_RESERVE_RATIO = 0.12
    WORLD_MARGIN = 30.0

    def __init__(self, world: "World") -> None:
        self.world = world
        self._sim_time = 0.0
        self._compound_runtime = ColonyCompoundRuntime(world)

    @property
    def affiliation_roots(self) -> dict[str, object]:
        from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

        return {root.id: root for root in iter_active_affiliation_roots(self.world)}

    def clear_all_affiliation_sites(self) -> None:
        """テスト用: 全 colony_site / colony_access を削除。"""
        ws = self.world.world_object_system
        ws.objects.clear()
        ws._children.clear()

    def create_affiliation_site(
        self,
        x: float,
        y: float,
        species_name: str,
        *,
        affiliation_id: str | None = None,
        max_mass: float = 400.0,
        stored_mass: float = 0.0,
    ):
        cid = str(affiliation_id or species_name)
        self._register_affiliation_site(
            cid,
            float(x),
            float(y),
            max_mass=float(max_mass),
            stored_mass=float(stored_mass),
        )
        return self.get_affiliation_root(cid)

    def assign_creature_on_spawn(self, creature) -> None:
        data = getattr(creature.species, "affiliation_data", None) or {}
        self.assign_creature(creature, data)

    def bootstrap_existing_creatures(self) -> None:
        """World 生成後に orchestrator を付けたとき、既にいる個体へ所属を付与する。"""
        for creature in list(self.world.creatures):
            self.assign_creature_on_spawn(creature)

    def get_affiliation_root(self, affiliation_id: str):
        return get_affiliation_root(self.world, affiliation_id)

    def get_creature_affiliation_root(self, creature):
        return get_creature_affiliation_root(creature)

    def _register_affiliation_site(
        self,
        affiliation_id: str,
        x: float,
        y: float,
        *,
        max_mass: float,
        stored_mass: float,
        with_default_access: bool = True,
    ) -> None:
        from src.sim.utils.affiliation_site_helpers import register_affiliation_site

        register_affiliation_site(
            self.world,
            affiliation_id,
            x,
            y,
            max_mass=max_mass,
            stored_mass=stored_mass,
            with_default_access=with_default_access,
        )

    def iter_affiliation_access(self, affiliation_id: str):
        ws = self.world.world_object_system
        if not ws.has_affiliation_root(affiliation_id):
            return ()
        return ws.iter_access_points(affiliation_id)

    def _iter_affiliation_access_xy(self, affiliation_id: str):
        ws = self.world.world_object_system
        if ws.has_affiliation_root(affiliation_id):
            for child in ws.iter_access_points(affiliation_id):
                yield float(child.x), float(child.y)
            return
        root = get_affiliation_root(self.world, affiliation_id)
        if root is not None:
            yield float(root.x), float(root.y)

    def _affiliation_access_count(self, affiliation_id: str) -> int:
        ws = self.world.world_object_system
        if ws.has_affiliation_root(affiliation_id):
            return ws.count_active_access(affiliation_id)
        return 0

    def _affiliation_access_exhausted(self, affiliation_id: str) -> bool:
        ws = self.world.world_object_system
        if ws.has_affiliation_root(affiliation_id):
            return ws.count_active_access(affiliation_id) == 0
        return True

    def set_affiliation_stored_mass(self, affiliation_id: str, amount: float) -> None:
        amount = max(0.0, float(amount))
        root = get_affiliation_root(self.world, affiliation_id)
        if root is None or root.storage is None:
            return
        cap = float(root.storage.capacity)
        root.storage.stored_mass = min(amount, cap) if cap > 0 else amount

    def affiliation_fill_ratio(self, affiliation_id: str) -> float:
        """備蓄率 0..1 (game 解釈)。defeated や root 不在時は 0。"""
        # Game 層での affiliation 解釈（ISSUE-001 分離）。Sim の affiliation_fill_ratio には依存せず、
        # 中立の get_compound_root + game の defeated 情報を使用。
        if is_affiliation_defeated(self.world, affiliation_id):
            return 0.0
        root = get_compound_root(self.world, affiliation_id)
        if root is None or root.storage is None:
            return 0.0
        cap = float(root.storage.capacity)
        if cap <= 0:
            return 0.0
        return max(0.0, min(1.0, float(root.storage.stored_mass) / cap))

    def _affiliation_settings(self) -> dict:
        from src.game.colony_config import get_affiliation_settings

        return get_affiliation_settings(self.world)

    def add_hole(self, affiliation_id: str, x: float, y: float) -> None:
        x, y = self._clamp_to_world(float(x), float(y))
        cs = self.world.compound_system
        root = get_affiliation_root(self.world, affiliation_id)
        if root is None:
            self._register_affiliation_site(
                affiliation_id, x, y, max_mass=400.0, stored_mass=0.0, with_default_access=False
            )
        if cs.find_access_at(affiliation_id, x, y) is None:
            cs.add_access_point(affiliation_id, x, y)
        invalidate_field_effect_cache(self.world)

    def damage_access(
        self,
        access,
        affiliation_id: str,
        amount: float,
        *,
        attacker_affiliation_id: str,
    ) -> float:
        from src.sim.utils.affiliation_group_helpers import (
            is_affiliation_defeated as is_affiliation_defeated,
            is_rival_affiliation as is_rival_affiliation,
        )

        if access is None or amount <= 0 or not affiliation_id:
            return 0.0
        if str(access.parent_id or "") != str(affiliation_id):
            return 0.0
        if is_affiliation_defeated(self.world, affiliation_id):
            return 0.0
        if not is_rival_affiliation(self.world, attacker_affiliation_id, affiliation_id):
            return 0.0

        root = get_affiliation_root(self.world, affiliation_id)
        on_all_removed = None
        if root is not None and root.is_affiliation_compound:
            on_all_removed = self.defeat_affiliation

        return self.world.compound_system.damage_access(
            access,
            affiliation_id,
            float(amount),
            on_all_access_removed=on_all_removed,
        )

    def defeat_affiliation(self, affiliation_id: str) -> None:
        if not affiliation_id:
            return
        from src.game.colony_session import get_colony_runtime
        from src.game.emitters import emit_affiliation_defeated

        runtime = get_colony_runtime(self.world)
        if runtime is None or runtime.is_defeated(affiliation_id):
            return

        self.world.compound_system.clear_access_points(affiliation_id)

        from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered

        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        for creature in self.world.creatures:
            if get_creature_affiliation_id(creature) != affiliation_id:
                continue
            from src.sim.utils.inventory_helpers import clear_inventory_for_kind

            clear_inventory_for_kind(creature)
            if is_creature_sheltered(creature):
                creature.become_corpse(cause="defeat")
                clear_creature_shelter(creature)
                from src.game.shelter_helpers import _restore_mind_after_shelter
                _restore_mind_after_shelter(creature)

        message = f"勢力 {affiliation_id} が敗北しました"
        runtime.mark_defeated(affiliation_id, message)
        # Also mark on World for neutral access from sim layer (no checker hook)
        if hasattr(self.world, "mark_affiliation_defeated"):
            try:
                self.world.mark_affiliation_defeated(affiliation_id)
            except Exception:
                pass
        emit_affiliation_defeated(self.world, affiliation_id, message)

    def can_place_hole(self, affiliation_id, x: float, y: float) -> tuple[bool, str]:
        affiliation_id = _resolve_affiliation_id(affiliation_id)
        if not affiliation_id or get_affiliation_root(self.world, affiliation_id) is None:
            return False, "巣が選択されていません"

        cfg = self._affiliation_settings()
        max_access = get_max_access_points(cfg)
        if self._affiliation_access_count(affiliation_id) >= max_access:
            return False, f"接続点上限 ({max_access} 個)"

        x, y = self._clamp_to_world(float(x), float(y))
        if not is_point_in_affiliation_territory(self.world, affiliation_id, x, y):
            return False, "既存テリトリー外です"

        from src.sim.utils.affiliation_group_helpers import is_point_in_rival_territory

        if is_point_in_rival_territory(self.world, affiliation_id, x, y):
            return False, "敵テリトリーと重なります"

        min_spacing = get_min_access_spacing(cfg)
        for ax, ay in self._iter_affiliation_access_xy(affiliation_id):
            if math.hypot(ax - x, ay - y) < min_spacing:
                return False, f"既存の接続点に近すぎます (要 {min_spacing:.0f}px 以上)"

        cost = get_access_deposit_cost(cfg)
        reserve = get_min_storage_reserve(self.world)
        needed = reserve + cost
        stored = affiliation_stored_mass(self.world, affiliation_id)
        if stored < needed:
            return (
                False,
                f"食料不足 (要 {needed:.0f}, 現在 {stored:.0f})",
            )

        return True, ""

    def try_place_hole(self, affiliation_id, x: float, y: float) -> tuple[bool, str]:
        affiliation_id = _resolve_affiliation_id(affiliation_id)
        ok, reason = self.can_place_hole(affiliation_id, x, y)
        if not ok:
            return False, reason

        cost = get_access_deposit_cost(self._affiliation_settings())
        root = get_affiliation_root(self.world, affiliation_id)
        if root is not None and root.storage is not None:
            root.storage.stored_mass = max(0.0, root.storage.stored_mass - cost)
        self.add_hole(affiliation_id, x, y)
        return True, "接続点を設置しました"

    def affiliation_target_xy(self, creature) -> tuple[float, float]:
        from src.sim.utils.affiliation_site_helpers import affiliation_target_xy

        return affiliation_target_xy(creature)

    def find_affiliation_at(self, x: float, y: float, pick_radius: float = 36.0) -> str | None:
        from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

        best_id = None
        min_dist = float("inf")
        for root in iter_active_affiliation_roots(self.world):
            from src.sim.utils.affiliation_site_helpers import nearest_access_xy

            tx, ty = nearest_access_xy(self.world, root.id, x, y)
            dist = math.hypot(tx - x, ty - y)
            if dist <= pick_radius and dist < min_dist:
                min_dist = dist
                best_id = root.id
        return best_id

    def find_affiliation_site_at(self, x: float, y: float, pick_radius: float = 36.0):
        affiliation_id = self.find_affiliation_at(x, y, pick_radius)
        if affiliation_id is None:
            return None
        return get_affiliation_root(self.world, affiliation_id)

    def find_nearest_affiliation_root(
        self,
        x: float,
        y: float,
        affiliation_id: str,
        max_dist: float,
    ):
        root = get_affiliation_root(self.world, affiliation_id)
        if root is None:
            return None
        dist = math.hypot(root.x - x, root.y - y)
        if dist <= max_dist:
            return root
        return None

    def spawn_position(self, species_name: str, affiliation_cfg: dict | None = None) -> tuple[float, float]:
        from src.sim.utils.spawn_placement import (
            SpawnAnchor,
            SpawnPlacementOptions,
            SpawnPlacementResolver,
        )

        cfg = affiliation_cfg or {}
        affiliation_id = resolve_affiliation_id(species_name, cfg)
        runtime_cfg = resolve_affiliation_runtime_cfg(self.world, affiliation_id, cfg)
        spread = float(runtime_cfg["spawn_spread"])
        resolver = SpawnPlacementResolver(self.world)
        anchor = SpawnAnchor(type="affiliation_site", affiliation_id=affiliation_id, spread=spread)
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

    def assign_creature(self, creature, affiliation_cfg: dict | None = None) -> None:
        """個体の所属（affiliation_id）を解決して付与する。

        affiliation_id は colony_site の root id として扱う。
        """
        affiliation = getattr(creature, "affiliation", None)
        if affiliation is None:
            return

        cfg = affiliation_cfg or {}
        species_name = creature.species.name
        single_affiliation = cfg.get("single_affiliation", cfg.get("single_affiliation", True))
        affiliation_id = resolve_affiliation_id(species_name, cfg)
        join_species = cfg.get("join_species")

        from src.sim.utils.affiliation_group_helpers import is_affiliation_defeated as is_affiliation_defeated

        if affiliation_id and is_affiliation_defeated(self.world, affiliation_id):
            affiliation.affiliation_id = str(affiliation_id)
            return

        ws = self.world.world_object_system
        if single_affiliation and ws.has_affiliation_root(affiliation_id):
            affiliation.affiliation_id = str(affiliation_id)
            return

        if not single_affiliation:
            cx, cy = entity_xy(creature)
            join_radius = float(cfg.get("join_radius", self.DEFAULT_JOIN_RADIUS))
            root = self.find_nearest_affiliation_root(cx, cy, affiliation_id, join_radius)
            if root is not None:
                affiliation.affiliation_id = str(affiliation_id)
                return

        if join_species is not None:
            affiliation.affiliation_id = str(affiliation_id) if affiliation_id else None
            return

        cx, cy = entity_xy(creature)
        runtime_cfg = resolve_affiliation_runtime_cfg(self.world, affiliation_id, cfg)
        self._register_affiliation_site(
            affiliation_id,
            cx,
            cy,
            max_mass=float(runtime_cfg["max_mass"]),
            stored_mass=float(runtime_cfg["initial_mass"]),
        )
        affiliation.affiliation_id = str(affiliation_id)

    def update(self, dt: float = 1.0) -> None:
        dt = float(dt)
        self._sim_time += dt
        from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

        for root in iter_active_affiliation_roots(self.world):
            if root.storage is None:
                continue
            runtime_cfg = resolve_affiliation_runtime_cfg(self.world, root.id, {})
            if root.storage.stored_mass > 0:
                self._leak_food_storage(root.storage, runtime_cfg, dt)

    def _leak_food_storage(self, storage, affiliation_cfg: dict, dt: float) -> None:
        if not affiliation_cfg:
            return
        leak_per_tick = float(affiliation_cfg["storage_leak_per_tick"])
        reserve_ratio = float(affiliation_cfg["storage_leak_reserve_ratio"])
        if leak_per_tick <= 0:
            return
        reserve = storage.capacity * reserve_ratio
        leakable = max(0.0, storage.stored_mass - reserve)
        if leakable <= 0:
            return
        storage.stored_mass = max(reserve, storage.stored_mass - leak_per_tick * dt)

    def try_consume_food(self, affiliation_id, amount: float) -> bool:
        affiliation_id = _resolve_affiliation_id(affiliation_id)
        if not affiliation_id or amount <= 0:
            return False
        root = get_affiliation_root(self.world, affiliation_id)
        if root is None or root.storage is None:
            return False
        if root.storage.stored_mass < amount:
            return False
        root.storage.withdraw(amount)
        return True

    def count_affiliation_members(self, affiliation_id, species_names: list[str]) -> int:
        affiliation_id = _resolve_affiliation_id(affiliation_id)
        if not affiliation_id:
            return 0
        if not species_names:
            return self.total_member_count(affiliation_id)
        names = set(species_names)
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            if c.species.name not in names:
                continue
            aff = getattr(c, "affiliation", None)
            if aff is not None and str(getattr(aff, "affiliation_id", "") or "") == affiliation_id:
                count += 1
        return count

    def distance_to_affiliation_site(self, creature) -> float:
        from src.sim.utils.affiliation_site_helpers import distance_to_affiliation_site

        return distance_to_affiliation_site(creature)

    def is_at_affiliation_site(self, creature, deposit_radius: float) -> bool:
        from src.sim.utils.affiliation_site_helpers import is_at_affiliation_site

        return is_at_affiliation_site(creature, deposit_radius)

    def deposit_space(self, affiliation_id: str) -> float:
        return self._compound_runtime.deposit_space(affiliation_id)

    def deposit_carried(self, creature) -> float:
        return self._compound_runtime.deposit_carried(creature)

    def feed_creature(
        self,
        creature,
        *,
        bite_gain: float = 1.2,
        feed_per_tick: float = 11.0,
    ) -> float:
        return self._compound_runtime.feed_creature(
            creature,
            bite_gain=bite_gain,
            feed_per_tick=feed_per_tick,
        )

    def member_count(self, affiliation_id, species_name: str) -> int:
        return self.count_affiliation_members(_resolve_affiliation_id(affiliation_id), [species_name])

    def total_member_count(self, affiliation_id) -> int:
        affiliation_id = _resolve_affiliation_id(affiliation_id)
        if not affiliation_id:
            return 0
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            aff = getattr(c, "affiliation", None)
            if aff is not None and str(getattr(aff, "affiliation_id", "") or "") == affiliation_id:
                count += 1
        return count

    def owner_species_for_affiliation(self, affiliation_id: str) -> str:
        return self._compound_runtime.owner_species(affiliation_id)
