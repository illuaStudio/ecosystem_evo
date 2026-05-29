# world.py
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.config import config
from src.utils.position_helpers import entity_xy
from src.systems.mana_system import ManaSystem
from src.systems.movement_system import MovementSystem
from src.systems.world_biome import WorldBiome
from src.systems.world_mana import WorldMana
from src.systems.nest_system import NestSystem
from src.systems.world_spawner import WorldSpawner


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
        worlds_dir = config.base_path / "worlds"
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
        self.name = world_data["name"]
        self.display_name = world_data.get("display_name", self.name)
        self.width = int(world_data["world_width"])
        self.height = int(world_data["world_height"])
        self.background_color = tuple(world_data.get("background_color", [34, 60, 25]))

        env = world_data.get("environment", {})
        self.temperature = float(env.get("temperature", 20.0))
        self.humidity = float(env.get("humidity", 50.0))

        self.creatures: List = []
        self.obstacles = []
        self.resources = []
        self.movement_system = MovementSystem()
        self.mana_system = ManaSystem()

        self.biome = WorldBiome(self)
        self.biome.init_from_config(world_data.get("world", {}))

        self.mana_layer = WorldMana(self)
        self.mana_layer.init_from_config(world_data.get("mana", {}))

        self.population_limits = normalize_population_limits(
            world_data.get("population_limits", {})
        )

        colony_block = dict(world_data.get("colony", {}))
        self.faction_styles = dict(colony_block.pop("factions", {}))
        self.faction_species = dict(colony_block.pop("faction_species", {}))
        self.colony_settings = colony_block

        self.nest_system = NestSystem(self)
        self.spawner = WorldSpawner(self)
        self.spawner.spawn_initial_entities(world_data)
        self.sim_dt = 1.0

    def get_population_cap(self, species_name: str) -> Optional[int]:
        """種族のワールド個体数上限。未設定なら None。"""
        return self.population_limits.get(species_name)

    # バイオーム（後方互換）
    biomes = property(lambda s: s.biome.biomes)
    biome_by_name = property(lambda s: s.biome.biome_by_name)
    biome_cell_size = property(lambda s: s.biome.biome_cell_size)
    biome_noise = property(lambda s: s.biome.biome_noise)
    biome_color_grid = property(lambda s: s.biome.biome_color_grid)
    avg_mana_regen_multiplier = property(lambda s: s.biome.avg_mana_regen_multiplier)

    def get_biome_at(self, x: float, y: float) -> Dict:
        return self.biome.get_biome_at(x, y)

    def get_biome_color_at(self, x: float, y: float) -> Tuple[int, int, int]:
        return self.biome.get_biome_color_at(x, y)

    def get_mana_regen_multiplier(self, x: float, y: float) -> float:
        return self.biome.get_mana_regen_multiplier(x, y)

    # マナ（後方互換）
    mana_regen_rate = property(lambda s: s.mana_layer.regen_rate)
    mana_cell_size = property(lambda s: s.mana_layer.mana_cell_size)
    mana_density_cap = property(lambda s: s.mana_layer.mana_density_cap)
    mana_density = property(lambda s: s.mana_layer.mana_density)
    max_mana = property(lambda s: s.mana_layer.max_mana)
    _mana_cols = property(lambda s: s.mana_layer._mana_cols)
    _mana_rows = property(lambda s: s.mana_layer._mana_rows)

    @property
    def mana(self) -> float:
        return self.mana_layer.mana

    @mana.setter
    def mana(self, value: float) -> None:
        self.mana_layer.mana = value

    def get_mana_density(self, x: float, y: float) -> float:
        return self.mana_layer.get_mana_density(x, y)

    def _regenerate_mana_density(self, dt: float = 1.0) -> None:
        self.mana_layer.regenerate(dt)

    def return_mana_from_decomposition(
        self, amount: float, x: float = None, y: float = None
    ) -> None:
        self.mana_layer.return_from_decomposition(amount, x, y)

    def consume_mana(self, amount: float, x: float = None, y: float = None) -> float:
        return self.mana_layer.consume(amount, x, y)

    def add_creature(self, creature) -> None:
        creature.world = self
        self.creatures.append(creature)
        if getattr(creature, "colony", None) is not None:
            self.nest_system.assign_creature(
                creature, creature.species.colony_data
            )

    def remove_creature(self, creature) -> None:
        if creature in self.creatures:
            self.creatures.remove(creature)

    def update(self, dt: float = 1.0) -> None:
        """生態シミュレーションを dt 分進める（1 = 旧来の 1 シミュ tick）。"""
        self.sim_dt = float(dt)
        self._regenerate_mana_density(dt)
        self.nest_system.update(dt)
        for creature in self.creatures[:]:
            creature.update(dt)
        self.movement_system.update(self.creatures, self, dt)
        self.mana_system.update(self.creatures, self, dt)
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
        for c in self.creatures:
            if c is exclude or not getattr(c, "alive", True):
                continue
            if species_name and c.species.name != species_name:
                continue
            cx, cy = entity_xy(c)
            dist = math.hypot(cx - pos[0], cy - pos[1])
            if dist < min_dist and dist <= max_dist:
                min_dist = dist
                best = c
        return best

    def is_valid_position(self, x: float, y: float) -> bool:
        return 30 <= x <= self.width - 30 and 30 <= y <= self.height - 30
