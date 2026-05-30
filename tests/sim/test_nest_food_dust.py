"""巣の食料塵（食事不能残り）の処理テスト。"""
import unittest

from src.sim.systems.world import World
from src.sim.utils.nutrition_helpers import is_sub_usable_nest_food


class TestNestFoodDust(unittest.TestCase):
    def test_is_sub_usable_below_ratio(self):
        self.assertTrue(is_sub_usable_nest_food(49.0, 5000.0))
        self.assertFalse(is_sub_usable_nest_food(50.0, 5000.0))

    def test_is_sub_usable_below_absolute(self):
        self.assertTrue(is_sub_usable_nest_food(7.0, 5000.0))
        self.assertFalse(is_sub_usable_nest_food(0.0, 5000.0))

    def test_flush_clears_dust_to_zero(self):
        world = World()
        nest = world.nest_system.get_colony_nest("red_ant")
        self.assertIsNotNone(nest)
        nest.stored_food = 49.0
        nest.max_food = 5000.0

        world.nest_system.update(dt=1.0)

        self.assertEqual(nest.stored_food, 0.0)


if __name__ == "__main__":
    unittest.main()
