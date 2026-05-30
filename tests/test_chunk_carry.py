"""死骸チャンク運搬（インベントリ上限）のテスト。"""
import unittest

from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import try_attack_only, try_pickup_carcass
from src.utils.inventory_helpers import (
    clear_inventory_biomass,
    get_haul_max_carry,
    inventory_is_loaded,
    total_biomass_amount,
)
from src.utils.position_helpers import entity_xy


class TestChunkCarry(unittest.TestCase):
    def test_spider_carcass_needs_many_trips(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=400, y=400)
        world.add_creature(ant)
        for slot in ant.inventory.slots:
            slot.max_mass = 3.3

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
        spider.remaining_biomass = 165.0
        self.assertFalse(spider.alive)

        total = spider.remaining_biomass
        per_trip_cap = sum(s.max_mass for s in ant.inventory.slots)
        self.assertGreater(per_trip_cap, 0.0)

        trips = 0
        while spider.remaining_biomass > 0 and trips < 120:
            self.assertTrue(try_pickup_carcass(ant, spider))
            trips += 1
            self.assertTrue(inventory_is_loaded(ant))
            self.assertLessEqual(total_biomass_amount(ant), per_trip_cap + 0.001)
            clear_inventory_biomass(ant)

        self.assertGreaterEqual(trips, 15)
        self.assertLessEqual(trips, 60)
        self.assertAlmostEqual(total, per_trip_cap * trips, delta=per_trip_cap * 2)


if __name__ == "__main__":
    unittest.main()
