"""地面ルート（量アイテム）のテスト。"""
import unittest

from src.sim.behavior import set_creature_death_policy
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.loot_helpers import try_pickup_loot


class TestGroundLoot(unittest.TestCase):
    def test_pickup_from_loot(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(ant)
        loot = world.ground_loot_system.spawn_biomass(
            100,
            100,
            40.0,
            source_species="Spider",
        )
        self.assertTrue(try_pickup_loot(ant, loot))
        self.assertFalse(world.ground_loot_system.loots)

    def test_legacy_corpse_on_creature_policy(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=50, y=50)
        world.add_creature(spider)
        set_creature_death_policy(spider, "biomass_corpse_legacy")
        spider.become_corpse()
        self.assertIn(spider, world.creatures)
        self.assertGreater(spider.remaining_biomass, 0.0)
        self.assertEqual(len(world.ground_loot_system.loots), 0)


if __name__ == "__main__":
    unittest.main()
