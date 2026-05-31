"""環境スポーン — 極小虫プールを目標個体数まで補充する。"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from src.config import config
from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.utils.stats_helpers import count_alive_by_species, is_species_at_population_cap

if TYPE_CHECKING:
    from src.sim.systems.world import World

DEFAULT_AMBIENT_SPAWN_CONFIG: Dict = {
    "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
    "target_population": 40,
    "spawn_rate_per_dt": 0.08,
    "nest_exclusion_radius": 120.0,
    "max_attempts_per_tick": 4,
    "position_attempts": 12,
    "margin": 80,
}


def normalize_ambient_spawn_config(raw: Optional[Dict]) -> Optional[Dict]:
    """ambient_spawns ブロックを正規化。空なら None。"""
    if not raw:
        return None
    cfg = dict(DEFAULT_AMBIENT_SPAWN_CONFIG)
    cfg.update(raw)
    pool = [str(s) for s in cfg.get("species_pool") or [] if str(s)]
    if not pool:
        pool = list(DEFAULT_MICRO_FAUNA_SPECIES)
    cfg["species_pool"] = pool
    cfg["target_population"] = max(0, int(cfg.get("target_population", 0)))
    cfg["spawn_rate_per_dt"] = max(0.0, float(cfg.get("spawn_rate_per_dt", 0.0)))
    cfg["nest_exclusion_radius"] = max(0.0, float(cfg.get("nest_exclusion_radius", 0.0)))
    cfg["max_attempts_per_tick"] = max(1, int(cfg.get("max_attempts_per_tick", 1)))
    cfg["position_attempts"] = max(1, int(cfg.get("position_attempts", 8)))
    cfg["margin"] = max(0, int(cfg.get("margin", 80)))
    return cfg


def count_alive_in_pool(world: "World", species_pool: List[str]) -> int:
    total = 0
    for name in species_pool:
        total += count_alive_by_species(world, name)
    return total


class AmbientSpawner:
    def __init__(self, world: "World", spawn_config: Optional[Dict]) -> None:
        self._world = world
        self.config = normalize_ambient_spawn_config(spawn_config)
        self._accumulator = 0.0
        self._factory = CreatureFactory()

    @property
    def species_pool(self) -> tuple[str, ...]:
        if not self.config:
            return DEFAULT_MICRO_FAUNA_SPECIES
        return tuple(self.config["species_pool"])

    def update(self, dt: float = 1.0) -> None:
        if not self.config or dt <= 0:
            return

        pool = self.config["species_pool"]
        target = int(self.config["target_population"])
        if target <= 0 or not pool:
            return

        current = count_alive_in_pool(self._world, pool)
        if current >= target:
            return

        self._accumulator += float(self.config["spawn_rate_per_dt"]) * float(dt)
        max_spawns = int(self.config["max_attempts_per_tick"])
        spawned = 0

        while self._accumulator >= 1.0 and current < target and spawned < max_spawns:
            self._accumulator -= 1.0
            if self._try_spawn_one(pool):
                current += 1
                spawned += 1

    def _try_spawn_one(self, pool: List[str]) -> bool:
        species = self._pick_species(pool)
        if species is None:
            return False

        pos = self._pick_spawn_position()
        if pos is None:
            return False

        x, y = pos
        if not self._accept_biome_spawn(x, y):
            return False

        creature = self._factory.create(species, world=self._world, x=x, y=y)
        self._world.add_creature(creature, spawn_source="spawn")
        return True

    def _pick_species(self, pool: List[str]) -> Optional[str]:
        available = [
            name
            for name in pool
            if name in config.species and not is_species_at_population_cap(self._world, name)
        ]
        if not available:
            return None
        return random.choice(available)

    def _pick_spawn_position(self) -> Optional[Tuple[float, float]]:
        world = self._world
        margin = int(self.config["margin"])
        attempts = int(self.config["position_attempts"])
        exclusion = float(self.config["nest_exclusion_radius"])
        x_min = margin
        y_min = margin
        x_max = max(x_min, int(world.width) - margin)
        y_max = max(y_min, int(world.height) - margin)

        best: Optional[Tuple[float, float, float]] = None
        for _ in range(attempts):
            x = random.uniform(x_min, x_max)
            y = random.uniform(y_min, y_max)
            if not world.is_valid_position(x, y):
                continue
            if self._too_close_to_nest(x, y, exclusion):
                continue
            mult = world.biome.get_spawn_rate_multiplier(x, y)
            if best is None or mult > best[2]:
                best = (x, y, mult)

        if best is None:
            return None
        return best[0], best[1]

    def _too_close_to_nest(self, x: float, y: float, radius: float) -> bool:
        if radius <= 0:
            return False
        nests = getattr(self._world.nest_system, "nests", None) or {}
        for nest in nests.values():
            if (x - nest.x) ** 2 + (y - nest.y) ** 2 < radius * radius:
                return True
        return False

    def _accept_biome_spawn(self, x: float, y: float) -> bool:
        mult = self._world.biome.get_spawn_rate_multiplier(x, y)
        if mult <= 0:
            return False
        rich_mult = self._world.biome.get_max_spawn_rate_multiplier()
        if rich_mult <= 0:
            return True
        return random.random() < min(1.0, mult / rich_mult)
