"""Uniform spatial grid for creature proximity queries."""
from __future__ import annotations

import math
from typing import Any, Iterable, Iterator, Optional

from src.sim.utils.position_helpers import entity_xy

DEFAULT_CELL_SIZE = 64.0


class SpatialGrid:
    """Axis-aligned uniform grid indexing world.creatures by position."""

    def __init__(
        self,
        width: float,
        height: float,
        cell_size: float = DEFAULT_CELL_SIZE,
    ) -> None:
        self.width = float(width)
        self.height = float(height)
        self.cell_size = max(16.0, float(cell_size))
        self._cols = max(1, math.ceil(self.width / self.cell_size))
        self._rows = max(1, math.ceil(self.height / self.cell_size))
        self._cells: list[list[Any]] = [[] for _ in range(self._cols * self._rows)]

    def rebuild(self, creatures: Iterable[Any]) -> None:
        """Re-index all creatures (call once per sim phase that needs fresh positions)."""
        for cell in self._cells:
            cell.clear()

        cs = self.cell_size
        cols = self._cols
        cells = self._cells
        for creature in creatures:
            x, y = entity_xy(creature)
            col = int(x // cs)
            row = int(y // cs)
            if col < 0:
                col = 0
            elif col >= cols:
                col = cols - 1
            max_row = self._rows - 1
            if row < 0:
                row = 0
            elif row > max_row:
                row = max_row
            cells[row * cols + col].append(creature)

    def iter_in_radius(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        alive_only: Optional[bool] = None,
    ) -> Iterator[Any]:
        """Yield creatures whose center is within radius of (x, y)."""
        if radius <= 0:
            return

        r = float(radius)
        cs = self.cell_size
        min_col = max(0, int((x - r) // cs))
        max_col = min(self._cols - 1, int((x + r) // cs))
        min_row = max(0, int((y - r) // cs))
        max_row = min(self._rows - 1, int((y + r) // cs))
        r2 = r * r
        cols = self._cols
        cells = self._cells

        for row in range(min_row, max_row + 1):
            base = row * cols
            for col in range(min_col, max_col + 1):
                for creature in cells[base + col]:
                    if alive_only is True and not getattr(creature, "alive", True):
                        continue
                    if alive_only is False and getattr(creature, "alive", True):
                        continue
                    ox, oy = entity_xy(creature)
                    dx = ox - x
                    dy = oy - y
                    if dx * dx + dy * dy <= r2:
                        yield creature


def iter_creatures_in_radius(
    world: Any,
    x: float,
    y: float,
    radius: float,
    *,
    alive_only: Optional[bool] = None,
) -> Iterator[Any]:
    """Spatial-grid query with linear fallback when grid is unavailable."""
    grid = getattr(world, "spatial_grid", None)
    if (
        isinstance(grid, SpatialGrid)
        and getattr(world, "_spatial_grid_valid", False)
    ):
        yield from grid.iter_in_radius(x, y, radius, alive_only=alive_only)
        return

    if radius <= 0:
        return
    r2 = radius * radius
    for creature in world.creatures:
        if alive_only is True and not getattr(creature, "alive", True):
            continue
        if alive_only is False and getattr(creature, "alive", True):
            continue
        ox, oy = entity_xy(creature)
        dx = ox - x
        dy = oy - y
        if dx * dx + dy * dy <= r2:
            yield creature
