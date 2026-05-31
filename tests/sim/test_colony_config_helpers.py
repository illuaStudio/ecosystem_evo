"""colony_config_helpers の単体テスト。"""
import unittest

from src.sim.systems.world import World
from src.sim.utils.colony_config_helpers import (
    get_colony_profile,
    get_min_food_reserve,
    resolve_colony_runtime_cfg,
)


class TestColonyConfigHelpers(unittest.TestCase):
    def test_min_food_reserve_from_world_colony(self):
        world = World()
        self.assertEqual(get_min_food_reserve(world), 72.0)

    def test_min_food_reserve_legacy_key(self):
        world = World.from_json(
            {
                "name": "Legacy",
                "world_width": 500,
                "world_height": 500,
                "colony": {"min_food_reserve": 55},
            }
        )
        self.assertEqual(get_min_food_reserve(world), 55.0)

    def test_colony_profile_by_colony_id(self):
        world = World()
        profile = get_colony_profile(world, "red_ant")
        self.assertEqual(profile["nest_x"], 120)
        self.assertEqual(profile["initial_stored_food"], 1000)
        self.assertAlmostEqual(profile["food_leak_per_tick"], 0.0)

    def test_species_override_spawn_spread(self):
        world = World()
        runtime = resolve_colony_runtime_cfg(
            world,
            "red_ant",
            {"spawn_spread": 22},
        )
        self.assertEqual(runtime["spawn_spread"], 22)
        self.assertEqual(runtime["nest_x"], 120)


if __name__ == "__main__":
    unittest.main()
