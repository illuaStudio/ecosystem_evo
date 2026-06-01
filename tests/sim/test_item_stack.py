"""ItemStack と storage↔inventory 移動（Phase 4）。"""
import unittest

from src.sim.components.inventory import BiomassItem, InventoryComponent, InventorySlot, StackItem
from src.sim.components.item_stack import ItemStack
from src.sim.components.object_storage import ObjectStorage
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.item_stack_helpers import (
    transfer_kind_creature_to_storage,
    transfer_kind_storage_to_creature,
)
from src.sim.utils.world_object_helpers import (
    deposit_carried_to_parent,
    set_creature_compound_parent_ids,
    withdraw_from_parent_storage,
)
from tests.sim.test_compound_system import _linked_chest_world


class TestItemStack(unittest.TestCase):
    def test_biomass_capacity_deposit_withdraw(self):
        stack = ItemStack.from_kind_capacity("biomass", 100.0, 10.0)
        self.assertAlmostEqual(stack.amount_for_kind("biomass"), 10.0)
        self.assertAlmostEqual(stack.deposit_kind("biomass", 50.0), 50.0)
        self.assertAlmostEqual(stack.amount_for_kind("biomass"), 60.0)
        self.assertAlmostEqual(stack.deposit_kind("biomass", 100.0), 40.0)
        self.assertAlmostEqual(stack.withdraw_kind("biomass", 25.0), 25.0)
        self.assertAlmostEqual(stack.amount_for_kind("biomass"), 75.0)

    def test_object_storage_compat_api(self):
        storage = ObjectStorage(stored_mass=30.0, max_mass=200.0)
        self.assertAlmostEqual(storage.stored_mass, 30.0)
        self.assertAlmostEqual(storage.capacity, 200.0)
        self.assertAlmostEqual(storage.deposit(10.0), 10.0)
        self.assertAlmostEqual(storage.stored_mass, 40.0)
        self.assertAlmostEqual(storage.fill_ratio, 0.2)

    def test_multi_slot_storage_config(self):
        storage = ObjectStorage.from_config(
            {
                "slot_count": 2,
                "max_mass": 100.0,
                "initial_mass": 0.0,
            }
        )
        self.assertEqual(storage.stack.slot_count, 2)
        self.assertAlmostEqual(storage.capacity, 100.0)

    def test_deposit_stack_item(self):
        stack = ItemStack(
            slots=[InventorySlot(max_mass=10.0, allowed_kinds=frozenset({"item"}))]
        )
        item = StackItem(item_type="sword", quantity=1, mass_per_unit=3.0)
        self.assertTrue(stack.deposit_item(item))
        self.assertAlmostEqual(stack.total_mass, 3.0)


class TestItemTransfer(unittest.TestCase):
    def test_creature_to_storage_and_back(self):
        world = _linked_chest_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=200)
        set_creature_compound_parent_ids(ant, ("dungeon_loot",))
        ant.world = world
        ant.inventory.slots[0].item = BiomassItem(amount=40.0)

        deposited = deposit_carried_to_parent(ant)
        self.assertAlmostEqual(deposited, 40.0)
        root = world.compound_system.get_root("dungeon_loot")
        self.assertAlmostEqual(root.storage.stored_mass, 40.0)

        withdrawn = withdraw_from_parent_storage(ant, 15.0)
        self.assertAlmostEqual(withdrawn, 15.0)
        self.assertAlmostEqual(root.storage.stored_mass, 25.0)
        self.assertAlmostEqual(ant.inventory.slots[0].item.amount, 15.0)

    def test_linked_chests_share_item_stack(self):
        world = _linked_chest_world()
        storage = world.compound_system.get_root("dungeon_loot").storage
        storage.stack.deposit_kind("biomass", 50.0)

        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=500, y=300)
        set_creature_compound_parent_ids(ant, ("dungeon_loot",))
        ant.world = world

        taken = withdraw_from_parent_storage(ant, 20.0)
        self.assertAlmostEqual(taken, 20.0)
        self.assertAlmostEqual(storage.stored_mass, 30.0)


if __name__ == "__main__":
    unittest.main()
