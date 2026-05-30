"""死骸の自然分解・マナ還元のテスト。"""
import unittest

from src.sim.components.corpse import CorpseComponent
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World


class TestCorpseDecompose(unittest.TestCase):
    def test_spider_carcass_lasts_many_sim_ticks(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=100, y=100)
        world.add_creature(spider)
        spider.become_corpse()
        initial = spider.remaining_biomass
        self.assertGreater(initial, 100)

        ticks = 0
        while spider.remaining_biomass > 0 and ticks < 5000:
            spider.corpse.update(10.0)
            ticks += 1

        self.assertGreater(ticks, 80)
        self.assertLess(ticks, 4000)


if __name__ == "__main__":
    unittest.main()
