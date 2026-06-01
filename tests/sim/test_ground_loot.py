"""地面ドロップ（field WorldObject）のテスト。"""
import unittest

from src.sim.behavior import set_creature_death_policy
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.field_pickup_helpers import iter_field_pickups
from src.sim.utils.loot_helpers import try_pickup_loot


class TestFieldPickup(unittest.TestCase):
    def test_pickup_from_field_object(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(ant)
        obj = world.world_object_system.spawn_instance(
            type_ref="field_bulk",
            x=100,
            y=100,
            fill={"mode": "fixed_amount", "amount": 40.0},
            overrides={"pickup_species_filter": "Spider"},
        )
        self.assertTrue(try_pickup_loot(ant, obj))
        self.assertEqual(len(iter_field_pickups(world)), 0)

    def test_legacy_corpse_on_creature_policy(self):
        world = World()
        factory = CreatureFactory()
        spider = factory.create("Spider", world=world, x=50, y=50)
        world.add_creature(spider)
        set_creature_death_policy(spider, "corpse_on_creature")
        spider.become_corpse()
        self.assertIn(spider, world.creatures)
        self.assertGreater(spider.remaining_mass, 0.0)
        self.assertEqual(len(iter_field_pickups(world)), 0)


if __name__ == "__main__":
    unittest.main()
