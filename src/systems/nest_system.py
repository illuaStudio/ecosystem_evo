# nest_system.py
"""捕食者コロニーの巣を管理する。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.utils.creature_helpers import distance_to_point
from src.utils.position_helpers import entity_xy

if TYPE_CHECKING:
    from src.systems.world import World


@dataclass
class Nest:
    id: int
    x: float
    y: float
    owner_species: str
    stored_food: float = 0.0
    max_food: float = 400.0

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
        max_food: float = 400.0,
    ) -> Nest:
        nest = Nest(
            id=self._next_id,
            x=float(x),
            y=float(y),
            owner_species=species_name,
            max_food=float(max_food),
        )
        self._next_id += 1
        self.nests[nest.id] = nest
        return nest

    def get_nest(self, nest_id: int | None) -> Nest | None:
        if nest_id is None:
            return None
        return self.nests.get(nest_id)

    def find_nearest_nest(
        self,
        x: float,
        y: float,
        species_name: str,
        max_dist: float,
    ) -> Nest | None:
        best = None
        min_dist = float("inf")
        for nest in self.nests.values():
            if nest.owner_species != species_name:
                continue
            dist = ((nest.x - x) ** 2 + (nest.y - y) ** 2) ** 0.5
            if dist <= max_dist and dist < min_dist:
                min_dist = dist
                best = nest
        return best

    def get_colony_nest(self, species_name: str) -> Nest | None:
        """種族のコロニー巣を1つ返す（現状は単一巣モデル用）。"""
        for nest in self.nests.values():
            if nest.owner_species == species_name:
                return nest
        return None

    def spawn_position(self, species_name: str, colony_cfg: dict | None = None) -> tuple[float, float]:
        """巣の位置付近にスポーン座標を返す（初期配置・P 追加用）。"""
        cfg = colony_cfg or {}
        spread = float(cfg.get("spawn_spread", self.DEFAULT_SPAWN_SPREAD))
        nest = self.get_colony_nest(species_name)
        if nest is not None:
            return self._offset_near(nest.x, nest.y, spread)
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
        なければ新設。将来の敵対コロニー用に join_radius による近傍合流も残す。
        """
        colony = getattr(creature, "colony", None)
        if colony is None:
            return

        cfg = colony_cfg or {}
        species_name = creature.species.name
        max_food = float(cfg.get("max_food", cfg.get("max_storage", 400.0)))
        single_colony = cfg.get("single_colony", True)

        if single_colony:
            existing = self.get_colony_nest(species_name)
        else:
            cx, cy = entity_xy(creature)
            join_radius = float(cfg.get("join_radius", self.DEFAULT_JOIN_RADIUS))
            existing = self.find_nearest_nest(cx, cy, species_name, join_radius)

        if existing is not None:
            colony.nest_id = existing.id
            return

        cx, cy = entity_xy(creature)
        nest = self.create_nest(
            cx,
            cy,
            species_name,
            max_food=max_food,
        )
        colony.nest_id = nest.id

    def update(self, dt: float = 1.0) -> None:
        """備蓄食料の腐敗・漏洩 → 巣位置へマナ還流（エコロジー接続）。"""
        from src.config import config

        dt = float(dt)
        for nest in self.nests.values():
            if nest.stored_food <= 0:
                continue
            species_data = config.get_species(nest.owner_species) or {}
            colony_cfg = species_data.get("colony", {})
            self._leak_food_to_mana(nest, colony_cfg, dt)

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
        return distance_to_point(creature, nest.x, nest.y)

    def get_creature_nest(self, creature) -> Nest | None:
        colony = getattr(creature, "colony", None)
        if colony is None:
            return None
        return self.get_nest(colony.nest_id)

    def is_at_nest(self, creature, deposit_radius: float) -> bool:
        return self.distance_to_nest(creature) <= deposit_radius

    def deposit_carried(self, creature) -> float:
        """運搬中の死骸を巣の食料備蓄へ移す。移した食料量を返す。"""
        colony = getattr(creature, "colony", None)
        if colony is None or not colony.is_carrying:
            return 0.0

        nest = self.get_creature_nest(creature)
        if nest is None:
            return 0.0

        carcass = colony.carried_carcass
        amount = float(getattr(carcass, "remaining_biomass", 0.0))
        if amount <= 0:
            colony.carried_carcass = None
            return 0.0

        space = max(0.0, nest.max_food - nest.stored_food)
        deposited = min(amount, space)
        nest.stored_food += deposited
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

        hunger_room = max(0.0, creature.max_satiety - creature.satiety)
        if hunger_room <= 0:
            return 0.0

        members = max(1, self.member_count(nest.id, creature.species.name))
        per_member_ratio = float(max_take_ratio) / members
        max_take = nest.stored_food * per_member_ratio
        take = min(nest.stored_food, max_take, hunger_room / float(bite_gain))
        if take <= 0:
            return 0.0

        nest.stored_food -= take
        creature.satiety = min(creature.max_satiety, creature.satiety + take * bite_gain)
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
