"""affiliation_config_helpers の単体テスト。"""
import unittest

from src.sim.systems.world import World
from src.sim.utils.affiliation_config_helpers import (
    get_affiliation_profile as get_affiliation_profile,
    get_min_storage_reserve,
    resolve_affiliation_runtime_cfg as resolve_affiliation_runtime_cfg,
)


class TestColonyConfigHelpers(unittest.TestCase):
    def test_min_storage_reserve_from_world_colony(self):
        world = World()
        self.assertEqual(get_min_storage_reserve(world), 72.0)

    def test_min_storage_reserve_legacy_key(self):
        world = World.from_json(
            {
                "name": "Legacy",
                "world_width": 500,
                "world_height": 500,
                "affiliation": {"min_storage_reserve": 55},
            }
        )
        self.assertEqual(get_min_storage_reserve(world), 55.0)

    def test_colony_profile_by_affiliation_id(self):
        world = World()
        profile = get_affiliation_profile(world, "red_ant")
        self.assertEqual(profile["nest_x"], 120)
        self.assertEqual(profile["initial_mass"], 1000)
        self.assertAlmostEqual(profile["storage_leak_per_tick"], 0.0)

    def test_species_override_spawn_spread(self):
        world = World()
        runtime = resolve_affiliation_runtime_cfg(
            world,
            "red_ant",
            {"spawn_spread": 22},
        )
        self.assertEqual(runtime["spawn_spread"], 22)
        self.assertEqual(runtime["nest_x"], 120)


if __name__ == "__main__":
    unittest.main()
