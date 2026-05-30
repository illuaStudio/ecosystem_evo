"""移動処理を担当する ECS System。"""
import math
import random
from typing import Any, List, Optional

from src.sim.components.position import Position
from src.sim.components.velocity import Velocity
from src.sim.utils.position_helpers import entity_xy, sync_legacy_pos

WORLD_MARGIN = 30


class MovementSystem:
    """Position / Velocity コンポーネントを持つエンティティの移動を更新する。"""

    def update(self, entities: List[Any], world: Any, dt: float = 1.0) -> None:
        """速度の適用とワールド境界へのクランプ。"""
        dt = float(dt)
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
                position.x += velocity.vx * dt
                position.y += velocity.vy * dt
                velocity.vx = 0.0
                velocity.vy = 0.0

            self._clamp_position(position, world)
            sync_legacy_pos(entity)

    @staticmethod
    def wander_step(
        entity: Any,
        angle_range: float,
        speed_multiplier: float,
        dt: float = 1.0,
        world: Any = None,
    ) -> None:
        """徘徊: wander_angle に沿って Position を更新する。"""
        position = MovementSystem._require_position(entity)
        wander_angle = getattr(entity, "wander_angle", 0.0)
        wander_angle += random.uniform(-angle_range, angle_range)
        entity.wander_angle = wander_angle

        if world is not None:
            MovementSystem._nudge_wander_from_bounds(entity, position, world)

        step = entity.get_current_speed() * speed_multiplier * float(dt)
        position.x += math.cos(math.radians(entity.wander_angle)) * step
        position.y += math.sin(math.radians(entity.wander_angle)) * step
        sync_legacy_pos(entity)

    @staticmethod
    def _nudge_wander_from_bounds(
        entity: Any,
        position: Position,
        world: Any,
        margin: float = WORLD_MARGIN,
        band: float = 50.0,
        strength: float = 0.4,
    ) -> None:
        """クランプ境界付近では内向きへ進路を寄せ、端への滞留を防ぐ。"""
        inward_x = 0.0
        inward_y = 0.0
        x, y = position.x, position.y
        w, h = float(world.width), float(world.height)

        if x < margin + band:
            inward_x += 1.0
        elif x > w - margin - band:
            inward_x -= 1.0
        if y < margin + band:
            inward_y += 1.0
        elif y > h - margin - band:
            inward_y -= 1.0

        if inward_x == 0.0 and inward_y == 0.0:
            return

        target = math.degrees(math.atan2(inward_y, inward_x)) % 360
        wander_angle = getattr(entity, "wander_angle", 0.0)
        diff = ((target - wander_angle + 180) % 360) - 180
        entity.wander_angle = (wander_angle + diff * strength) % 360

    @staticmethod
    def move_toward(
        entity: Any,
        target: Any,
        speed_multiplier: float = 1.0,
        dt: float = 1.0,
        min_distance: float | None = None,
    ) -> float:
        """
        ターゲット方向へ移動し、移動後の距離を返す。

        min_distance を指定した場合、その距離より近づかない（相手サイズに応じた
        接触リングの外側で止まる。攻撃判定の contact_range と揃える想定）。
        """
        position = MovementSystem._require_position(entity)
        target_pos = MovementSystem._target_position(target)

        dx = target_pos[0] - position.x
        dy = target_pos[1] - position.y
        dist = math.hypot(dx, dy)
        if dist == 0:
            return 0.0

        standoff = float(min_distance) if min_distance is not None else 0.0
        if standoff > 0 and dist <= standoff:
            return dist

        step = entity.get_current_speed() * speed_multiplier * float(dt)
        if standoff > 0:
            step = min(step, max(0.0, dist - standoff))

        if step <= 0:
            return dist

        position.x += (dx / dist) * step
        position.y += (dy / dist) * step
        sync_legacy_pos(entity)

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
        return entity_xy(target)
