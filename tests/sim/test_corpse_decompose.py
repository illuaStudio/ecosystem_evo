"""死骸の自然分解（地面ルート）のテスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


class TestCorpseDecompose(unittest.TestCase):
    def test_biomass_loot_lasts_many_sim_ticks(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=100, y=100)
        world.add_creature(spider)
        spider.become_corpse()
        loot = next(iter(world.world_object_system.iter_field_pickups()))
        initial = loot.amount_for_kind("biomass")
        self.assertGreater(initial, 100)

        ticks = 0
        while world.world_object_system.iter_field_pickups() and ticks < 5000:
            world.world_object_system.update_field_objects(10.0)
            ticks += 1

        self.assertGreater(ticks, 80)
        self.assertLess(ticks, 4000)


if __name__ == "__main__":
    unittest.main()
