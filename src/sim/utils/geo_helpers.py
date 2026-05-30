"""距離・視界・近さの幾何計算。"""
import math

from src.sim.utils.position_helpers import entity_xy

def distance_between(a, b) -> float:
    ax, ay = entity_xy(a)
    bx, by = entity_xy(b)
    return math.hypot(bx - ax, by - ay)

def distance_to_point(entity, x: float, y: float) -> float:
    ex, ey = entity_xy(entity)
    return math.hypot(x - ex, y - ey)

class PointTarget:
    """座標のみの移動ターゲット（巣など）。"""

    __slots__ = ("pos",)

    def __init__(self, x: float, y: float):
        self.pos = [float(x), float(y)]

def closeness_ratio(creature, other) -> float:
    """視界内での近さ（0=遠い, 1=至近）"""
    vision = creature.get_current_vision()
    if vision <= 0:
        return 0.0
    return max(0.0, min(1.0, 1.0 - distance_between(creature, other) / vision))

def is_in_vision(creature, target) -> bool:
    return distance_between(creature, target) <= creature.get_current_vision()
