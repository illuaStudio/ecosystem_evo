"""バイオーム・ノイズマップ・描画用カラーグリッドを担当。"""
import math
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from src.sim.systems.biome_noise import BiomeNoise

if TYPE_CHECKING:
    from src.sim.systems.world import World


def parse_color(value) -> Tuple[int, int, int]:
    """'#RRGGBB' または [r,g,b] を pygame 用 RGB タプルに変換。"""
    if isinstance(value, str):
        s = value.strip().lstrip("#")
        if len(s) == 6:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (int(value[0]), int(value[1]), int(value[2]))
    return (34, 60, 25)


class WorldBiome:
    def __init__(self, world: "World") -> None:
        self._world = world
        self.biomes: List[Dict] = []
        self.biome_by_name: Dict[str, Dict] = {}
        self.biome_cell_size = 16
        self.biome_noise: Optional[BiomeNoise] = None
        self._rich_biome: Optional[Dict] = None
        self._poor_biome: Optional[Dict] = None
        self.biome_color_grid: List[List[Tuple[int, int, int]]] = []
        self._max_spawn_rate_multiplier = 1.0

    def init_from_config(self, world_cfg: Dict) -> None:
        """ノイズマップとバイオーム定義を構築（Renderer 用グリッドも生成）。"""
        self.biomes = list(world_cfg.get("biomes", []))
        self.biome_by_name = {b["name"]: b for b in self.biomes if "name" in b}
        self.biome_cell_size = int(world_cfg.get("biome_map_cell_size", 16))

        self.biome_noise = None
        self._rich_biome = None
        self._poor_biome = None
        self.biome_color_grid = []
        self._max_spawn_rate_multiplier = 1.0

        if len(self.biomes) < 2:
            return

        if "biome_noise" not in world_cfg:
            raise ValueError("world.biome_noise が world.json に定義されていません")
        self.biome_noise = BiomeNoise.from_config(world_cfg["biome_noise"])

        self._rich_biome = self.biome_by_name.get("rich", self.biomes[0])
        self._poor_biome = self.biome_by_name.get("poor", self.biomes[-1])
        self._build_biome_color_grid()
        self._max_spawn_rate_multiplier = self._compute_max_spawn_rate_multiplier()

    def _build_biome_color_grid(self) -> None:
        """描画用: セル単位でバイオーム色を事前計算。"""
        world = self._world
        cell = max(4, self.biome_cell_size)
        cols = math.ceil(world.width / cell)
        rows = math.ceil(world.height / cell)
        self.biome_color_grid = []

        for row in range(rows):
            row_colors = []
            cy = row * cell + cell * 0.5
            for col in range(cols):
                cx = col * cell + cell * 0.5
                biome = self.get_biome_at(cx, cy)
                row_colors.append(parse_color(biome.get("color", world.background_color)))
            self.biome_color_grid.append(row_colors)

    def get_biome_at(self, x: float, y: float) -> Dict:
        """座標のバイオーム定義 dict を返す。"""
        world = self._world
        if not self.biomes or self.biome_noise is None or self._rich_biome is None:
            return {
                "name": "default",
                "display_name": "通常",
                "color": world.background_color,
            }

        biome_type = self.biome_noise.get_biome_type(x, y)
        if biome_type == "rich":
            return self._rich_biome
        return self._poor_biome

    def get_biome_color_at(self, x: float, y: float) -> Tuple[int, int, int]:
        """座標の地面色（RGB）。"""
        biome = self.get_biome_at(x, y)
        return parse_color(biome.get("color", self._world.background_color))

    def _compute_max_spawn_rate_multiplier(self) -> float:
        if not self.biomes:
            return 1.0
        values = [float(b.get("spawn_rate_multiplier", 1.0)) for b in self.biomes]
        return max(values) if values else 1.0

    def get_max_spawn_rate_multiplier(self) -> float:
        """バイオーム定義上の最大スポーン倍率。"""
        return self._max_spawn_rate_multiplier

    def get_spawn_rate_multiplier(self, x: float, y: float) -> float:
        """座標における環境スポーンの倍率。"""
        biome = self.get_biome_at(x, y)
        return float(biome.get("spawn_rate_multiplier", 1.0))
