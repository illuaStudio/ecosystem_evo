"""ワールド population_limits による個体数上限。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.stats_helpers import is_species_at_population_cap


def _empty_world(population_limits=None):
    return World.from_json(
        {
            "name": "Test",
            "world_width": 800,
            "world_height": 800,
            "initial_entities": {},
            "population_limits": population_limits or {},
        }
    )


class TestPopulationCap(unittest.TestCase):
    def test_at_cap_when_alive_equals_limit(self):
        cap = 3
        world = _empty_world({"springtail": cap})
        factory = CreatureFactory()

        for i in range(cap):
            creature = factory.create("springtail", world=world, x=100 + i, y=100)
            world.add_creature(creature)

        self.assertTrue(is_species_at_population_cap(world, "springtail"))

    def test_below_cap_when_alive_less_than_limit(self):
        cap = 5
        world = _empty_world({"springtail": cap})
        factory = CreatureFactory()

        for i in range(2):
            creature = factory.create("springtail", world=world, x=100 + i, y=100)
            world.add_creature(creature)

        self.assertFalse(is_species_at_population_cap(world, "springtail"))

    def test_world_loads_population_limits(self):
        world = World()
        # These are driven by config/game/worlds/world.json and may change during tuning.
        from src.config import config

        cfg = config.get_world("Grassland") or {}
        limits = cfg.get("population_limits") or {}
        self.assertEqual(world.get_population_cap("springtail"), limits.get("springtail"))
        self.assertEqual(world.get_population_cap("red_ant"), limits.get("red_ant"))
        self.assertEqual(world.get_population_cap("red_ant_queen"), limits.get("red_ant_queen"))
        self.assertEqual(world.get_population_cap("red_ant_soldier"), limits.get("red_ant_soldier"))
        self.assertIsNone(world.get_population_cap("Unknown"))


if __name__ == "__main__":
    unittest.main()
