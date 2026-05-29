"""ManaWanderAction の密度連動徘徊のユニットテスト。"""
import unittest
from unittest.mock import MagicMock, patch

from src.ai.actions import ManaWanderAction
from src.components.position import Position


class TestManaWanderAction(unittest.TestCase):
    def _creature(self, density=500.0, cap=2500.0):
        creature = MagicMock()
        creature.alive = True
        creature.position = Position(100.0, 100.0)
        creature.world = MagicMock()
        creature.world.mana_density_cap = cap
        creature.world.get_mana_density.return_value = density
        creature.get_current_speed.return_value = 1.0
        return creature

    def test_sparse_moves_faster_than_dense(self):
        action = ManaWanderAction(
            angle_range_sparse=30,
            angle_range_dense=10,
            speed_multiplier_sparse=1.0,
            speed_multiplier_dense=0.3,
        )
        sparse = self._creature(density=0.0)
        dense = self._creature(density=2500.0)

        with patch("src.ai.actions.movement.wander_step") as wander:
            action.execute(sparse)
            sparse_speed = wander.call_args[0][2]
            wander.reset_mock()
            action.execute(dense)
            dense_speed = wander.call_args[0][2]

        self.assertGreater(sparse_speed, dense_speed)
        self.assertEqual(sparse_speed, 1.0)
        self.assertAlmostEqual(dense_speed, 0.3)

    def test_sparse_turns_more_than_dense(self):
        action = ManaWanderAction(
            angle_range_sparse=28,
            angle_range_dense=8,
            speed_multiplier_sparse=1.0,
            speed_multiplier_dense=0.4,
        )
        sparse = self._creature(density=0.0)
        dense = self._creature(density=2500.0)

        with patch("src.ai.actions.movement.wander_step") as wander:
            action.execute(sparse)
            sparse_angle = wander.call_args[0][1]
            wander.reset_mock()
            action.execute(dense)
            dense_angle = wander.call_args[0][1]

        self.assertGreater(sparse_angle, dense_angle)


if __name__ == "__main__":
    unittest.main()
