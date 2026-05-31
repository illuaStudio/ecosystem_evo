"""スポーン座標の anchor 型と共通配置ロジック。"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

from src.sim.utils.territory_helpers import resolve_colony_id

if TYPE_CHECKING:
    from src.sim.systems.world import World

DEFAULT_MARGIN = 80
DEFAULT_ATTEMPTS = 32


@dataclass(frozen=True)
class SpawnAnchor:
    """スポーン起点。type に応じて x/y/radius/spread/colony_id を解釈する。"""

    type: str  # world | area | point | nest | profile_nest
    x: float = 0.0
    y: float = 0.0
    radius: float = 0.0
    spread: float = 0.0
    colony_id: str = ""


@dataclass
class SpawnPlacementOptions:
    respect_zones: bool = True
    use_biome_weight: bool = True
    attempts: int = DEFAULT_ATTEMPTS
    margin: int = DEFAULT_MARGIN
    nest_exclusion_radius: float = 0.0
    fallback_unrestricted: bool = False


@dataclass
class InitialSpawnEntry:
    species: str
    count: int
    anchor: SpawnAnchor
    options: SpawnPlacementOptions = field(default_factory=SpawnPlacementOptions)


def parse_anchor(raw: Any, *, default_type: str = "world") -> SpawnAnchor:
    if raw is None:
        return SpawnAnchor(type=default_type)
    if isinstance(raw, str):
        return SpawnAnchor(type=raw)
    if not isinstance(raw, dict):
        return SpawnAnchor(type=default_type)
    anchor_type = str(raw.get("type", default_type))
    return SpawnAnchor(
        type=anchor_type,
        x=float(raw.get("x", 0.0)),
        y=float(raw.get("y", 0.0)),
        radius=float(raw.get("radius", 0.0)),
        spread=float(raw.get("spread", 0.0)),
        colony_id=str(raw.get("colony_id", "")),
    )


def parse_placement_options(
    raw: Dict | None,
    *,
    defaults: Dict | None = None,
) -> SpawnPlacementOptions:
    merged: Dict = {}
    if defaults:
        merged.update(defaults)
    if raw:
        merged.update(raw)
    return SpawnPlacementOptions(
        respect_zones=bool(merged.get("respect_zones", True)),
        use_biome_weight=bool(merged.get("use_biome_weight", True)),
        attempts=max(1, int(merged.get("attempts", merged.get("position_attempts", DEFAULT_ATTEMPTS)))),
        margin=max(0, int(merged.get("margin", DEFAULT_MARGIN))),
        nest_exclusion_radius=max(0.0, float(merged.get("nest_exclusion_radius", 0.0))),
        fallback_unrestricted=bool(merged.get("fallback_unrestricted", False)),
    )


def _colony_anchor_for_species(
    world: "World",
    species_name: str,
    colony_cfg: Dict,
    *,
    prefer_profile: bool = False,
) -> SpawnAnchor:
    colony_id = resolve_colony_id(species_name, colony_cfg)
    from src.sim.utils.colony_config_helpers import resolve_colony_runtime_cfg

    runtime_cfg = resolve_colony_runtime_cfg(world, colony_id, colony_cfg)
    spread = float(runtime_cfg.get("spawn_spread", 28.0))
    anchor_type = "profile_nest" if prefer_profile else "nest"
    return SpawnAnchor(type=anchor_type, colony_id=colony_id, spread=spread)


def expand_initial_entities(world_data: Dict, world: "World") -> List[InitialSpawnEntry]:
    """initial_entities {種: 数} を anchor 付きエントリへ展開（後方互換）。"""
    from src.config import config

    initial = dict(world_data.get("initial_entities", {}))
    if not initial:
        if world_data.get("initial_amoeba"):
            initial["Amoeba"] = world_data["initial_amoeba"]
        if world_data.get("initial_ant"):
            initial["red_ant"] = world_data["initial_ant"]
        elif world_data.get("initial_predator"):
            initial["red_ant"] = world_data["initial_predator"]

    entries: List[InitialSpawnEntry] = []
    for species_name, count in initial.items():
        n = int(count)
        if n <= 0:
            continue
        species_data = config.get_species(species_name) or {}
        colony_cfg = species_data.get("colony", {})
        if colony_cfg.get("enabled"):
            anchor = _colony_anchor_for_species(world, species_name, colony_cfg)
            options = SpawnPlacementOptions(
                respect_zones=False,
                use_biome_weight=False,
            )
        else:
            anchor = SpawnAnchor(type="world")
            options = SpawnPlacementOptions(
                respect_zones=True,
                use_biome_weight=True,
            )
        entries.append(
            InitialSpawnEntry(
                species=species_name,
                count=n,
                anchor=anchor,
                options=options,
            )
        )
    return entries


def expand_initial_spawns(world_data: Dict, world: "World") -> List[InitialSpawnEntry]:
    """initial_spawns 設定を InitialSpawnEntry リストへ正規化。"""
    cfg = world_data.get("initial_spawns")
    if not cfg:
        return expand_initial_entities(world_data, world)

    defaults = dict(cfg.get("defaults") or {}) if isinstance(cfg, dict) else {}
    default_options = parse_placement_options(defaults)
    entries: List[InitialSpawnEntry] = []
    if isinstance(cfg, dict):
        groups = list(cfg.get("groups") or [])
    elif isinstance(cfg, list):
        groups = list(cfg)

    for group in groups:
        if not isinstance(group, dict):
            continue
        group_anchor = parse_anchor(group.get("anchor"))
        group_options = parse_placement_options(group.get("placement"), defaults=defaults)
        group_options = _merge_options(default_options, group_options)

        for raw_entry in group.get("entries") or []:
            entries.extend(
                _entries_from_raw(
                    raw_entry, group_anchor, group_options, defaults, inherit_group_options=True
                )
            )

        if "species" in group or "species_pool" in group:
            entries.extend(
                _entries_from_raw(
                    group, group_anchor, group_options, defaults, inherit_group_options=True
                )
            )

    return entries


def _merge_options(
    base: SpawnPlacementOptions,
    override: SpawnPlacementOptions,
) -> SpawnPlacementOptions:
    return SpawnPlacementOptions(
        respect_zones=override.respect_zones,
        use_biome_weight=override.use_biome_weight,
        attempts=override.attempts,
        margin=override.margin,
        nest_exclusion_radius=override.nest_exclusion_radius,
        fallback_unrestricted=override.fallback_unrestricted,
    )


def _entries_from_raw(
    raw: Dict,
    group_anchor: SpawnAnchor,
    group_options: SpawnPlacementOptions,
    defaults: Dict,
    *,
    inherit_group_options: bool = False,
) -> List[InitialSpawnEntry]:
    if not isinstance(raw, dict):
        return []

    species_list: List[str] = []
    if "species" in raw:
        species_list = [str(raw["species"])]
    elif "species_pool" in raw:
        pool = raw["species_pool"]
        if isinstance(pool, str):
            species_list = [pool]
        else:
            species_list = [str(s) for s in pool if s]

    count = max(0, int(raw.get("count", 1)))
    if not species_list or count <= 0:
        return []

    entry_anchor = parse_anchor(raw.get("anchor"))
    if entry_anchor.type == "world" and group_anchor.type != "world":
        entry_anchor = group_anchor
    elif raw.get("anchor") is None:
        entry_anchor = group_anchor

    if raw.get("placement") is not None:
        entry_options = parse_placement_options(raw.get("placement"), defaults=defaults)
        options = _merge_options(group_options, entry_options)
    elif inherit_group_options:
        options = group_options
    else:
        options = parse_placement_options(None, defaults=defaults)

    per_species = int(raw.get("per_species", 0))
    if per_species > 0:
        counts = {name: per_species for name in species_list}
    elif len(species_list) == 1:
        counts = {species_list[0]: count}
    else:
        base, rem = divmod(count, len(species_list))
        counts = {name: base for name in species_list}
        for name in species_list[:rem]:
            counts[name] += 1

    return [
        InitialSpawnEntry(species=name, count=counts[name], anchor=entry_anchor, options=options)
        for name in species_list
        if counts.get(name, 0) > 0
    ]


class SpawnPlacementResolver:
    def __init__(self, world: "World") -> None:
        self.world = world

    def pick(
        self,
        anchor: SpawnAnchor,
        options: SpawnPlacementOptions | None = None,
    ) -> Optional[Tuple[float, float]]:
        opts = options or SpawnPlacementOptions()
        pos = self._pick_best(anchor, opts)
        if pos is not None:
            return pos
        if opts.fallback_unrestricted:
            return self._pick_unrestricted(anchor, opts)
        return None

    def accept_probabilistic(self, x: float, y: float, *, use_biome_weight: bool = True) -> bool:
        zone_system = getattr(self.world, "zone_system", None)
        if zone_system is not None:
            if not zone_system.is_spawn_allowed(x, y):
                return False
            if use_biome_weight:
                return zone_system.accept_probabilistic_spawn(x, y)
            return True
        if not use_biome_weight:
            return True
        mult = self.world.biome.get_spawn_rate_multiplier(x, y)
        if mult <= 0:
            return False
        rich = self.world.biome.get_max_spawn_rate_multiplier()
        if rich <= 0:
            return True
        return random.random() < min(1.0, mult / rich)

    def _pick_best(
        self,
        anchor: SpawnAnchor,
        opts: SpawnPlacementOptions,
    ) -> Optional[Tuple[float, float]]:
        best: Optional[Tuple[float, float, float]] = None
        for _ in range(opts.attempts):
            candidate = self._sample_candidate(anchor, opts)
            if candidate is None:
                continue
            x, y = candidate
            if not self._is_valid_candidate(x, y, opts, anchor):
                continue
            mult = self._score(x, y, opts, anchor)
            if mult <= 0:
                continue
            if best is None or mult > best[2]:
                best = (x, y, mult)
        if best is None:
            return None
        return best[0], best[1]

    def _pick_unrestricted(
        self,
        anchor: SpawnAnchor,
        opts: SpawnPlacementOptions,
    ) -> Tuple[float, float]:
        for _ in range(opts.attempts):
            candidate = self._sample_candidate(anchor, opts)
            if candidate is None:
                continue
            x, y = candidate
            if self.world.is_valid_position(x, y):
                return x, y
        margin = opts.margin
        return (
            float(random.uniform(margin, max(margin, self.world.width - margin))),
            float(random.uniform(margin, max(margin, self.world.height - margin))),
        )

    def _sample_candidate(
        self,
        anchor: SpawnAnchor,
        opts: SpawnPlacementOptions,
    ) -> Optional[Tuple[float, float]]:
        anchor_type = anchor.type
        if anchor_type == "world":
            margin = opts.margin
            x = random.uniform(margin, max(margin, self.world.width - margin))
            y = random.uniform(margin, max(margin, self.world.height - margin))
            return x, y

        if anchor_type == "area":
            radius = max(1.0, anchor.radius)
            angle = random.uniform(0, 2 * math.pi)
            dist = radius * math.sqrt(random.random())
            x = anchor.x + math.cos(angle) * dist
            y = anchor.y + math.sin(angle) * dist
            return self._apply_spread(x, y, anchor.spread)

        if anchor_type == "point":
            return self._apply_spread(anchor.x, anchor.y, anchor.spread)

        if anchor_type in ("nest", "profile_nest"):
            center = self._resolve_nest_center(anchor)
            if center is None:
                return None
            cx, cy = center
            spread = anchor.spread if anchor.spread > 0 else self._default_colony_spread(anchor.colony_id)
            return self._apply_spread(cx, cy, spread)

        return None

    def _resolve_nest_center(self, anchor: SpawnAnchor) -> Optional[Tuple[float, float]]:
        colony_id = anchor.colony_id
        if not colony_id:
            return None

        if anchor.type == "profile_nest":
            return self._profile_nest_center(colony_id)

        nest_system = self.world.nest_system
        nest = nest_system.get_colony_nest(colony_id)
        if nest is not None:
            if nest.holes:
                hole = random.choice(nest.holes)
                return float(hole.x), float(hole.y)
            return float(nest.x), float(nest.y)
        return self._profile_nest_center(colony_id)

    def _profile_nest_center(self, colony_id: str) -> Optional[Tuple[float, float]]:
        from src.sim.utils.colony_config_helpers import get_colony_profile

        profile = get_colony_profile(self.world, colony_id)
        if not profile:
            return self.world.width * 0.5, self.world.height * 0.5
        return float(profile["nest_x"]), float(profile["nest_y"])

    def _default_colony_spread(self, colony_id: str) -> float:
        from src.sim.utils.colony_config_helpers import get_colony_profile

        profile = get_colony_profile(self.world, colony_id)
        return float(profile.get("spawn_spread", 28.0))

    def _apply_spread(self, x: float, y: float, spread: float) -> Tuple[float, float]:
        if spread <= 0:
            return self._clamp_to_world(x, y)
        angle = random.uniform(0, 2 * math.pi)
        dist = random.uniform(0, spread)
        sx = x + math.cos(angle) * dist
        sy = y + math.sin(angle) * dist
        return self._clamp_to_world(sx, sy)

    def _clamp_to_world(self, x: float, y: float) -> Tuple[float, float]:
        margin = 30.0
        x = max(margin, min(self.world.width - margin, x))
        y = max(margin, min(self.world.height - margin, y))
        return x, y

    def _is_valid_candidate(
        self,
        x: float,
        y: float,
        opts: SpawnPlacementOptions,
        anchor: SpawnAnchor | None = None,
    ) -> bool:
        if not self.world.is_valid_position(x, y):
            return False
        if opts.respect_zones:
            zone_system = getattr(self.world, "zone_system", None)
            if zone_system is not None and not zone_system.is_spawn_allowed(x, y):
                return False
        if opts.nest_exclusion_radius > 0 and self._too_close_to_nest(x, y, opts.nest_exclusion_radius):
            return False
        return True

    def _score(
        self,
        x: float,
        y: float,
        opts: SpawnPlacementOptions,
        anchor: SpawnAnchor | None = None,
    ) -> float:
        if anchor is not None and anchor.type in ("nest", "profile_nest"):
            return 1.0
        if not opts.use_biome_weight:
            return 1.0
        zone_system = getattr(self.world, "zone_system", None)
        if zone_system is not None:
            return zone_system.get_spawn_rate_multiplier(x, y)
        return self.world.biome.get_spawn_rate_multiplier(x, y)

    def _too_close_to_nest(self, x: float, y: float, radius: float) -> bool:
        if radius <= 0:
            return False
        nests = getattr(self.world.nest_system, "nests", None) or {}
        for nest in nests.values():
            if (x - nest.x) ** 2 + (y - nest.y) ** 2 < radius * radius:
                return True
        return False

    @staticmethod
    def anchor_from_emitter(emitter, *, is_ambient: bool) -> SpawnAnchor:
        if is_ambient:
            return SpawnAnchor(type="world")
        return SpawnAnchor(
            type="area",
            x=float(emitter.x),
            y=float(emitter.y),
            radius=max(1.0, float(emitter.radius)),
        )

    @staticmethod
    def options_from_emitter(emitter) -> SpawnPlacementOptions:
        return SpawnPlacementOptions(
            respect_zones=True,
            use_biome_weight=bool(emitter.use_biome_weight),
            attempts=max(1, int(emitter.position_attempts)),
            margin=max(0, int(emitter.margin)),
            nest_exclusion_radius=max(0.0, float(emitter.nest_exclusion_radius)),
        )
