"""WorldObject 上の spawn capability（配置の正は WorldObjectSystem）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES

StartTrigger = str  # "world_load" | "on_enable"


@dataclass(frozen=True)
class SpawnCapability:
    mode: str = "point"
    species_pool: Tuple[str, ...] = ()
    target_population: int = 10
    spawn_rate_per_dt: float = 0.1
    radius: float = 80.0
    max_spawns_per_tick: int = 2
    position_attempts: int = 8
    nest_exclusion_radius: float = 0.0
    use_biome_weight: bool = True
    margin: int = 80
    label: str = ""
    start_trigger: StartTrigger = "world_load"
    enabled_at_load: bool = True
    initial_burst_count: int = 0
    lifetime_budget: int = -1
    replenish_batch_size: int = 0
    replenish_cooldown_ticks: int = 0
    spawn_at_center: bool = False
    creature_spawn_source: str = "spawn"

    @property
    def is_ambient(self) -> bool:
        return str(self.mode).lower() == "ambient"

    @property
    def uses_on_enable(self) -> bool:
        return str(self.start_trigger).lower() == "on_enable"

    @classmethod
    def from_mapping(
        cls,
        data: Mapping[str, Any],
        *,
        global_defaults: Mapping[str, Any] | None = None,
        type_defaults: Mapping[str, Any] | None = None,
    ) -> SpawnCapability:
        merged: Dict[str, Any] = {}
        if global_defaults:
            merged.update(global_defaults)
        if type_defaults:
            merged.update(type_defaults)
        merged.update(dict(data))

        mode = str(merged.get("mode", "point")).lower()
        if mode not in ("ambient", "point"):
            mode = "point"

        pool = [str(s) for s in (merged.get("species_pool") or []) if str(s)]
        if not pool:
            pool = list(DEFAULT_MICRO_FAUNA_SPECIES)

        trigger = str(merged.get("start_trigger", "world_load")).lower()
        if trigger not in ("world_load", "on_enable"):
            trigger = "world_load"

        burst = max(0, int(merged.get("initial_burst_count", 0)))
        budget_raw = merged.get("lifetime_budget")
        lifetime_budget = -1 if budget_raw is None else int(budget_raw)

        batch = int(merged.get("replenish_batch_size", 0))
        if batch <= 0:
            batch = max(1, int(merged.get("max_spawns_per_tick", 2)))

        return cls(
            mode=mode,
            species_pool=tuple(pool),
            target_population=max(0, int(merged.get("target_population", 0))),
            spawn_rate_per_dt=max(0.0, float(merged.get("spawn_rate_per_dt", 0.0))),
            radius=max(0.0, float(merged.get("radius", 80.0))),
            max_spawns_per_tick=max(1, int(merged.get("max_spawns_per_tick", 2))),
            position_attempts=max(1, int(merged.get("position_attempts", 8))),
            nest_exclusion_radius=max(
                0.0, float(merged.get("nest_exclusion_radius", 0.0))
            ),
            use_biome_weight=bool(merged.get("use_biome_weight", True)),
            margin=max(0, int(merged.get("margin", 80))),
            label=str(merged.get("label", merged.get("type", ""))),
            start_trigger=trigger,
            enabled_at_load=bool(merged.get("enabled_at_load", trigger != "on_enable")),
            initial_burst_count=burst,
            lifetime_budget=lifetime_budget,
            replenish_batch_size=batch,
            replenish_cooldown_ticks=max(
                0, int(merged.get("replenish_cooldown_ticks", 0))
            ),
            spawn_at_center=bool(merged.get("spawn_at_center", False)),
            creature_spawn_source=str(
                merged.get("creature_spawn_source", "spawn")
            ),
        )
