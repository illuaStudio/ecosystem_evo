"""ワールド population_limits による繁殖抑制。"""
import unittest

from src.sim.ai.actions import SplitAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


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
    def test_split_blocked_at_world_cap(self):
        cap = 3
        world = _empty_world({"Amoeba": cap})
        factory = CreatureFactory()

        parent = factory.create("Amoeba", world=world, x=100, y=100)
        world.add_creature(parent)
        parent.traits["base_size"] = 16.0
        parent.satiety = parent.max_satiety
        parent.age = int(parent.life_cycle.get("mature", 0))
        parent.repro_cooldown = 0

        for i in range(cap - 1):
            other = factory.create("Amoeba", world=world, x=110 + i, y=100)
            world.add_creature(other)

        action = SplitAction()
        self.assertFalse(action.can_execute(parent))

    def test_split_allowed_below_cap(self):
        cap = 5
        world = _empty_world({"Amoeba": cap})
        factory = CreatureFactory()

        parent = factory.create("Amoeba", world=world, x=100, y=100)
        world.add_creature(parent)
        parent.traits["base_size"] = 16.0
        parent.satiety = parent.max_satiety
        parent.age = int(parent.life_cycle.get("mature", 0))
        parent.repro_cooldown = 0

        for i in range(2):
            other = factory.create("Amoeba", world=world, x=110 + i, y=100)
            world.add_creature(other)

        action = SplitAction()
        self.assertTrue(action.can_execute(parent))

    def test_world_loads_population_limits(self):
        world = World()
        self.assertEqual(world.get_population_cap("springtail"), 50)
        self.assertEqual(world.get_population_cap("red_ant"), 20)
        self.assertEqual(world.get_population_cap("red_ant_queen"), 3)
        self.assertEqual(world.get_population_cap("red_ant_soldier"), 10)
        self.assertIsNone(world.get_population_cap("Unknown"))


if __name__ == "__main__":
    unittest.main()
