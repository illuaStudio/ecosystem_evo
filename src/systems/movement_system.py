"""移動処理を担当する ECS System。"""
import math
import random
from typing import Any, List, Optional

from src.components.position import Position
from src.components.velocity import Velocity

WORLD_MARGIN = 30


class MovementSystem:
    """Position / Velocity コンポーネントを持つエンティティの移動を更新する。"""

    def update(self, entities: List[Any], world: Any, dt: float = 1.0) -> None:
        """速度の適用とワールド境界へのクランプ。"""
        del dt  # ティック単位シミュレーション（将来 dt 対応用）
        if world is None:
            return

        for entity in entities:
            if not getattr(entity, "alive", True):
                continue
            position = getattr(entity, "position", None)
            if position is None:
                continue

            velocity = getattr(entity, "velocity", None)
            if isinstance(velocity, Velocity) and (velocity.vx != 0.0 or velocity.vy != 0.0):
                position.x += velocity.vx
                position.y += velocity.vy
                velocity.vx = 0.0
                velocity.vy = 0.0

            self._clamp_position(position, world)
            self._sync_pos(entity, position)

    @staticmethod
    def wander_step(
        entity: Any,
        angle_range: float,
        speed_multiplier: float,
    ) -> None:
        """徘徊: wander_angle に沿って Position を更新する。"""
        position = MovementSystem._require_position(entity)
        wander_angle = getattr(entity, "wander_angle", 0.0)
        wander_angle += random.uniform(-angle_range, angle_range)
        entity.wander_angle = wander_angle

        step = entity.get_current_speed() * speed_multiplier
        position.x += math.cos(math.radians(wander_angle)) * step
        position.y += math.sin(math.radians(wander_angle)) * step
        MovementSystem._sync_pos(entity, position)

    @staticmethod
    def move_toward(
        entity: Any,
        target: Any,
        speed_multiplier: float = 1.0,
    ) -> float:
        """ターゲット方向へ移動し、移動後の距離を返す。"""
        position = MovementSystem._require_position(entity)
        target_pos = MovementSystem._target_position(target)

        dx = target_pos[0] - position.x
        dy = target_pos[1] - position.y
        dist = math.hypot(dx, dy)
        if dist == 0:
            return 0.0

        step = entity.get_current_speed() * speed_multiplier
        position.x += (dx / dist) * step
        position.y += (dy / dist) * step
        MovementSystem._sync_pos(entity, position)

        return math.hypot(target_pos[0] - position.x, target_pos[1] - position.y)

    @staticmethod
    def _clamp_position(position: Position, world: Any) -> None:
        position.x = max(WORLD_MARGIN, min(world.width - WORLD_MARGIN, position.x))
        position.y = max(WORLD_MARGIN, min(world.height - WORLD_MARGIN, position.y))

    @staticmethod
    def _require_position(entity: Any) -> Position:
        position = getattr(entity, "position", None)
        if position is None:
            raise AttributeError(f"{type(entity).__name__} に position コンポーネントがありません")
        return position

    @staticmethod
    def _target_position(target: Any) -> tuple[float, float]:
        if hasattr(target, "position") and target.position is not None:
            return target.position.x, target.position.y
        return float(target.pos[0]), float(target.pos[1])

    @staticmethod
    def _sync_pos(entity: Any, position: Position) -> None:
        if hasattr(entity, "pos"):
            entity.pos[0] = position.x
            entity.pos[1] = position.y
