"""死骸チャンク運搬（base_max_carry）のテスト。"""
import unittest

from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    get_haul_max_carry,
    try_attack_only,
    try_pickup_carcass,
)
from src.utils.position_helpers import entity_xy


class TestChunkCarry(unittest.TestCase):
    def test_spider_carcass_needs_many_trips(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=400, y=400)
        world.add_creature(ant)

        spider = factory.create("Spider", world=world, x=0, y=0)
        world.add_creature(spider)
        ax, ay = entity_xy(ant)
        spider.pos[0] = ax + 12
        spider.pos[1] = ay
        if hasattr(spider, "position"):
            spider.position.x = spider.pos[0]
            spider.position.y = spider.pos[1]

        spider.hp = 0
        spider.become_corpse()
        self.assertFalse(spider.alive)

        total = spider.remaining_biomass
        max_carry = get_haul_max_carry(ant)
        self.assertAlmostEqual(max_carry, 3.3, places=1)

        trips = 0
        while spider.remaining_biomass > 0 and trips < 120:
            self.assertTrue(try_pickup_carcass(ant, spider))
            trips += 1
            self.assertGreater(ant.colony.carried_biomass, 0)
            self.assertLessEqual(ant.colony.carried_biomass, max_carry + 0.001)
            ant.colony.carried_biomass = 0.0
            ant.colony.carried_carcass = None

        self.assertGreaterEqual(trips, 45)
        self.assertLessEqual(trips, 55)
        self.assertAlmostEqual(total, max_carry * trips, delta=max_carry * 2)


if __name__ == "__main__":
    unittest.main()
