"""巣食料: 端数も食べ切って 0 にできることのテスト。"""
import unittest

from src.sim.ai.actions.colony import FeedAtNestAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.nutrition_helpers import nest_has_usable_food
from tests.sim.world_fixtures import set_affiliation_stored_food


class TestNestFoodCleanup(unittest.TestCase):
    def test_low_reserve_usable_when_hungry(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(ant, spawn_source="initial")
        ant.satiety = ant.max_satiety * 0.10
        nest = world.nest_system.get_creature_nest(ant)
        set_affiliation_stored_food(world, nest.affiliation_id, 8.0)

        self.assertTrue(nest_has_usable_food(ant))
        self.assertGreater(FeedAtNestAction().calculate_utility(ant), 0.0)

    def test_feed_clears_reserve_in_steps(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(ant, spawn_source="initial")
        ant.satiety = 0.0
        nest = world.nest_system.get_creature_nest(ant)
        set_affiliation_stored_food(world, nest.affiliation_id, 49.0)

        self.assertTrue(nest_has_usable_food(ant))
        while nest.stored_food > 0 and ant.satiety < ant.max_satiety:
            world.nest_system.feed_creature(ant, bite_gain=1.15, feed_per_tick=11.0)
        self.assertEqual(nest.stored_food, 0.0)

    def test_no_dust_flush_on_update(self):
        world = World()
        nest = world.nest_system.get_affiliation_root("red_ant")
        self.assertIsNotNone(nest)
        root = world.world_object_system.get("red_ant")
        self.assertIsNotNone(root)
        root.storage.stored_food = 49.0
        nest.stored_food = 49.0
        nest.max_food = 5000.0

        world.nest_system.update(dt=1.0)

        self.assertEqual(nest.stored_food, 49.0)
        self.assertEqual(root.storage.stored_food, 49.0)


if __name__ == "__main__":
    unittest.main()
