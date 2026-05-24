# world.py
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from src.config import config
from src.entities.creature_factory import CreatureFactory
from src.systems.biome_noise import BiomeNoise


def _parse_color(value) -> Tuple[int, int, int]:
    """'#RRGGBB' または [r,g,b] を pygame 用 RGB タプルに変換。"""
    if isinstance(value, str):
        s = value.strip().lstrip("#")
        if len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    return (34, 60, 25)


class World:
    """ゲーム世界全体を管理。設定は config/worlds/*.json から読み込む。

    world.json のバイオーム例（world セクション）:
        "world": {
          "biome_map_cell_size": 16,
          "biomes": [
            { "name": "rich", "color": "#2E8B57", "mana_regen_multiplier": 1.4 },
            { "name": "poor", "color": "#8F9E6E", "mana_regen_multiplier": 0.6 }
          ],
          "biome_noise": {
            "scale": 0.018, "octaves": 4, "persistence": 0.55,
            "lacunarity": 2.2, "threshold": 0.5, "seed": 42
          }
        }

    初期化:
        world = World("Grassland")
        biome = world.get_biome_at(120, 80)
        mult = world.get_mana_regen_multiplier(120, 80)
    """

    def __init__(self, world_name: str = "Grassland"):
        # config.get_world は reload_worlds() 後の最新 JSON を参照する
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

        mana_cfg = world_data.get("mana", {})
        self.mana = float(mana_cfg.get("initial", 5000.0))
        self.max_mana = float(mana_cfg.get("max", self.mana))
        self.mana_regen_rate = float(mana_cfg.get("regen_rate", 0.0))
        self.mana = min(self.mana, self.max_mana)

        env = world_data.get("environment", {})
        self.temperature = float(env.get("temperature", 20.0))
        self.humidity = float(env.get("humidity", 50.0))

        self.creatures: List = []
        self.obstacles = []
        self.resources = []

        self._init_biomes(world_data.get("world", {}))
        self._spawn_initial_entities(world_data)

    def _init_biomes(self, world_cfg: Dict) -> None:
        """ノイズマップとバイオーム定義を構築（Renderer 用グリッドも生成）。"""
        self.biomes: List[Dict] = list(world_cfg.get("biomes", []))
        self.biome_by_name: Dict[str, Dict] = {b["name"]: b for b in self.biomes if "name" in b}
        self.biome_cell_size = int(world_cfg.get("biome_map_cell_size", 16))

        self.biome_noise: Optional[BiomeNoise] = None
        self._rich_biome: Optional[Dict] = None
        self._poor_biome: Optional[Dict] = None
        self.biome_color_grid: List[List[Tuple[int, int, int]]] = []

        self.avg_mana_regen_multiplier = 1.0
        if len(self.biomes) < 2:
            return

        if "biome_noise" not in world_cfg:
            raise ValueError("world.biome_noise が world.json に定義されていません")
        self.biome_noise = BiomeNoise.from_config(world_cfg["biome_noise"])

        self._rich_biome = self.biome_by_name.get("rich", self.biomes[0])
        self._poor_biome = self.biome_by_name.get("poor", self.biomes[-1])
        self._build_biome_color_grid()
        self.avg_mana_regen_multiplier = self._compute_average_mana_multiplier()

    def _build_biome_color_grid(self) -> None:
        """描画用: セル単位でバイオーム色を事前計算。"""
        cell = max(4, self.biome_cell_size)
        cols = math.ceil(self.width / cell)
        rows = math.ceil(self.height / cell)
        self.biome_color_grid = []

        for row in range(rows):
            row_colors = []
            cy = row * cell + cell * 0.5
            for col in range(cols):
                cx = col * cell + cell * 0.5
                biome = self.get_biome_at(cx, cy)
                row_colors.append(_parse_color(biome.get("color", self.background_color)))
            self.biome_color_grid.append(row_colors)

    def _compute_average_mana_multiplier(self) -> float:
        """全セルのバイオーム倍率の平均（共有マナ池の自然回復用）。"""
        if not self.biome_color_grid:
            return 1.0
        cell = self.biome_cell_size
        total = 0.0
        count = 0
        for row in range(len(self.biome_color_grid)):
            for col in range(len(self.biome_color_grid[row])):
                cx = col * cell + cell * 0.5
                cy = row * cell + cell * 0.5
                total += self.get_mana_regen_multiplier(cx, cy)
                count += 1
        return total / count if count else 1.0

    def get_biome_at(self, x: float, y: float) -> Dict:
        """座標のバイオーム定義 dict を返す（name, color, mana_regen_multiplier 等）。"""
        if not self.biomes or self.biome_noise is None or self._rich_biome is None:
            return {
                "name": "default",
                "display_name": "通常",
                "color": self.background_color,
                "mana_regen_multiplier": 1.0,
            }

        biome_type = self.biome_noise.get_biome_type(x, y)
        if biome_type == "rich":
            return self._rich_biome
        return self._poor_biome

    def get_biome_color_at(self, x: float, y: float) -> Tuple[int, int, int]:
        """座標の地面色（RGB）。"""
        biome = self.get_biome_at(x, y)
        return _parse_color(biome.get("color", self.background_color))

    def get_mana_regen_multiplier(self, x: float, y: float) -> float:
        """座標におけるマナ自然回復の倍率。"""
        return float(self.get_biome_at(x, y).get("mana_regen_multiplier", 1.0))

    def _spawn_initial_entities(self, world_data: Dict) -> None:
        initial = dict(world_data.get("initial_entities", {}))

        if not initial:
            if world_data.get("initial_amoeba"):
                initial["Amoeba"] = world_data["initial_amoeba"]
            if world_data.get("initial_predator"):
                initial["Predator"] = world_data["initial_predator"]

        factory = CreatureFactory()
        for species_name, count in initial.items():
            n = int(count)
            if n <= 0:
                continue
            if species_name not in config.species:
                print(f"警告: 種族 '{species_name}' の JSON が無いためスキップします")
                continue
            for _ in range(n):
                self.add_creature(factory.create(species_name, world=self))

    def add_creature(self, creature) -> None:
        creature.world = self
        self.creatures.append(creature)

    def remove_creature(self, creature) -> None:
        if creature in self.creatures:
            self.creatures.remove(creature)

    def return_mana_from_decomposition(self, amount: float) -> None:
        if amount > 0:
            self.mana = min(self.max_mana, self.mana + amount)

    def consume_mana(self, amount: float) -> float:
        if amount <= 0 or self.mana <= 0:
            return 0.0
        taken = min(amount, self.mana)
        self.mana -= taken
        return taken

    def update(self) -> None:
        if self.mana_regen_rate > 0 and self.mana < self.max_mana:
            mult = getattr(self, "avg_mana_regen_multiplier", 1.0)
            self.mana = min(
                self.max_mana,
                self.mana + self.mana_regen_rate * mult,
            )

        for creature in self.creatures[:]:
            creature.update()
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
            dist = math.hypot(c.pos[0] - pos[0], c.pos[1] - pos[1])
            if dist < min_dist and dist <= max_dist:
                min_dist = dist
                best = c
        return best

    def is_valid_position(self, x: float, y: float) -> bool:
        return 30 <= x <= self.width - 30 and 30 <= y <= self.height - 30
