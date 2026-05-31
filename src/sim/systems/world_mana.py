"""マナ密度マップ・消費・回復・分解還元を担当。"""
import math
import random
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from src.sim.systems.world import World


class WorldMana:
    def __init__(self, world: "World") -> None:
        self._world = world
        self.regen_rate = 0.0
        self.mana_cell_size = 16
        self.mana_density_cap = 2500.0
        self.mana_density: List[List[float]] = []
        self.mana = 0.0
        self.max_mana = 0.0
        self._mana_cols = 0
        self._mana_rows = 0
        self._regen_multiplier_grid: List[List[float]] = []

    def init_from_config(self, mana_cfg: Dict) -> None:
        """座標ごとのマナ残量マップ（2D）を初期化する。"""
        world = self._world
        self.regen_rate = float(mana_cfg.get("regen_rate", 0.0))
        self.mana_cell_size = int(
            mana_cfg.get("cell_size", getattr(world.biome, "biome_cell_size", 16))
        )
        self.mana_density_cap = float(mana_cfg.get("density_max", 2500.0))
        initial_min = float(mana_cfg.get("density_initial_min", 800.0))
        initial_max = float(mana_cfg.get("density_initial_max", 1500.0))

        cell = max(4, self.mana_cell_size)
        self._mana_cols = math.ceil(world.width / cell)
        self._mana_rows = math.ceil(world.height / cell)

        biome_noise = world.biome.biome_noise
        seed = biome_noise.seed if biome_noise else 42
        rng = random.Random(seed)

        self.mana_density = []
        self._regen_multiplier_grid = []
        for row in range(self._mana_rows):
            row_data: List[float] = []
            mult_row: List[float] = []
            cy = row * cell + cell * 0.5
            for col in range(self._mana_cols):
                cx = col * cell + cell * 0.5
                mult = world.biome.get_mana_regen_multiplier(cx, cy)
                mult_row.append(mult)
                base = rng.uniform(initial_min, initial_max)
                row_data.append(min(self.mana_density_cap, base * (0.85 + 0.15 * mult)))
            self.mana_density.append(row_data)
            self._regen_multiplier_grid.append(mult_row)

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

    def regenerate(self, dt: float = 1.0) -> None:
        """バイオーム倍率に基づき、マナ密度マップ全体を回復させる。"""
        if self.regen_rate <= 0 or not self.mana_density or dt <= 0:
            return

        cell_count = self._mana_cols * self._mana_rows
        base_per_cell = (self.regen_rate / cell_count) * float(dt)
        cap = self.mana_density_cap
        regen_total = 0.0
        mult_grid = self._regen_multiplier_grid

        for row in range(self._mana_rows):
            density_row = self.mana_density[row]
            mult_row = mult_grid[row]
            for col in range(self._mana_cols):
                current = density_row[col]
                if current >= cap:
                    continue
                delta = base_per_cell * mult_row[col]
                new_value = min(cap, current + delta)
                regen_total += new_value - current
                density_row[col] = new_value

        self.mana += regen_total

    def return_from_decomposition(
        self, amount: float, x: float = None, y: float = None
    ) -> None:
        if amount <= 0 or not self.mana_density:
            return
        world = self._world
        if x is None:
            x = world.width * 0.5
        if y is None:
            y = world.height * 0.5

        col, row = self._pos_to_mana_cell(x, y)
        current = self.mana_density[row][col]
        added = min(amount, self.mana_density_cap - current)
        if added <= 0:
            return
        self.mana_density[row][col] = current + added
        self.mana += added

    def consume(self, amount: float, x: float = None, y: float = None) -> float:
        """指定位置のマナを消費する。x/y 省略時は世界中心から吸収（後方互換）。"""
        if amount <= 0:
            return 0.0

        world = self._world
        if self.mana_density:
            if x is None:
                x = world.width * 0.5
            if y is None:
                y = world.height * 0.5

            col, row = self._pos_to_mana_cell(x, y)
            available = self.mana_density[row][col]
            if available <= 0:
                return 0.0
            taken = min(amount, available)
            self.mana_density[row][col] -= taken
            self.mana -= taken
            return taken

        if self.mana <= 0:
            return 0.0
        taken = min(amount, self.mana)
        self.mana -= taken
        return taken
