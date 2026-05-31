# world.py
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.config import config
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.spatial_grid import SpatialGrid, iter_creatures_in_radius
from src.sim.utils.field_effect_cache import FieldEffectCache, invalidate_field_effect_cache
from src.sim.systems.movement_system import MovementSystem
from src.sim.systems.world_biome import WorldBiome
from src.sim.systems.zone_system import ZoneSystem
from src.sim.systems.obstacle_system import ObstacleSystem
from src.sim.systems.nest_system import NestSystem
from src.sim.event_bus import EventBus
from src.sim.systems.spawn_system import SpawnSystem
from src.sim.systems.world_spawner import WorldSpawner
from src.sim.utils.object_type_loader import merge_zone_config
from src.sim.systems.world_object_system import WorldObjectSystem
from src.sim.utils.world_instances import normalize_world_layout


def normalize_population_limits(raw: Dict) -> Dict[str, int]:
    """ワールド JSON の population_limits を正の整数 dict に正規化。"""
    out: Dict[str, int] = {}
    for name, cap in (raw or {}).items():
        try:
            n = int(cap)
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[str(name)] = n
    return out


class World:
    """ゲーム世界全体を管理。設定は config/worlds/*.json から読み込む。"""

    def __init__(self, world_name: str = "Grassland"):
        world_data = config.get_world(world_name) or self._load_world_file(world_name)
        if not world_data:
            raise ValueError(
                f"ワールド '{world_name}' が見つかりません。"
                f" config/worlds/*.json を確認してください。"
            )
        self._init_from_data(world_data)

    @staticmethod
    def _load_world_file(world_name: str) -> Optional[Dict]:
        worlds_dir = config.base_path / "sim" / "worlds"
        for candidate in (
            worlds_dir / f"{world_name}.json",
            worlds_dir / f"{world_name.lower()}.json",
            worlds_dir / "world.json",
        ):
            if candidate.exists():
                with open(candidate, encoding="utf-8") as f:
                    return json.load(f)
        return None

    @classmethod
    def from_json(cls, source: Union[str, Path, Dict]) -> "World":
        if isinstance(source, dict):
            world = cls.__new__(cls)
            world._init_from_data(source)
            return world
        path = Path(source)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_json(data)

    def _init_from_data(self, world_data: Dict) -> None:
        layout = normalize_world_layout(world_data)
        self.name = layout["name"]
        self.display_name = layout.get("display_name", self.name)
        self.width = int(layout["world_width"])
        self.height = int(layout["world_height"])
        self.background_color = tuple(layout.get("background_color", [34, 60, 25]))

        env = layout.get("environment", {})
        self.temperature = float(env.get("temperature", 20.0))
        self.humidity = float(env.get("humidity", 50.0))

        self.creatures: List = []
        self._alive_species_counts: Dict[str, int] = {}
        self.spatial_grid = SpatialGrid(self.width, self.height)
        self._spatial_grid_valid = False
        self.field_effect_cache = FieldEffectCache(self)
        self.resources = []
        self.movement_system = MovementSystem()

        self.biome = WorldBiome(self)
        self.biome.init_from_config(layout.get("world", {}))

        self.population_limits = normalize_population_limits(
            layout.get("population_limits", {})
        )

        colony_block = dict(layout.get("colony", {}))
        self.faction_styles = dict(colony_block.pop("factions", {}))
        self.faction_species = dict(colony_block.pop("faction_species", {}))
        self.colony_profiles = {
            str(k): dict(v)
            for k, v in (colony_block.pop("profiles", {}) or {}).items()
        }
        self.colony_settings = colony_block
        self.defeated_colonies: set[str] = set()
        self.last_defeat_message: str = ""
        self.events = EventBus()
        self._combat_pairs_this_tick: set[tuple] = set()

        self.nest_system = NestSystem(self)
        self.world_object_system = WorldObjectSystem(self)
        self.world_object_system.init_from_layout(layout)
        self.nest_system.bootstrap_from_world_objects()
        self.zone_system = ZoneSystem(self)
        self.zone_system.init_from_config(
            merge_zone_config(layout.get("zones")),
            legacy_field_emitters=layout.get("field_emitters"),
            colony_profiles=self.colony_profiles,
        )
        self.obstacle_system = ObstacleSystem(self)
        self.obstacle_system.init_from_layout(layout)
        self.spawner = WorldSpawner(self)
        self.spawn_system = SpawnSystem(self)
        self.spawn_system.init_from_config(
            layout.get("spawn_emitters"),
            legacy_ambient=layout.get("ambient_spawns"),
        )
        self.spawner.spawn_initial_entities(layout)
        self.field_effect_cache.rebuild()
        self.sim_dt = 1.0

    @property
    def ambient_spawner(self):
        """後方互換: Phase 1 の AmbientSpawner 参照。"""
        return self.spawn_system

    def get_population_cap(self, species_name: str) -> Optional[int]:
        """種族のワールド個体数上限。未設定なら None。"""
        return self.population_limits.get(species_name)

    def count_alive_by_species(self, species_name: str) -> int:
        """生存個体数（O(1) キャッシュ）。"""
        return self._alive_species_counts.get(species_name, 0)

    def _adjust_alive_species_count(self, species_name: str, delta: int) -> None:
        if not species_name or delta == 0:
            return
        counts = self._alive_species_counts
        new_val = counts.get(species_name, 0) + delta
        if new_val <= 0:
            counts.pop(species_name, None)
        else:
            counts[species_name] = new_val

    def on_creature_became_corpse(self, creature) -> None:
        """死亡→死骸化時に生存カウントを減らす。"""
        self._adjust_alive_species_count(creature.species.name, -1)

    def rebuild_spatial_grid(self) -> None:
        self.spatial_grid.rebuild(self.creatures)
        self._spatial_grid_valid = True

    def add_creature(
        self,
        creature,
        *,
        spawn_source: str = "spawn",
        parent=None,
    ) -> None:
        creature.world = self
        self.creatures.append(creature)
        self._spatial_grid_valid = False
        if getattr(creature, "alive", True):
            self._adjust_alive_species_count(creature.species.name, 1)
        if getattr(creature, "colony", None) is not None:
            self.nest_system.assign_creature(
                creature, creature.species.colony_data
            )
        from src.sim.utils.spawn_helpers import apply_creature_spawn_state

        apply_creature_spawn_state(creature)

        from src.sim.emitters import emit_spawn
        from src.sim.events import SpawnSource

        source: SpawnSource = spawn_source  # type: ignore[assignment]
        emit_spawn(self, creature, source=source, parent=parent)

    def remove_creature(self, creature) -> None:
        if creature in self.creatures:
            if getattr(creature, "alive", True):
                self._adjust_alive_species_count(creature.species.name, -1)
            self.creatures.remove(creature)
            self._spatial_grid_valid = False

    def update(self, dt: float = 1.0) -> None:
        """生態シミュレーションを dt 分進める（1 = 旧来の 1 シミュ tick）。"""
        self.sim_dt = float(dt)
        self._combat_pairs_this_tick = set()
        self.spawn_system.update(dt)
        self.nest_system.update(dt)
        self.rebuild_spatial_grid()
        for creature in self.creatures[:]:
            creature.update(dt)
        self.movement_system.update(self.creatures, self, dt)
        self.rebuild_spatial_grid()
        for creature in self.creatures[:]:
            if creature.is_dead():
                self.remove_creature(creature)

    def get_nearest_creature(
        self,
        pos: Tuple[float, float],
        species_name: str = None,
        max_dist: float = 9999.0,
        exclude=None,
    ):
        best = None
        min_dist = float("inf")
        px, py = pos[0], pos[1]
        for c in iter_creatures_in_radius(self, px, py, max_dist, alive_only=True):
            if c is exclude:
                continue
            if species_name and c.species.name != species_name:
                continue
            cx, cy = entity_xy(c)
            dist = math.hypot(cx - px, cy - py)
            if dist < min_dist:
                min_dist = dist
                best = c
        return best

    def is_valid_position(self, x: float, y: float, body_radius: float = 0.0) -> bool:
        margin = 30.0
        if not (margin <= x <= self.width - margin and margin <= y <= self.height - margin):
            return False
        return self.obstacle_system.is_walkable(x, y, body_radius)

    def resolve_creature_position(self, creature, x: float, y: float) -> tuple[float, float]:
        """ワールド端クランプ後、障害物から押し出した座標を返す。"""
        from src.sim.utils.stats_helpers import current_size

        margin = 30.0
        px = max(margin, min(self.width - margin, float(x)))
        py = max(margin, min(self.height - margin, float(y)))
        body_radius = max(1.0, float(current_size(creature)))
        return self.obstacle_system.resolve_position(px, py, body_radius)
