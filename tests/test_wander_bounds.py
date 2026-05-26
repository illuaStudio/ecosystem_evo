"""徘徊の境界内向き補正のユニットテスト。"""
import math
import unittest
from unittest.mock import MagicMock

from src.components.position import Position
from src.systems.movement_system import MovementSystem, WORLD_MARGIN


class TestWanderBounds(unittest.TestCase):
    def _entity_at_left_edge(self):
        entity = MagicMock()
        entity.wander_angle = 180.0
        entity.position = Position(WORLD_MARGIN + 5, 400.0)
        entity.get_current_speed.return_value = 1.0
        world = MagicMock()
        world.width = 1500
        world.height = 1500
        entity.world = world
        return entity, world

    def test_nudge_turns_inward_from_left_wall(self):
        entity, world = self._entity_at_left_edge()
        MovementSystem._nudge_wander_from_bounds(entity, entity.position, world)
        # 左端付近では右向き（0°付近）へ寄る
        self.assertLess(abs(entity.wander_angle - 180.0), 90.0)

    def test_wander_step_passes_world_from_creature_helpers(self):
        entity, world = self._entity_at_left_edge()
        from src.utils.creature_helpers import wander_step

        wander_step(entity, 5.0, 1.0)
        self.assertLess(abs(entity.wander_angle - 180.0), 120.0)


if __name__ == "__main__":
    unittest.main()
