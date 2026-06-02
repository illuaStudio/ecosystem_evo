"""ワールド上のスポーン発生源（エミッター）と環境補充を管理する。"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Dict, List, Optional, Sequence, Tuple

from src.config import config
from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.utils.spatial_grid import iter_creatures_in_radius
from src.sim.utils.stats_helpers import count_alive_by_species, is_species_at_population_cap

if TYPE_CHECKING:
    from src.sim.components.spawn_capability import SpawnCapability
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
    count = 0
    for creature in iter_creatures_in_radius(world, cx, cy, radius, alive_only=True):
        if creature.species.name not in pool:
            continue
        count += 1
    return count


@dataclass
class SpawnEmitter:
    """WorldObject 由来のスポーン発生源キャッシュ。"""

    world_object_id: str
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
    start_trigger: str = "world_load"
    enabled_at_load: bool = True
    initial_burst_count: int = 0
    lifetime_budget: int = -1
    replenish_batch_size: int = 2
    replenish_cooldown_ticks: int = 0
    spawn_at_center: bool = False
    creature_spawn_source: str = "spawn"

    @property
    def is_ambient(self) -> bool:
        return self.spawn_type == "ambient"

    @property
    def uses_on_enable_trigger(self) -> bool:
        return str(self.start_trigger).lower() == "on_enable"


@dataclass
class _EmitterRuntime:
    enabled: bool = False
    burst_done: bool = False
    lifetime_spawned: int = 0
    replenish_cooldown: int = 0
    tracked_creature_ids: set[int] = field(default_factory=set)


class SpawnSystem:
    """spawn_emitters 設定に基づき、エミッターごとに個体数を補充する。"""

    def __init__(self, world: "World") -> None:
        self.world = world
        self.emitters: List[SpawnEmitter] = []
        self.ambient: Optional[SpawnEmitter] = None
        self._accumulators: Dict[str, float] = {}
        self._runtime: Dict[str, _EmitterRuntime] = {}
        self._factory = CreatureFactory()

    def init_from_layout(self, layout: Dict | None = None) -> None:
        self.rebuild_from_world_objects()

    def rebuild_from_world_objects(self) -> None:
        self.emitters.clear()
        self.ambient = None
        self._accumulators.clear()
        old_runtime = dict(self._runtime)
        self._runtime.clear()
        ws = getattr(self.world, "world_object_system", None)
        if ws is None:
            return
        for obj in ws.iter_spawn_emitters():
            if obj.spawn is None:
                continue
            emitter = self._emitter_from_world_object(obj)
            prev = old_runtime.get(emitter.world_object_id)
            if prev is not None:
                rt = _EmitterRuntime(
                    enabled=prev.enabled,
                    burst_done=prev.burst_done,
                    lifetime_spawned=prev.lifetime_spawned,
                    replenish_cooldown=prev.replenish_cooldown,
                    tracked_creature_ids=set(prev.tracked_creature_ids),
                )
            else:
                rt = self._runtime_for_new_emitter(emitter)
            self._runtime[emitter.world_object_id] = rt
            if emitter.is_ambient:
                self.ambient = emitter
            else:
                self.emitters.append(emitter)
            self._accumulators[emitter.world_object_id] = 0.0

    def _runtime_for_new_emitter(self, emitter: SpawnEmitter) -> _EmitterRuntime:
        if emitter.uses_on_enable_trigger:
            return _EmitterRuntime(enabled=False, burst_done=False)
        enabled = bool(emitter.enabled_at_load)
        rt = _EmitterRuntime(enabled=enabled, burst_done=not enabled)
        if enabled and emitter.initial_burst_count > 0:
            rt.burst_done = False
        return rt

    def _emitter_from_world_object(self, obj) -> SpawnEmitter:
        cap = obj.spawn
        assert cap is not None
        batch = cap.replenish_batch_size
        if batch <= 0:
            batch = cap.max_spawns_per_tick
        return SpawnEmitter(
            world_object_id=str(obj.id),
            spawn_type="ambient" if cap.is_ambient else "point",
            species_pool=cap.species_pool,
            target_population=cap.target_population,
            spawn_rate_per_dt=cap.spawn_rate_per_dt,
            radius=cap.radius,
            max_spawns_per_tick=cap.max_spawns_per_tick,
            position_attempts=cap.position_attempts,
            nest_exclusion_radius=cap.nest_exclusion_radius,
            use_biome_weight=cap.use_biome_weight,
            margin=cap.margin,
            x=float(obj.x),
            y=float(obj.y),
            label=cap.label or obj.label,
            start_trigger=str(cap.start_trigger),
            enabled_at_load=bool(cap.enabled_at_load),
            initial_burst_count=int(cap.initial_burst_count),
            lifetime_budget=int(cap.lifetime_budget),
            replenish_batch_size=int(batch),
            replenish_cooldown_ticks=int(cap.replenish_cooldown_ticks),
            spawn_at_center=bool(cap.spawn_at_center),
            creature_spawn_source=str(cap.creature_spawn_source),
        )

    def _get_emitter(self, emitter_id: str) -> SpawnEmitter | None:
        if self.ambient is not None and self.ambient.world_object_id == emitter_id:
            return self.ambient
        for emitter in self.emitters:
            if emitter.world_object_id == emitter_id:
                return emitter
        return None

    def is_emitter_enabled(self, emitter_id: str) -> bool:
        rt = self._runtime.get(emitter_id)
        return bool(rt and rt.enabled)

    def set_emitter_enabled(self, emitter_id: str, enabled: bool) -> int:
        """Enable/disable an emitter. On enable, runs initial burst once. Returns burst count."""
        emitter = self._get_emitter(emitter_id)
        if emitter is None:
            return 0
        rt = self._runtime.setdefault(emitter_id, _EmitterRuntime())
        was_enabled = rt.enabled
        rt.enabled = bool(enabled)
        if not enabled:
            return 0
        if was_enabled and rt.burst_done:
            return 0
        if rt.burst_done:
            return 0
        burst_n = emitter.initial_burst_count
        if burst_n <= 0 and not emitter.uses_on_enable_trigger:
            burst_n = 0
        elif burst_n <= 0 and emitter.uses_on_enable_trigger:
            burst_n = emitter.target_population
        spawned = self._spawn_burst(emitter, burst_n)
        rt.burst_done = True
        rt.replenish_cooldown = emitter.replenish_cooldown_ticks
        return spawned

    def tracked_creature_ids(self, emitter_id: str | None = None) -> set[int]:
        if emitter_id is not None:
            rt = self._runtime.get(emitter_id)
            return set(rt.tracked_creature_ids) if rt else set()
        out: set[int] = set()
        for rt in self._runtime.values():
            out.update(rt.tracked_creature_ids)
        return out

    def sync_tracked_alive(self) -> None:
        """Drop dead creatures from per-emitter tracking sets."""
        for rt in self._runtime.values():
            live: set[int] = set()
            for cid in rt.tracked_creature_ids:
                creature = self._creature_by_id(cid)
                if creature is not None and getattr(creature, "alive", True):
                    live.add(cid)
            rt.tracked_creature_ids = live

    def emitter_has_budget(self, emitter_id: str) -> bool:
        emitter = self._get_emitter(emitter_id)
        rt = self._runtime.get(emitter_id)
        if emitter is None or rt is None:
            return False
        if emitter.lifetime_budget < 0:
            return True
        return rt.lifetime_spawned < emitter.lifetime_budget

    def any_enabled_emitter_has_budget(self) -> bool:
        for emitter_id, rt in self._runtime.items():
            if not rt.enabled:
                continue
            if self.emitter_has_budget(emitter_id):
                return True
        return False

    def _creature_by_id(self, creature_id: int):
        for creature in self.world.creatures:
            if id(creature) == creature_id:
                return creature
        return None

    @property
    def species_pool(self) -> tuple[str, ...]:
        if self.ambient is not None:
            return self.ambient.species_pool
        if self.emitters:
            return self.emitters[0].species_pool
        return DEFAULT_MICRO_FAUNA_SPECIES

    def update(self, dt: float = 1.0) -> None:
        if dt <= 0:
            return
        self.sync_tracked_alive()
        if self.ambient is not None:
            self._update_emitter(self.ambient, dt)
        for emitter in self.emitters:
            self._update_emitter(emitter, dt)

    def _update_emitter(self, emitter: SpawnEmitter, dt: float) -> None:
        if emitter.target_population <= 0 or not emitter.species_pool:
            return
        rt = self._runtime.setdefault(emitter.world_object_id, _EmitterRuntime())
        if not rt.enabled:
            return
        if not self._has_lifetime_budget(emitter, rt):
            return

        if not rt.burst_done:
            burst_n = emitter.initial_burst_count
            if burst_n <= 0 and emitter.uses_on_enable_trigger:
                burst_n = emitter.target_population
            if burst_n > 0:
                self._spawn_burst(emitter, burst_n)
            rt.burst_done = True
            rt.replenish_cooldown = emitter.replenish_cooldown_ticks

        current = self._count_for_emitter(emitter)
        if current >= emitter.target_population:
            return

        if emitter.replenish_batch_size > 0 and emitter.spawn_rate_per_dt <= 0:
            if emitter.replenish_cooldown_ticks > 0 and rt.replenish_cooldown > 0:
                rt.replenish_cooldown -= 1
                return
            deficit = emitter.target_population - current
            if deficit <= 0:
                return
            batch = min(emitter.replenish_batch_size, deficit)
            self._spawn_burst(emitter, batch)
            if emitter.replenish_cooldown_ticks > 0:
                rt.replenish_cooldown = emitter.replenish_cooldown_ticks
            return

        acc = self._accumulators.setdefault(emitter.world_object_id, 0.0)
        acc += emitter.spawn_rate_per_dt * float(dt)
        spawned = 0
        while (
            acc >= 1.0
            and current < emitter.target_population
            and spawned < emitter.max_spawns_per_tick
        ):
            acc -= 1.0
            if self._try_spawn_one(emitter, rt):
                current += 1
                spawned += 1
            else:
                break
        self._accumulators[emitter.world_object_id] = acc

    def _has_lifetime_budget(self, emitter: SpawnEmitter, rt: _EmitterRuntime) -> bool:
        if emitter.lifetime_budget < 0:
            return True
        return rt.lifetime_spawned < emitter.lifetime_budget

    def _spawn_burst(self, emitter: SpawnEmitter, count: int) -> int:
        if count <= 0:
            return 0
        rt = self._runtime.setdefault(emitter.world_object_id, _EmitterRuntime())
        spawned = 0
        attempts = 0
        max_attempts = max(count * 3, count)
        while spawned < count and attempts < max_attempts:
            attempts += 1
            if emitter.target_population > 0:
                if self._count_for_emitter(emitter) >= emitter.target_population:
                    break
            if not self._has_lifetime_budget(emitter, rt):
                break
            if self._try_spawn_one(emitter, rt):
                spawned += 1
        return spawned

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

    def _try_spawn_one(self, emitter: SpawnEmitter, rt: _EmitterRuntime) -> bool:
        species = self._pick_species(emitter.species_pool)
        if species is None:
            return False

        pos = self._pick_spawn_position(emitter)
        if pos is None:
            return False

        x, y = pos
        if not emitter.spawn_at_center and not self._accept_spawn_at(
            x, y, emitter.use_biome_weight
        ):
            return False

        creature = self._factory.create(species, world=self.world, x=x, y=y)
        source = emitter.creature_spawn_source or "spawn"
        self.world.add_creature(creature, spawn_source=source)
        rt.tracked_creature_ids.add(id(creature))
        rt.lifetime_spawned += 1
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
        if emitter.spawn_at_center:
            return float(emitter.x), float(emitter.y)
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
        from src.sim.utils.world_object_helpers import iter_active_affiliation_roots

        for root in iter_active_affiliation_roots(self.world):
            if (x - root.x) ** 2 + (y - root.y) ** 2 < radius * radius:
                return True
        return False

    def _accept_spawn_at(self, x: float, y: float, use_biome_weight: bool) -> bool:
        from src.sim.utils.spawn_placement import SpawnPlacementResolver

        return SpawnPlacementResolver(self.world).accept_probabilistic(
            x, y, use_biome_weight=use_biome_weight
        )
