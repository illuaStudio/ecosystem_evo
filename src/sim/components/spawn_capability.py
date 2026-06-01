"""WorldObject 上の spawn capability（配置の正は WorldObjectSystem）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping, Sequence, Tuple

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES


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

    @property
    def is_ambient(self) -> bool:
        return str(self.mode).lower() == "ambient"

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
        )
