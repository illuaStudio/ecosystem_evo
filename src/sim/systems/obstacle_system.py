"""静的障害物（円・軸平行矩形）の配置と歩行可否判定。"""
from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from src.sim.systems.world import World

DEFAULT_CELL_SIZE = 128.0
DEFAULT_SPAWN_BODY_RADIUS = 5.0


def _parse_color(raw: Any, default: Tuple[int, int, int]) -> Tuple[int, int, int]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        return (
            max(0, min(255, int(raw[0]))),
            max(0, min(255, int(raw[1]))),
            max(0, min(255, int(raw[2]))),
        )
    if isinstance(raw, str) and raw.startswith("#") and len(raw) >= 7:
        try:
            return (
                int(raw[1:3], 16),
                int(raw[3:5], 16),
                int(raw[5:7], 16),
            )
        except ValueError:
            pass
    return default


@dataclass(frozen=True)
class ObstacleCircle:
    id: int
    obstacle_type: str
    x: float
    y: float
    radius: float
    color: Tuple[int, int, int] = (120, 118, 110)

    def query_aabb(self) -> Tuple[float, float, float, float]:
        r = self.radius
        return (self.x - r, self.y - r, self.x + r, self.y + r)

    def blocks(self, px: float, py: float, body_radius: float) -> bool:
        dist = math.hypot(px - self.x, py - self.y)
        return dist < self.radius + body_radius


@dataclass(frozen=True)
class ObstacleRect:
    id: int
    obstacle_type: str
    x: float
    y: float
    half_w: float
    half_h: float
    color: Tuple[int, int, int] = (92, 64, 40)

    def query_aabb(self) -> Tuple[float, float, float, float]:
        return (
            self.x - self.half_w,
            self.y - self.half_h,
            self.x + self.half_w,
            self.y + self.half_h,
        )

    def blocks(self, px: float, py: float, body_radius: float) -> bool:
        hw = self.half_w + body_radius
        hh = self.half_h + body_radius
        return abs(px - self.x) < hw and abs(py - self.y) < hh


Obstacle = Union[ObstacleCircle, ObstacleRect]


def _resolve_circle(
    px: float, py: float, body_radius: float, obs: ObstacleCircle
) -> Tuple[float, float]:
    dx = px - obs.x
    dy = py - obs.y
    dist_sq = dx * dx + dy * dy
    min_dist = obs.radius + body_radius
    if dist_sq >= min_dist * min_dist:
        return px, py
    if dist_sq <= 1e-12:
        return obs.x + min_dist, obs.y
    dist = math.sqrt(dist_sq)
    scale = min_dist / dist
    return obs.x + dx * scale, obs.y + dy * scale


def _resolve_rect(
    px: float, py: float, body_radius: float, obs: ObstacleRect
) -> Tuple[float, float]:
    hw = obs.half_w + body_radius
    hh = obs.half_h + body_radius
    lx = px - obs.x
    ly = py - obs.y
    if abs(lx) >= hw or abs(ly) >= hh:
        return px, py
    pen_x = hw - abs(lx)
    pen_y = hh - abs(ly)
    if pen_x <= pen_y:
        lx = math.copysign(hw, lx if lx != 0.0 else 1.0)
    else:
        ly = math.copysign(hh, ly if ly != 0.0 else 1.0)
    return obs.x + lx, obs.y + ly


class ObstacleSystem:
    """静的障害物。起動時に空間索引を構築し、以降は再計算しない。"""

    def __init__(self, world: "World") -> None:
        self.world = world
        self.obstacles: List[Obstacle] = []
        self._cell_size = DEFAULT_CELL_SIZE
        self._cols = 1
        self._rows = 1
        self._cells: Dict[Tuple[int, int], List[int]] = defaultdict(list)

    def init_from_config(self, cfg: Dict | None) -> None:
        """非推奨: テスト用。本番は World → WOS → rebuild_from_world_objects。"""
        self.obstacles.clear()
        self._cells.clear()
        if not cfg:
            return
        type_defaults: Dict[str, Dict] = {}
        for key, value in (cfg.get("types") or {}).items():
            if isinstance(value, dict):
                type_defaults[str(key)] = dict(value)
        defaults = dict(cfg.get("defaults") or {})
        for entry in cfg.get("sources") or []:
            if isinstance(entry, dict):
                self._add_from_entry(entry, type_defaults, defaults)
        self._build_index()

    def bootstrap_from_world_objects(self) -> bool:
        self.rebuild_from_world_objects()
        return len(self.obstacles) > 0

    def init_from_layout(self, layout: Dict | None = None) -> None:
        """WorldObject（obstacle）のみから衝突キャッシュを構築。"""
        self.rebuild_from_world_objects()

    def rebuild_from_world_objects(self) -> None:
        self.obstacles.clear()
        self._cells.clear()
        ws = getattr(self.world, "world_object_system", None)
        if ws is None:
            return
        for idx, obj in enumerate(ws.iter_obstacles(), start=1):
            if obj.shape == "rect":
                self.obstacles.append(
                    ObstacleRect(
                        id=idx,
                        obstacle_type=obj.type_ref,
                        x=float(obj.x),
                        y=float(obj.y),
                        half_w=float(obj.half_w),
                        half_h=float(obj.half_h),
                        color=obj.color,
                    )
                )
            else:
                self.obstacles.append(
                    ObstacleCircle(
                        id=idx,
                        obstacle_type=obj.type_ref,
                        x=float(obj.x),
                        y=float(obj.y),
                        radius=float(obj.radius),
                        color=obj.color,
                    )
                )
        self._build_index()

    def _add_from_entry(
        self,
        entry: Dict,
        type_defaults: Dict[str, Dict],
        defaults: Dict,
    ) -> None:
        merged = dict(defaults)
        obs_type = str(entry.get("type", ""))
        if obs_type and obs_type in type_defaults:
            merged.update(type_defaults[obs_type])
        merged.update(entry)

        shape = str(merged.get("shape", "circle")).lower()
        x = float(merged.get("x", 0.0))
        y = float(merged.get("y", 0.0))
        color = _parse_color((merged.get("render") or {}).get("color"), (120, 118, 110))
        obs_id = len(self.obstacles) + 1
        label = obs_type or shape

        if shape == "rect":
            width = float(merged.get("width", 40.0))
            height = float(merged.get("height", 16.0))
            self.obstacles.append(
                ObstacleRect(
                    id=obs_id,
                    obstacle_type=label,
                    x=x,
                    y=y,
                    half_w=max(1.0, width * 0.5),
                    half_h=max(1.0, height * 0.5),
                    color=color,
                )
            )
            return

        radius = float(merged.get("radius", 20.0))
        self.obstacles.append(
            ObstacleCircle(
                id=obs_id,
                obstacle_type=label,
                x=x,
                y=y,
                radius=max(1.0, radius),
                color=color,
            )
        )

    def _build_index(self) -> None:
        self._cells.clear()
        if not self.obstacles:
            return

        width = float(self.world.width)
        height = float(self.world.height)
        self._cell_size = DEFAULT_CELL_SIZE
        self._cols = max(1, math.ceil(width / self._cell_size))
        self._rows = max(1, math.ceil(height / self._cell_size))

        for idx, obs in enumerate(self.obstacles):
            min_x, min_y, max_x, max_y = obs.query_aabb()
            col0 = max(0, int(min_x // self._cell_size))
            col1 = min(self._cols - 1, int(max_x // self._cell_size))
            row0 = max(0, int(min_y // self._cell_size))
            row1 = min(self._rows - 1, int(max_y // self._cell_size))
            for row in range(row0, row1 + 1):
                for col in range(col0, col1 + 1):
                    self._cells[(col, row)].append(idx)

    def iter_near(self, x: float, y: float, margin: float) -> Iterator[Obstacle]:
        if not self.obstacles:
            return
        margin = max(0.0, float(margin))
        cs = self._cell_size
        col0 = max(0, int((x - margin) // cs))
        col1 = min(self._cols - 1, int((x + margin) // cs))
        row0 = max(0, int((y - margin) // cs))
        row1 = min(self._rows - 1, int((y + margin) // cs))
        seen: set[int] = set()
        for row in range(row0, row1 + 1):
            for col in range(col0, col1 + 1):
                for idx in self._cells.get((col, row), ()):
                    if idx in seen:
                        continue
                    seen.add(idx)
                    yield self.obstacles[idx]

    def is_walkable(self, x: float, y: float, body_radius: float = 0.0) -> bool:
        body_radius = max(0.0, float(body_radius))
        margin = body_radius
        for obs in self.iter_near(x, y, margin):
            if obs.blocks(x, y, body_radius):
                return False
        return True

    def resolve_position(
        self,
        x: float,
        y: float,
        body_radius: float,
        *,
        max_passes: int = 3,
    ) -> Tuple[float, float]:
        body_radius = max(0.0, float(body_radius))
        if body_radius <= 0.0 or not self.obstacles:
            return x, y

        px, py = float(x), float(y)
        for _ in range(max_passes):
            moved = False
            for obs in self.iter_near(px, py, body_radius + 8.0):
                if isinstance(obs, ObstacleCircle):
                    nx, ny = _resolve_circle(px, py, body_radius, obs)
                else:
                    nx, ny = _resolve_rect(px, py, body_radius, obs)
                if nx != px or ny != py:
                    px, py = nx, ny
                    moved = True
            if not moved:
                break
        return px, py
