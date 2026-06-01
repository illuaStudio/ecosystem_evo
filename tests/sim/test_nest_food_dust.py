from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""巣食料: 端数も食べ切って 0 にできることのテスト。"""
import unittest

from src.game.ai.colony_actions import FeedAtNestAction
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.game.affiliation_feed import nest_has_usable_storage
from tests.sim.world_fixtures import set_affiliation_stored_mass


class TestNestFoodCleanup(unittest.TestCase):
    def test_low_reserve_usable_when_hungry(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(ant, spawn_source="initial")
        ant.satiety = ant.max_satiety * 0.10
        nest = colony(world).get_creature_affiliation_root(ant)
        set_affiliation_stored_mass(world, nest.affiliation_id, 8.0)

        self.assertTrue(nest_has_usable_storage(ant))
        self.assertGreater(FeedAtNestAction().calculate_utility(ant), 0.0)

    def test_feed_clears_reserve_in_steps(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=120, y=120)
        world.add_creature(ant, spawn_source="initial")
        ant.satiety = 0.0
        nest = colony(world).get_creature_affiliation_root(ant)
        set_affiliation_stored_mass(world, nest.affiliation_id, 49.0)

        self.assertTrue(nest_has_usable_storage(ant))
        while nest.stored_mass > 0 and ant.satiety < ant.max_satiety:
            colony(world).feed_creature(ant, bite_gain=1.15, feed_per_tick=11.0)
        self.assertEqual(nest.stored_mass, 0.0)

    def test_no_dust_flush_on_update(self):
        world = World()
        nest = colony(world).get_affiliation_root("red_ant")
        self.assertIsNotNone(nest)
        root = world.world_object_system.get("red_ant")
        self.assertIsNotNone(root)
        root.storage.stored_mass = 49.0
        nest.stored_mass = 49.0
        nest.capacity = 5000.0

        colony(world).update(dt=1.0)

        self.assertEqual(nest.stored_mass, 49.0)
        self.assertEqual(root.storage.stored_mass, 49.0)


if __name__ == "__main__":
    unittest.main()
