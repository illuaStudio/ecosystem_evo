"""地面バイオマスのチャンク運搬（インベントリ上限）のテスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from tests.sim.field_drop_helpers import kill_creature, pickup_field_biomass
from src.sim.utils.inventory_helpers import (
    clear_inventory_for_kind,
    inventory_is_loaded,
    carried_mass_for_kind,
)
from src.sim.utils.position_helpers import entity_xy


class TestChunkCarry(unittest.TestCase):
    def test_spider_pickup_needs_many_trips(self):
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

        loot = kill_creature(world, spider)
        loot.storage.stack.set_amount_for_kind("biomass", 165.0)
        loot.initial_fill = 165.0
        total = 165.0
        per_trip_cap = sum(s.max_mass for s in ant.inventory.slots)
        self.assertGreater(per_trip_cap, 0.0)

        trips = 0
        while loot.amount_for_kind("biomass") > 0 and trips < 120:
            self.assertTrue(pickup_field_biomass(ant, loot))
            trips += 1
            self.assertTrue(inventory_is_loaded(ant))
            self.assertLessEqual(carried_mass_for_kind(ant), per_trip_cap + 0.001)
            clear_inventory_for_kind(ant)

        self.assertGreaterEqual(trips, 15)
        self.assertLessEqual(trips, 60)
        self.assertAlmostEqual(total, per_trip_cap * trips, delta=per_trip_cap * 2)


if __name__ == "__main__":
    unittest.main()
