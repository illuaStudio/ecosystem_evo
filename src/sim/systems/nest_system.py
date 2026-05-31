# nest_system.py
"""捕食者コロニーの巣を管理する。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.sim.utils.colony_config_helpers import (
    get_min_food_reserve,
    resolve_colony_runtime_cfg,
)
from src.sim.utils.creature_helpers import (
    distance_to_point,
    is_point_in_nest_territory,
    resolve_colony_id,
)
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.field_effect_cache import invalidate_field_effect_cache

if TYPE_CHECKING:
    from src.sim.systems.world import World

# この値以下で破壊（int 表示の 0/120 と復活見えを防ぐ）
HOLE_DESTROY_HP = 1.0


@dataclass
class NestHole:
    x: float
    y: float
    hp: float = 0.0
    max_hp: float = 100.0


@dataclass
class Nest:
    id: int
    x: float
    y: float
    owner_species: str
    colony_id: str = ""
    stored_food: float = 0.0
    max_food: float = 400.0
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
    DEFAULT_FOOD_LEAK_RESERVE_RATIO = 0.12
    WORLD_MARGIN = 30.0

    def __init__(self, world: "World") -> None:
        self.world = world
        self.nests: dict[int, Nest] = {}
        self._next_id = 1
        self._sim_time = 0.0

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
        nest.holes.append(self._new_hole(float(x), float(y)))
        self._next_id += 1
        self.nests[nest.id] = nest
        invalidate_field_effect_cache(self.world)
        zone_system = getattr(self.world, "zone_system", None)
        if zone_system is not None:
            zone_system.sync_colony_clearing(colony_id, nest.x, nest.y)
        return nest

    def _colony_settings(self) -> dict:
        return getattr(self.world, "colony_settings", {}) or {}

    def _hole_max_hp(self) -> float:
        return float(self._colony_settings().get("hole_max_hp", 120.0))

    def _new_hole(self, x: float, y: float) -> NestHole:
        max_hp = self._hole_max_hp()
        return NestHole(x=x, y=y, hp=max_hp, max_hp=max_hp)

    def add_hole(self, nest: Nest, x: float, y: float) -> None:
        x, y = self._clamp_to_world(float(x), float(y))
        nest.holes.append(self._new_hole(x, y))
        invalidate_field_effect_cache(self.world)

    def damage_hole(
        self, nest: Nest, hole: NestHole, amount: float, *, attacker_colony_id: str
    ) -> float:
        """敵勢力兵隊のみ。実際に与えたダメージ量。"""
        from src.sim.utils.colony_helpers import is_colony_defeated, is_rival_colony

        if nest is None or hole is None or amount <= 0:
            return 0.0
        if hole not in (nest.holes or []):
            return 0.0
        if is_colony_defeated(self.world, nest.colony_id):
            return 0.0
        if not is_rival_colony(self.world, attacker_colony_id, nest.colony_id):
            return 0.0
        if float(hole.hp) <= 0:
            return 0.0

        dealt = min(float(hole.hp), float(amount))
        hole.hp = max(0.0, hole.hp - dealt)

        if hole.hp <= HOLE_DESTROY_HP:
            hole.hp = 0.0
            self._remove_hole(nest, hole)
        return dealt

    def _remove_hole(self, nest: Nest, hole: NestHole) -> None:
        try:
            nest.holes.remove(hole)
        except ValueError:
            pass
        if len(nest.holes) == 0:
            self.defeat_colony(nest.colony_id)

    def defeat_colony(self, colony_id: str) -> None:
        """最後の巣穴破壊＝勢力敗北。個体はワールドに残す（巣のみ消滅）。"""
        if not colony_id:
            return
        defeated = getattr(self.world, "defeated_colonies", None)
        if defeated is None:
            self.world.defeated_colonies = set()
        if colony_id in self.world.defeated_colonies:
            return

        self.world.defeated_colonies.add(colony_id)
        nest = self.get_colony_nest(colony_id)
        if nest is not None:
            del self.nests[nest.id]

        from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered

        for creature in self.world.creatures:
            colony = getattr(creature, "colony", None)
            if colony is None or colony.colony_id != colony_id:
                continue
            colony.defeated = True
            colony.nest_id = None
            from src.sim.utils.inventory_helpers import clear_inventory_biomass

            clear_inventory_biomass(creature)
            if is_creature_sheltered(creature):
                creature.become_corpse(cause="defeat")
                clear_creature_shelter(creature)

        message = f"勢力 {colony_id} が敗北しました"
        self.world.last_defeat_message = message
        from src.sim.emitters import emit_colony_defeated

        emit_colony_defeated(self.world, colony_id, message)

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

        from src.sim.utils.colony_helpers import is_point_in_rival_territory

        if is_point_in_rival_territory(self.world, nest.colony_id, x, y):
            return False, "敵テリトリーと重なります"

        min_spacing = float(cfg.get("min_hole_spacing", 120))
        for h in nest.holes or []:
            if math.hypot(h.x - x, h.y - y) < min_spacing:
                return False, f"既存の巣穴に近すぎます (要 {min_spacing:.0f}px 以上)"

        cost = float(cfg.get("hole_food_cost", 250))
        reserve = get_min_food_reserve(self.world)
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
        """コロニー有効種を巣に割り当て。

        single_colony=true（既定）: 同種の既存巣があれば距離に関係なく合流。
        なければ新設。将来の複数コロニー用に join_radius による近傍合流も残す。
        """
        colony = getattr(creature, "colony", None)
        if colony is None:
            return

        cfg = colony_cfg or {}
        species_name = creature.species.name
        single_colony = cfg.get("single_colony", True)
        colony_id = resolve_colony_id(species_name, cfg)
        join_species = cfg.get("join_species")

        if single_colony:
            existing = self.get_colony_nest(colony_id)
        else:
            cx, cy = entity_xy(creature)
            join_radius = float(cfg.get("join_radius", self.DEFAULT_JOIN_RADIUS))
            existing = self.find_nearest_nest(cx, cy, colony_id, join_radius)

        from src.sim.utils.colony_helpers import is_colony_defeated

        if colony_id and is_colony_defeated(self.world, colony_id):
            colony.defeated = True
            colony.nest_id = None
            return

        if existing is not None:
            colony.nest_id = existing.id
            colony.colony_id = existing.colony_id
            return

        if join_species is not None:
            # 兵隊蟻など: 働きアリの巣がまだ無い場合は新設しない
            return

        cx, cy = entity_xy(creature)
        runtime_cfg = resolve_colony_runtime_cfg(self.world, colony_id, cfg)
        max_food = float(runtime_cfg["max_food"])
        initial_food = float(runtime_cfg["initial_stored_food"])
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
        """巣の更新（食料漏洩など）。"""
        dt = float(dt)
        self._sim_time += dt
        for nest in list(self.nests.values()):
            runtime_cfg = resolve_colony_runtime_cfg(self.world, nest.colony_id, {})
            if nest.stored_food > 0:
                self._leak_food(nest, runtime_cfg, dt)

    def _leak_food(self, nest: Nest, colony_cfg: dict, dt: float) -> None:
        if not colony_cfg:
            return
        leak_per_tick = float(colony_cfg["food_leak_per_tick"])
        reserve_ratio = float(colony_cfg["food_leak_reserve_ratio"])
        if leak_per_tick <= 0:
            return

        reserve = nest.max_food * reserve_ratio
        leakable = max(0.0, nest.stored_food - reserve)
        if leakable <= 0:
            return

        leak = min(leakable, leak_per_tick)
        if leak <= 0:
            return

        nest.stored_food -= leak

    def try_consume_food(self, nest: Nest, amount: float) -> bool:
        """巣備蓄から食料を消費する。不足時は False。"""
        if nest is None or amount <= 0:
            return False
        if nest.stored_food < amount:
            return False
        nest.stored_food -= amount
        return True

    def count_colony_members(self, nest_id: int, species_names: list[str]) -> int:
        """巣に所属する指定種族の生存個体数。"""
        if not species_names:
            return self.total_member_count(nest_id)
        names = set(species_names)
        count = 0
        for c in self.world.creatures:
            if not getattr(c, "alive", True):
                continue
            if c.species.name not in names:
                continue
            colony = getattr(c, "colony", None)
            if colony is not None and colony.nest_id == nest_id:
                count += 1
        return count

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
        """インベントリ内バイオマスを巣の食料備蓄へ移す。移した食料量を返す。

        備蓄が満杯で入らない分は破棄する。
        """
        from src.sim.utils.inventory_helpers import clear_inventory_biomass, inventory_is_loaded

        if not inventory_is_loaded(creature):
            return 0.0

        nest = self.get_creature_nest(creature)
        if nest is None:
            return 0.0

        amount = clear_inventory_biomass(creature)
        if amount <= 0:
            return 0.0

        space = self.deposit_space(nest)
        deposited = min(amount, space)
        nest.stored_food += deposited
        return deposited

    def feed_creature(
        self,
        creature,
        *,
        bite_gain: float = 1.2,
        feed_per_tick: float = 11.0,
    ) -> float:
        """巣の食料備蓄から満腹度を回復。消費した食料量を返す。"""
        nest = self.get_creature_nest(creature)
        if nest is None or nest.stored_food <= 0:
            return 0.0

        max_sat = float(creature.max_satiety)
        if float(creature.satiety) >= max_sat:
            return 0.0

        take = min(nest.stored_food, float(feed_per_tick))
        if take <= 0:
            return 0.0

        nest.stored_food -= take
        creature.satiety = min(
            max_sat,
            creature.satiety + take * float(bite_gain),
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
