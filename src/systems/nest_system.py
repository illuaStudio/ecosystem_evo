# nest_system.py
"""捕食者コロニーの巣を管理する。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.utils.creature_helpers import (
    count_alive_by_species,
    distance_to_point,
    get_species_population_cap,
    is_point_in_nest_territory,
    is_species_at_population_cap,
    resolve_colony_id,
    satiety_feed_target,
    satiety_room_until_feed_target,
)
from src.utils.position_helpers import entity_xy

if TYPE_CHECKING:
    from src.systems.world import World


@dataclass
class NestHole:
    x: float
    y: float


@dataclass
class Nest:
    id: int
    x: float
    y: float
    owner_species: str
    colony_id: str = ""
    stored_food: float = 0.0
    max_food: float = 400.0
    spawn_timer: float = 0.0
    holes: list[NestHole] = field(default_factory=list)

    @property
    def food_ratio(self) -> float:
        if self.max_food <= 0:
            return 0.0
        return max(0.0, min(1.0, self.stored_food / self.max_food))


class NestSystem:
    DEFAULT_JOIN_RADIUS = 200.0
    DEFAULT_DEPOSIT_RADIUS = 30.0
    DEFAULT_SPAWN_SPREAD = 28.0
    DEFAULT_FOOD_LEAK_RATE = 0.0015
    DEFAULT_FOOD_TO_MANA_RATIO = 0.35
    DEFAULT_FOOD_LEAK_RESERVE_RATIO = 0.12
    DEFAULT_SPAWN_INTERVAL_TICKS = 900.0
    WORLD_MARGIN = 30.0

    def __init__(self, world: "World") -> None:
        self.world = world
        self.nests: dict[int, Nest] = {}
        self._next_id = 1

    def create_nest(
        self,
        x: float,
        y: float,
        species_name: str,
        *,
        colony_id: str,
        max_food: float = 400.0,
        stored_food: float = 0.0,
    ) -> Nest:
        cap = float(max_food)
        food = max(0.0, min(float(stored_food), cap))
        nest = Nest(
            id=self._next_id,
            x=float(x),
            y=float(y),
            owner_species=species_name,
            colony_id=str(colony_id),
            stored_food=food,
            max_food=cap,
        )
        # 既定で「巣穴=作成地点」を1つ持つ（巣=備蓄、巣穴=出入口・テリトリー核）。
        nest.holes.append(NestHole(x=float(x), y=float(y)))
        self._next_id += 1
        self.nests[nest.id] = nest
        return nest

    def _colony_settings(self) -> dict:
        return getattr(self.world, "colony_settings", {}) or {}

    def add_hole(self, nest: Nest, x: float, y: float) -> None:
        x, y = self._clamp_to_world(float(x), float(y))
        nest.holes.append(NestHole(x=x, y=y))

    def can_place_hole(self, nest: Nest, x: float, y: float) -> tuple[bool, str]:
        """新規巣穴を置けるか（標準ルール: 自テリトリー内・間隔・上限・食料）。"""
        if nest is None:
            return False, "巣が選択されていません"

        cfg = self._colony_settings()
        max_holes = int(cfg.get("max_holes", 8))
        if len(nest.holes or []) >= max_holes:
            return False, f"巣穴上限 ({max_holes} 個)"

        x, y = self._clamp_to_world(float(x), float(y))
        if not is_point_in_nest_territory(self.world, nest, x, y):
            return False, "既存テリトリー外です"

        min_spacing = float(cfg.get("min_hole_spacing", 120))
        for h in nest.holes or []:
            if math.hypot(h.x - x, h.y - y) < min_spacing:
                return False, f"既存の巣穴に近すぎます (要 {min_spacing:.0f}px 以上)"

        cost = float(cfg.get("hole_food_cost", 250))
        reserve = float(cfg.get("hole_min_food_reserve", 72))
        needed = reserve + cost
        if nest.stored_food < needed:
            return (
                False,
                f"食料不足 (要 {needed:.0f}, 現在 {nest.stored_food:.0f})",
            )

        return True, ""

    def try_place_hole(self, nest: Nest, x: float, y: float) -> tuple[bool, str]:
        """条件を満たせば巣穴を追加し食料を消費する。"""
        ok, reason = self.can_place_hole(nest, x, y)
        if not ok:
            return False, reason

        cost = float(self._colony_settings().get("hole_food_cost", 250))
        nest.stored_food -= cost
        self.add_hole(nest, x, y)
        return True, "巣穴を設置しました"

    def _nearest_hole_xy(self, nest: Nest, x: float, y: float) -> tuple[float, float]:
        if not nest.holes:
            return nest.x, nest.y
        best = None
        best_d = float("inf")
        for h in nest.holes:
            d = (h.x - x) ** 2 + (h.y - y) ** 2
            if d < best_d:
                best_d = d
                best = h
        return best.x, best.y

    def nest_target_xy(self, creature) -> tuple[float, float]:
        """その個体が所属する巣へ向かう座標（最寄り巣穴）。"""
        nest = self.get_creature_nest(creature)
        if nest is None:
            return entity_xy(creature)
        cx, cy = entity_xy(creature)
        return self._nearest_hole_xy(nest, cx, cy)

    def get_nest(self, nest_id: int | None) -> Nest | None:
        if nest_id is None:
            return None
        return self.nests.get(nest_id)

    def find_nest_at(self, x: float, y: float, pick_radius: float = 36.0) -> Nest | None:
        """ワールド座標でクリック可能な最寄り巣を返す。"""
        best = None
        min_dist = float("inf")
        for nest in self.nests.values():
            tx, ty = self._nearest_hole_xy(nest, x, y)
            dist = math.hypot(tx - x, ty - y)
            if dist <= pick_radius and dist < min_dist:
                min_dist = dist
                best = nest
        return best

    def find_nearest_nest(
        self,
        x: float,
        y: float,
        colony_id: str,
        max_dist: float,
    ) -> Nest | None:
        best = None
        min_dist = float("inf")
        for nest in self.nests.values():
            if nest.colony_id != colony_id:
                continue
            dist = ((nest.x - x) ** 2 + (nest.y - y) ** 2) ** 0.5
            if dist <= max_dist and dist < min_dist:
                min_dist = dist
                best = nest
        return best

    def get_colony_nest(self, colony_id: str) -> Nest | None:
        """勢力 ID のコロニー巣を1つ返す。"""
        for nest in self.nests.values():
            if nest.colony_id == colony_id:
                return nest
        return None

    def get_colony_nest_for_creature(
        self, species_name: str, colony_cfg: dict | None = None
    ) -> Nest | None:
        """colony_id / join_species を考慮してコロニー巣を返す。"""
        cid = resolve_colony_id(species_name, colony_cfg)
        return self.get_colony_nest(cid)

    def spawn_position(self, species_name: str, colony_cfg: dict | None = None) -> tuple[float, float]:
        """巣の位置付近にスポーン座標を返す（初期配置・P 追加用）。"""
        cfg = colony_cfg or {}
        spread = float(cfg.get("spawn_spread", self.DEFAULT_SPAWN_SPREAD))
        colony_id = resolve_colony_id(species_name, cfg)
        nest = self.get_colony_nest(colony_id)
        if nest is not None:
            hole = random.choice(nest.holes) if nest.holes else None
            hx, hy = (hole.x, hole.y) if hole is not None else (nest.x, nest.y)
            return self._offset_near(hx, hy, spread)
        ax, ay = self._nest_anchor(cfg)
        return self._offset_near(ax, ay, spread)

    def _nest_anchor(self, colony_cfg: dict) -> tuple[float, float]:
        if "nest_x" in colony_cfg and "nest_y" in colony_cfg:
            return float(colony_cfg["nest_x"]), float(colony_cfg["nest_y"])
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
        """コロニー有効種を巣に割り当て。

        single_colony=true（既定）: 同種の既存巣があれば距離に関係なく合流。
        なければ新設。将来の複数コロニー用に join_radius による近傍合流も残す。
        """
        colony = getattr(creature, "colony", None)
        if colony is None:
            return

        cfg = colony_cfg or {}
        species_name = creature.species.name
        max_food = float(cfg.get("max_food", cfg.get("max_storage", 400.0)))
        single_colony = cfg.get("single_colony", True)
        colony_id = resolve_colony_id(species_name, cfg)
        join_species = cfg.get("join_species")

        if single_colony:
            existing = self.get_colony_nest(colony_id)
        else:
            cx, cy = entity_xy(creature)
            join_radius = float(cfg.get("join_radius", self.DEFAULT_JOIN_RADIUS))
            existing = self.find_nearest_nest(cx, cy, colony_id, join_radius)

        if existing is not None:
            colony.nest_id = existing.id
            colony.colony_id = existing.colony_id
            return

        if join_species is not None:
            # 兵隊蟻など: 働きアリの巣がまだ無い場合は新設しない
            return

        cx, cy = entity_xy(creature)
        initial_food = float(
            cfg.get("initial_stored_food", cfg.get("initial_food", 0.0))
        )
        nest = self.create_nest(
            cx,
            cy,
            species_name,
            colony_id=colony_id,
            max_food=max_food,
            stored_food=initial_food,
        )
        colony.nest_id = nest.id
        colony.colony_id = colony_id

    def update(self, dt: float = 1.0) -> None:
        """巣の更新（食料漏洩→マナ還流、巣からのスポーン等）。"""
        from src.config import config

        dt = float(dt)
        for nest in self.nests.values():
            species_data = config.get_species(nest.owner_species) or {}
            colony_cfg = species_data.get("colony", {})
            if nest.stored_food > 0:
                self._leak_food_to_mana(nest, colony_cfg, dt)
            self._update_nest_spawning(nest, colony_cfg, dt)

    def _spawn_interval_ticks(self, colony_cfg: dict) -> float:
        interval = float(
            colony_cfg.get("spawn_interval_ticks", self.DEFAULT_SPAWN_INTERVAL_TICKS)
        )
        return max(1.0, interval)

    def _update_nest_spawning(self, nest: Nest, colony_cfg: dict, dt: float) -> None:
        """巣の備蓄で一定間隔に1匹スポーン（卵概念なし）。"""
        if not colony_cfg.get("enabled"):
            nest.spawn_timer = 0.0
            return

        interval = self._spawn_interval_ticks(colony_cfg)
        ok, _ = self.spawn_readiness(nest)
        if not ok:
            # 条件を満たさない間は孵化進行しない（溜めない）
            nest.spawn_timer = 0.0
            return

        nest.spawn_timer += dt
        if nest.spawn_timer < interval:
            return

        # 1回の update で大量スポーンしないように「最大1匹」に制限。
        nest.spawn_timer = 0.0
        spawned = self.spawn_worker_from_nest(nest, colony_cfg)
        if spawned is not None:
            self.world.add_creature(spawned)

    def spawn_worker_from_nest(self, nest: Nest, colony_cfg: dict | None = None):
        """巣の備蓄を消費して子個体を生成する。失敗時は None。ワールドへの登録は呼び出し側。"""
        cfg = colony_cfg or {}
        ok, _ = self.spawn_readiness(nest)
        if not ok:
            return None

        cost = float(cfg.get("spawn_food_cost", 0))
        if cost <= 0:
            return None
        nest.stored_food -= cost

        from src.entities.creature_factory import CreatureFactory

        x, y = self.spawn_position(nest.owner_species, cfg)
        return CreatureFactory.create(nest.owner_species, world=self.world, x=x, y=y)

    def _leak_food_to_mana(self, nest: Nest, colony_cfg: dict, dt: float) -> None:
        leak_rate = float(
            colony_cfg.get("food_leak_rate", self.DEFAULT_FOOD_LEAK_RATE)
        )
        mana_ratio = float(
            colony_cfg.get("food_to_mana_ratio", self.DEFAULT_FOOD_TO_MANA_RATIO)
        )
        reserve_ratio = float(
            colony_cfg.get(
                "food_leak_reserve_ratio", self.DEFAULT_FOOD_LEAK_RESERVE_RATIO
            )
        )
        if leak_rate <= 0 or mana_ratio <= 0:
            return

        reserve = nest.max_food * reserve_ratio
        leakable = max(0.0, nest.stored_food - reserve)
        if leakable <= 0:
            return

        leak = min(leakable, leakable * leak_rate * dt)
        if leak <= 0:
            return

        nest.stored_food -= leak
        self.world.return_mana_from_decomposition(
            leak * mana_ratio, nest.x, nest.y
        )

    def distance_to_nest(self, creature) -> float:
        nest = self.get_creature_nest(creature)
        if nest is None:
            return float("inf")
        cx, cy = entity_xy(creature)
        tx, ty = self._nearest_hole_xy(nest, cx, cy)
        return math.hypot(tx - cx, ty - cy)

    def get_creature_nest(self, creature) -> Nest | None:
        colony = getattr(creature, "colony", None)
        if colony is None:
            return None
        return self.get_nest(colony.nest_id)

    def is_at_nest(self, creature, deposit_radius: float) -> bool:
        return self.distance_to_nest(creature) <= deposit_radius

    def deposit_space(self, nest: Nest) -> float:
        """巣にこれ以上入れられる食料量。"""
        return max(0.0, nest.max_food - nest.stored_food)

    def deposit_carried(self, creature) -> float:
        """運搬中チャンクを巣の食料備蓄へ移す。移した食料量を返す。

        備蓄が満杯で入らない分は巣付近でマナ還元し、運搬状態を解く
        （満タン巣で持ち帰りループしないようにする）。
        """
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying:
            return 0.0

        nest = self.get_creature_nest(creature)
        if nest is None:
            return 0.0

        amount = float(colony.carried_biomass)
        if amount <= 0:
            colony.carried_biomass = 0.0
            colony.carried_carcass = None
            return 0.0

        space = self.deposit_space(nest)
        deposited = min(amount, space)
        nest.stored_food += deposited
        leftover = amount - deposited

        if leftover > 0:
            overflow = leftover
            if self.world is not None:
                self.world.return_mana_from_decomposition(
                    overflow * 0.65, nest.x, nest.y
                )
            colony.carried_biomass = 0.0
            colony.carried_carcass = None
        else:
            colony.carried_biomass = 0.0
            colony.carried_carcass = None
        return deposited

    def feed_creature(
        self,
        creature,
        *,
        bite_gain: float = 1.2,
        max_take_ratio: float = 0.12,
    ) -> float:
        """巣の食料備蓄から満腹度を回復。消費した食料量を返す。"""
        nest = self.get_creature_nest(creature)
        if nest is None or nest.stored_food <= 0:
            return 0.0

        hunger_room = satiety_room_until_feed_target(creature)
        if hunger_room <= 0:
            return 0.0

        members = max(1, self.member_count(nest.id, creature.species.name))
        per_member_ratio = float(max_take_ratio) / members
        max_take = nest.stored_food * per_member_ratio
        take = min(nest.stored_food, max_take, hunger_room / float(bite_gain))
        if take <= 0:
            return 0.0

        nest.stored_food -= take
        creature.satiety = min(
            satiety_feed_target(creature),
            creature.satiety + take * bite_gain,
        )
        return take

    def member_count(self, nest_id: int, species_name: str) -> int:
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            if c.species.name != species_name:
                continue
            colony = getattr(c, "colony", None)
            if colony is not None and colony.nest_id == nest_id:
                count += 1
        return count

    def total_member_count(self, nest_id: int) -> int:
        """巣に所属する全種の生存個体数。"""
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            colony = getattr(c, "colony", None)
            if colony is not None and colony.nest_id == nest_id:
                count += 1
        return count

    def spawn_readiness(self, nest: Nest) -> tuple[bool, str]:
        """コロニー全体として働きアリを増やせるか（個体を選ばない判定）。"""
        from src.config import config

        species_data = config.get_species(nest.owner_species) or {}
        cfg = species_data.get("colony", {})
        if not cfg.get("enabled"):
            return False, "コロニー無効"

        cost = float(cfg.get("spawn_food_cost", 0))
        if cost <= 0:
            return False, "繁殖未設定"

        max_workers = int(cfg.get("max_workers", 0))
        if max_workers <= 0:
            return False, "繁殖未設定"

        if is_species_at_population_cap(self.world, nest.owner_species):
            alive = count_alive_by_species(self.world, nest.owner_species)
            cap = get_species_population_cap(self.world, nest.owner_species)
            return False, f"種族上限 ({alive}/{cap})"

        reserve = float(cfg.get("min_food_reserve", 0))
        needed = reserve + cost
        members = self.member_count(nest.id, nest.owner_species)

        if members >= max_workers:
            return False, f"個体数上限 ({members}/{max_workers})"

        if nest.stored_food < needed:
            return (
                False,
                f"備蓄不足 (要 {needed:.0f}, 現在 {nest.stored_food:.0f})",
            )

        return True, f"繁殖可能 ({members}/{max_workers})"

    def can_spawn_worker(
        self, creature, colony_cfg: dict | None = None
    ) -> bool:
        """巣備蓄・個体数上限・最低備蓄を満たすか。"""
        colony = getattr(creature, "colony", None)
        if colony is None:
            return False
        nest = self.get_creature_nest(creature)
        if nest is None:
            return False

        cfg = colony_cfg if colony_cfg is not None else creature.species.colony_data
        cost = float(cfg.get("spawn_food_cost", 0))
        if cost <= 0:
            return False

        max_workers = int(cfg.get("max_workers", 0))
        if max_workers <= 0:
            return False

        if is_species_at_population_cap(self.world, nest.owner_species):
            return False

        reserve = float(cfg.get("min_food_reserve", 0))
        if nest.stored_food < reserve + cost:
            return False

        if self.member_count(nest.id, nest.owner_species) >= max_workers:
            return False

        return True

    def spawn_worker(self, creature, colony_cfg: dict | None = None):
        """食料を消費して子個体を生成する。失敗時は None。ワールドへの登録は呼び出し側。"""
        if not self.can_spawn_worker(creature, colony_cfg):
            return None

        cfg = colony_cfg if colony_cfg is not None else creature.species.colony_data
        cost = float(cfg["spawn_food_cost"])
        nest = self.get_creature_nest(creature)
        nest.stored_food -= cost

        from src.entities.creature_factory import CreatureFactory

        x, y = self.spawn_position(nest.owner_species, cfg)
        return CreatureFactory.create(
            nest.owner_species, world=self.world, x=x, y=y
        )
