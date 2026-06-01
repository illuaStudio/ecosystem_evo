"""インベントリ Phase 1 のテスト。"""
import unittest

from src.sim.components.inventory import BiomassItem
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.inventory_helpers import (
    clear_inventory_for_kind,
    get_haul_max_carry,
    inventory_is_loaded,
    release_inventory_biomass,
    carried_mass_for_kind,
    try_pickup_carcass,
)
from tests.sim.legacy_corpse_helpers import become_legacy_corpse
from src.sim.utils.position_helpers import entity_xy


class TestInventory(unittest.TestCase):
    def test_ant_has_one_slot_from_json(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        self.assertEqual(ant.inventory.slot_count, 1)
        self.assertAlmostEqual(get_haul_max_carry(ant), 50.0)

    def test_carry_slows_speed(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("rival_ant", world=world, x=100, y=100)
        base = ant.get_current_speed()
        ant.inventory.slots[0].item = BiomassItem(amount=80.0)
        loaded = ant.get_current_speed()
        self.assertLess(loaded, base)
        ref = float(ant.inventory.carry_speed_reference_weight)
        expected = base / (1.0 + 80.0 / ref)
        self.assertAlmostEqual(loaded, expected)

    def test_carry_speed_respects_reference_weight(self):
        inv_ref = 40.0
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        ant.inventory.carry_speed_reference_weight = inv_ref
        ant.inventory.slots[0].item = BiomassItem(amount=40.0)
        mult = ant.inventory.carry_speed_multiplier()
        self.assertAlmostEqual(mult, 0.5)

    def test_multi_slot_pickup_uses_empty_slots(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("rival_ant", world=world, x=100, y=100)
        from src.sim.components.inventory import InventoryComponent, InventorySlot

        ant.inventory = InventoryComponent(
            slots=[
                InventorySlot(max_mass=10.0),
                InventorySlot(max_mass=10.0),
                InventorySlot(max_mass=10.0),
            ],
            mass_per_unit=1.0,
            carry_speed_reference_weight=80.0,
        )
        world.add_creature(ant)

        prey = factory.create("springtail", world=world, x=102, y=100)
        world.add_creature(prey)
        prey.hp = 0
        become_legacy_corpse(prey)
        prey.remaining_mass = 25.0

        self.assertTrue(try_pickup_carcass(ant, prey))
        self.assertTrue(inventory_is_loaded(ant))
        self.assertAlmostEqual(carried_mass_for_kind(ant), 25.0)
        self.assertAlmostEqual(prey.remaining_mass, 0.0, places=1)

    def test_release_does_not_resurrect_removed_carcass(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(ant)

        prey = factory.create("springtail", world=world, x=102, y=100)
        world.add_creature(prey)
        prey.hp = 0
        become_legacy_corpse(prey)
        prey.remaining_mass = 30.0

        self.assertTrue(try_pickup_carcass(ant, prey))
        self.assertNotIn(prey, world.creatures)
        self.assertTrue(inventory_is_loaded(ant))

        release_inventory_biomass(ant)
        self.assertNotIn(prey, world.creatures)

    def test_clear_inventory_for_kind(self):
        world = World()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=100)
        ant.inventory.slots[0].item = BiomassItem(amount=33.0)
        self.assertAlmostEqual(clear_inventory_for_kind(ant), 33.0)
        self.assertFalse(inventory_is_loaded(ant))


if __name__ == "__main__":
    unittest.main()
