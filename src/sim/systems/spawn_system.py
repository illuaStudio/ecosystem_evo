"""ワールド上のスポーン発生源（エミッター）と環境補充を管理する。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from src.config import config
from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.utils.spatial_grid import iter_creatures_in_radius
from src.sim.utils.stats_helpers import count_alive_by_species, is_species_at_population_cap

if TYPE_CHECKING:
    from src.sim.systems.world import World

SpawnMode = str  # "ambient" | "point"

DEFAULT_SPAWN_DEFAULTS: Dict = {
    "mode": "point",
    "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
    "target_population": 10,
    "spawn_rate_per_dt": 0.1,
    "radius": 80.0,
    "max_spawns_per_tick": 2,
    "position_attempts": 8,
    "nest_exclusion_radius": 0.0,
    "use_biome_weight": True,
    "margin": 80,
}

DEFAULT_AMBIENT_DEFAULTS: Dict = {
    "mode": "ambient",
    "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
    "target_population": 40,
    "spawn_rate_per_dt": 0.08,
    "radius": 0.0,
    "max_spawns_per_tick": 4,
    "position_attempts": 12,
    "nest_exclusion_radius": 120.0,
    "use_biome_weight": True,
    "margin": 80,
}


def count_alive_in_pool(world: "World", species_pool: Sequence[str]) -> int:
    total = 0
    for name in species_pool:
        total += count_alive_by_species(world, name)
    return total


def count_alive_in_radius(
    world: "World",
    species_pool: Sequence[str],
    cx: float,
    cy: float,
    radius: float,
) -> int:
    if radius <= 0:
        return 0
    pool = set(species_pool)
    r2 = radius * radius
    count = 0
    for creature in iter_creatures_in_radius(world, cx, cy, radius, alive_only=True):
        if creature.species.name not in pool:
            continue
        count += 1
    return count


@dataclass
class SpawnEmitter:
    """一定エリア内、またはワールド全体で生物を湧かせる発生源。"""

    id: int
    spawn_type: str
    species_pool: Tuple[str, ...]
    target_population: int = 10
    spawn_rate_per_dt: float = 0.1
    radius: float = 80.0
    max_spawns_per_tick: int = 2
    position_attempts: int = 8
    nest_exclusion_radius: float = 0.0
    use_biome_weight: bool = True
    margin: int = 80
    x: float = 0.0
    y: float = 0.0
    label: str = ""

    @property
    def is_ambient(self) -> bool:
        return self.spawn_type == "ambient"


class SpawnSystem:
    """spawn_emitters 設定に基づき、エミッターごとに個体数を補充する。"""

    def __init__(self, world: "World") -> None:
        self.world = world
        self.emitters: List[SpawnEmitter] = []
        self.ambient: Optional[SpawnEmitter] = None
        self._next_id = 1
        self._type_defaults: Dict[str, Dict] = {}
        self._accumulators: Dict[int, float] = {}
        self._factory = CreatureFactory()

    def init_from_config(
        self,
        cfg: Dict | None,
        *,
        legacy_ambient: Dict | None = None,
    ) -> None:
        self.emitters.clear()
        self.ambient = None
        self._next_id = 1
        self._type_defaults.clear()
        self._accumulators.clear()

        if not cfg and legacy_ambient:
            self._init_ambient_only(legacy_ambient)
            return
        if not cfg:
            return

        global_defaults = dict(DEFAULT_SPAWN_DEFAULTS)
        global_defaults.update(cfg.get("defaults") or {})

        for key, value in (cfg.get("types") or {}).items():
            if isinstance(value, dict):
                self._type_defaults[str(key)] = dict(value)

        ambient_raw = cfg.get("ambient")
        if isinstance(ambient_raw, dict):
            self.ambient = self._build_ambient_emitter(ambient_raw, global_defaults)
            self._accumulators[self.ambient.id] = 0.0

        for entry in cfg.get("sources") or cfg.get("emitters") or []:
            if isinstance(entry, dict):
                self._add_point_from_entry(entry, global_defaults)

    def _init_ambient_only(self, legacy_ambient: Dict) -> None:
        merged = dict(DEFAULT_AMBIENT_DEFAULTS)
        merged.update(legacy_ambient)
        self.ambient = self._build_ambient_emitter(merged, {})
        self._accumulators[self.ambient.id] = 0.0

    def _build_ambient_emitter(self, raw: Dict, global_defaults: Dict) -> SpawnEmitter:
        merged = dict(DEFAULT_AMBIENT_DEFAULTS)
        merged.update(global_defaults)
        merged.update(raw)
        merged["mode"] = "ambient"
        return self._make_emitter(merged)

    def _resolve_entry(self, entry: Dict, global_defaults: Dict) -> Dict:
        spawn_type = str(entry.get("type", global_defaults.get("type", "micro_fauna")))
        merged = dict(global_defaults)
        merged.update(self._type_defaults.get(spawn_type, {}))
        merged.update(entry)
        if "mode" not in merged:
            merged["mode"] = "point"
        return merged

    def _normalize_pool(self, raw) -> Tuple[str, ...]:
        pool = [str(s) for s in (raw or []) if str(s)]
        if not pool:
            pool = list(DEFAULT_MICRO_FAUNA_SPECIES)
        return tuple(pool)

    def _make_emitter(self, data: Dict) -> SpawnEmitter:
        emitter_id = self._next_id
        self._next_id += 1
        mode = str(data.get("mode", "point"))
        if mode not in ("ambient", "point"):
            mode = "point"
        pool = self._normalize_pool(data.get("species_pool"))
        emitter = SpawnEmitter(
            id=emitter_id,
            spawn_type=mode,
            species_pool=pool,
            target_population=max(0, int(data.get("target_population", 0))),
            spawn_rate_per_dt=max(0.0, float(data.get("spawn_rate_per_dt", 0.0))),
            radius=max(0.0, float(data.get("radius", 80.0))),
            max_spawns_per_tick=max(1, int(data.get("max_spawns_per_tick", 2))),
            position_attempts=max(1, int(data.get("position_attempts", 8))),
            nest_exclusion_radius=max(0.0, float(data.get("nest_exclusion_radius", 0.0))),
            use_biome_weight=bool(data.get("use_biome_weight", True)),
            margin=max(0, int(data.get("margin", 80))),
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            label=str(data.get("label", data.get("type", ""))),
        )
        return emitter

    def _add_point_from_entry(self, entry: Dict, global_defaults: Dict) -> None:
        if "x" not in entry or "y" not in entry:
            return
        data = self._resolve_entry(entry, global_defaults)
        data["mode"] = "point"
        emitter = self._make_emitter(data)
        self.emitters.append(emitter)
        self._accumulators[emitter.id] = 0.0

    @property
    def species_pool(self) -> tuple[str, ...]:
        """後方互換: ambient エミッターの種プール（なければデフォルト）。"""
        if self.ambient is not None:
            return self.ambient.species_pool
        if self.emitters:
            return self.emitters[0].species_pool
        return DEFAULT_MICRO_FAUNA_SPECIES

    def update(self, dt: float = 1.0) -> None:
        if dt <= 0:
            return
        if self.ambient is not None:
            self._update_emitter(self.ambient, dt)
        for emitter in self.emitters:
            self._update_emitter(emitter, dt)

    def _update_emitter(self, emitter: SpawnEmitter, dt: float) -> None:
        if emitter.target_population <= 0 or not emitter.species_pool:
            return

        current = self._count_for_emitter(emitter)
        if current >= emitter.target_population:
            return

        acc = self._accumulators.setdefault(emitter.id, 0.0)
        acc += emitter.spawn_rate_per_dt * float(dt)
        spawned = 0

        while (
            acc >= 1.0
            and current < emitter.target_population
            and spawned < emitter.max_spawns_per_tick
        ):
            acc -= 1.0
            if self._try_spawn_one(emitter):
                current += 1
                spawned += 1

        self._accumulators[emitter.id] = acc

    def _count_for_emitter(self, emitter: SpawnEmitter) -> int:
        if emitter.is_ambient:
            return count_alive_in_pool(self.world, emitter.species_pool)
        return count_alive_in_radius(
            self.world,
            emitter.species_pool,
            emitter.x,
            emitter.y,
            emitter.radius,
        )

    def _try_spawn_one(self, emitter: SpawnEmitter) -> bool:
        species = self._pick_species(emitter.species_pool)
        if species is None:
            return False

        pos = self._pick_spawn_position(emitter)
        if pos is None:
            return False

        x, y = pos
        if not self._accept_spawn_at(x, y, emitter.use_biome_weight):
            return False

        creature = self._factory.create(species, world=self.world, x=x, y=y)
        self.world.add_creature(creature, spawn_source="spawn")
        return True

    def _pick_species(self, pool: Sequence[str]) -> Optional[str]:
        available = [
            name
            for name in pool
            if name in config.species and not is_species_at_population_cap(self.world, name)
        ]
        if not available:
            return None
        return random.choice(available)

    def _pick_spawn_position(self, emitter: SpawnEmitter) -> Optional[Tuple[float, float]]:
        from src.sim.utils.spawn_placement import SpawnPlacementResolver

        resolver = SpawnPlacementResolver(self.world)
        anchor = SpawnPlacementResolver.anchor_from_emitter(
            emitter, is_ambient=emitter.is_ambient
        )
        options = SpawnPlacementResolver.options_from_emitter(emitter)
        pos = resolver.pick(anchor, options)
        if pos is not None and self._too_close_to_nest(
            pos[0], pos[1], emitter.nest_exclusion_radius
        ):
            return None
        return pos

    def _too_close_to_nest(self, x: float, y: float, radius: float) -> bool:
        if radius <= 0:
            return False
        from src.sim.utils.world_object_helpers import iter_active_colony_roots

        for root in iter_active_colony_roots(self.world):
            if (x - root.x) ** 2 + (y - root.y) ** 2 < radius * radius:
                return True
        return False

    def _accept_spawn_at(self, x: float, y: float, use_biome_weight: bool) -> bool:
        from src.sim.utils.spawn_placement import SpawnPlacementResolver

        return SpawnPlacementResolver(self.world).accept_probabilistic(
            x, y, use_biome_weight=use_biome_weight
        )

    def _accept_biome_spawn(self, x: float, y: float) -> bool:
        return self._accept_spawn_at(x, y, use_biome_weight=True)
