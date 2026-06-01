"""地面ドロップ（field WorldObject）のテスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.components.inventory import InventorySlot
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

    def test_pickup_stack_item_from_field(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        inv = ant.inventory
        inv.slots.append(
            InventorySlot(max_mass=20.0, allowed_kinds=frozenset({"item"}))
        )
        world.add_creature(ant)
        obj = world.world_object_system.spawn_instance(
            type_ref="field_item",
            x=100,
            y=100,
            fill={
                "mode": "stack_item",
                "item_type": "gold_coin",
                "quantity": 3,
                "mass_per_unit": 0.5,
            },
        )
        self.assertTrue(try_pickup_loot(ant, obj))
        self.assertEqual(len(iter_field_pickups(world)), 0)
        item_slot = next(s for s in inv.slots if s.item and s.item.kind == "item")
        self.assertEqual(item_slot.item.item_type, "gold_coin")
        self.assertEqual(item_slot.item.quantity, 3)

if __name__ == "__main__":
    unittest.main()
