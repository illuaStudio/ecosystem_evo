# world.py
import json
import math
import random
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
        density = world.get_mana_density(120, 80)
        world.consume_mana(0.75, 120, 80)
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
        self.mana_regen_rate = float(mana_cfg.get("regen_rate", 0.0))

        env = world_data.get("environment", {})
        self.temperature = float(env.get("temperature", 20.0))
        self.humidity = float(env.get("humidity", 50.0))

        self.creatures: List = []
        self.obstacles = []
        self.resources = []

        self._init_biomes(world_data.get("world", {}))
        self._init_mana_density(mana_cfg)
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

    def _init_mana_density(self, mana_cfg: Dict) -> None:
        """座標ごとのマナ残量マップ（2D）を初期化する。"""
        self.mana_cell_size = int(
            mana_cfg.get("cell_size", getattr(self, "biome_cell_size", 16))
        )
        self.mana_density_cap = float(mana_cfg.get("density_max", 2500.0))
        initial_min = float(mana_cfg.get("density_initial_min", 800.0))
        initial_max = float(mana_cfg.get("density_initial_max", 1500.0))

        cell = max(4, self.mana_cell_size)
        self._mana_cols = math.ceil(self.width / cell)
        self._mana_rows = math.ceil(self.height / cell)

        seed = self.biome_noise.seed if self.biome_noise else 42
        rng = random.Random(seed)

        self.mana_density: List[List[float]] = []
        for row in range(self._mana_rows):
            row_data: List[float] = []
            cy = row * cell + cell * 0.5
            for col in range(self._mana_cols):
                cx = col * cell + cell * 0.5
                mult = self.get_mana_regen_multiplier(cx, cy)
                base = rng.uniform(initial_min, initial_max)
                row_data.append(min(self.mana_density_cap, base * (0.85 + 0.15 * mult)))
            self.mana_density.append(row_data)

        self.mana = self._compute_total_mana()
        self.max_mana = self._mana_cols * self._mana_rows * self.mana_density_cap

    def _pos_to_mana_cell(self, x: float, y: float) -> Tuple[int, int]:
        cell = self.mana_cell_size
        col = int(x // cell)
        row = int(y // cell)
        col = max(0, min(self._mana_cols - 1, col))
        row = max(0, min(self._mana_rows - 1, row))
        return col, row

    def _compute_total_mana(self) -> float:
        if not self.mana_density:
            return 0.0
        return sum(sum(row) for row in self.mana_density)

    def get_mana_density(self, x: float, y: float) -> float:
        """座標におけるマナ残量（セル単位）。"""
        if not self.mana_density:
            return 0.0
        col, row = self._pos_to_mana_cell(x, y)
        return self.mana_density[row][col]

    def _regenerate_mana_density(self) -> None:
        """バイオーム倍率に基づき、マナ密度マップ全体を回復させる。"""
        if self.mana_regen_rate <= 0 or not self.mana_density:
            return

        cell_count = self._mana_cols * self._mana_rows
        base_per_cell = self.mana_regen_rate / cell_count
        cell = self.mana_cell_size
        cap = self.mana_density_cap
        regen_total = 0.0

        for row in range(self._mana_rows):
            cy = row * cell + cell * 0.5
            for col in range(self._mana_cols):
                current = self.mana_density[row][col]
                if current >= cap:
                    continue
                cx = col * cell + cell * 0.5
                mult = self.get_mana_regen_multiplier(cx, cy)
                delta = base_per_cell * mult
                new_value = min(cap, current + delta)
                regen_total += new_value - current
                self.mana_density[row][col] = new_value

        self.mana += regen_total

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

    def return_mana_from_decomposition(
        self, amount: float, x: float = None, y: float = None
    ) -> None:
        if amount <= 0 or not self.mana_density:
            return
        if x is None:
            x = self.width * 0.5
        if y is None:
            y = self.height * 0.5

        col, row = self._pos_to_mana_cell(x, y)
        current = self.mana_density[row][col]
        added = min(amount, self.mana_density_cap - current)
        if added <= 0:
            return
        self.mana_density[row][col] = current + added
        self.mana += added

    def consume_mana(
        self, amount: float, x: float = None, y: float = None
    ) -> float:
        """指定位置のマナを消費する。x/y 省略時は世界中心から吸収（後方互換）。"""
        if amount <= 0:
            return 0.0

        if self.mana_density:
            if x is None:
                x = self.width * 0.5
            if y is None:
                y = self.height * 0.5

            col, row = self._pos_to_mana_cell(x, y)
            available = self.mana_density[row][col]
            if available <= 0:
                return 0.0
            taken = min(amount, available)
            self.mana_density[row][col] -= taken
            self.mana -= taken
            return taken

        # フォールバック: 旧来の共有プール
        if self.mana <= 0:
            return 0.0
        taken = min(amount, self.mana)
        self.mana -= taken
        return taken

    def update(self) -> None:
        self._regenerate_mana_density()

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
