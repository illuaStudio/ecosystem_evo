"""CompoundSystem（Phase 2）— 共有 storage + 複数 access。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.world_object_helpers import (
    deposit_carried_to_parent,
    get_compound_root,
    resolve_deposit_target,
    resolve_withdraw_target,
    set_creature_compound_parent_ids,
)


def _linked_chest_world(**overrides):
    data = {
        "name": "LinkedChestWorld",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "instances": [
            {
                "id": "dungeon_loot",
                "layer": "compound_root",
                "type": "storage_hub",
                "x": 0,
                "y": 0,
            },
            {
                "id": "chest_a",
                "layer": "compound_access",
                "type": "linked_chest",
                "parent": "dungeon_loot",
                "x": 100,
                "y": 200,
            },
            {
                "id": "chest_b",
                "layer": "compound_access",
                "type": "linked_chest",
                "parent": "dungeon_loot",
                "x": 500,
                "y": 300,
            },
        ],
        "world": {
            "biome_map_cell_size": 64,
            "biomes": [{"name": "rich", "color": "#2E8B57", "spawn_rate_multiplier": 1.0}],
            "biome_noise": {
                "scale": 0.003,
                "octaves": 2,
                "persistence": 0.55,
                "lacunarity": 2.2,
                "threshold": 0.5,
                "seed": 1,
            },
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestCompoundSystem(unittest.TestCase):
    def test_linked_chests_share_storage_root(self):
        world = _linked_chest_world()
        cs = world.compound_system
        root = cs.get_root("dungeon_loot")
        self.assertIsNotNone(root)
        self.assertFalse(root.is_colony_compound)
        self.assertEqual(cs.count_active_access("dungeon_loot"), 2)

        chest_a = world.world_object_system.get("chest_a")
        chest_b = world.world_object_system.get("chest_b")
        self.assertTrue(chest_a.deposit_access)
        self.assertTrue(chest_a.withdraw_access)
        self.assertEqual(chest_a.parent_id, "dungeon_loot")
        self.assertEqual(chest_b.parent_id, "dungeon_loot")

    def test_deposit_at_one_chest_visible_from_root(self):
        world = _linked_chest_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=100, y=200)
        set_creature_compound_parent_ids(ant, ("dungeon_loot",))
        ant.world = world

        from src.sim.components.inventory import BiomassItem

        ant.inventory.slots[0].item = BiomassItem(amount=40.0)
        deposited = deposit_carried_to_parent(ant)
        self.assertAlmostEqual(deposited, 40.0)

        root = get_compound_root(world, "dungeon_loot")
        self.assertAlmostEqual(root.storage.stored_food, 40.0)

    def test_resolve_deposit_and_withdraw_use_nearest_access(self):
        world = _linked_chest_world()
        factory = CreatureFactory()
        ant = factory.create("springtail", world=world, x=490, y=300)
        set_creature_compound_parent_ids(ant, ("dungeon_loot",))

        parent, deposit_access = resolve_deposit_target(ant)
        self.assertEqual(parent.id, "dungeon_loot")
        self.assertEqual(deposit_access.id, "chest_b")

        _parent, withdraw_access = resolve_withdraw_target(ant)
        self.assertEqual(withdraw_access.id, "chest_b")

    def test_colony_site_still_has_colony_profile(self):
        world = World.from_json(
            {
                "name": "ColonyCompound",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "instances": [
                    {
                        "id": "red_ant",
                        "layer": "affiliation_site",
                        "type": "affiliation_site",
                        "x": 50,
                        "y": 50,
                    }
                ],
                "world": {
                    "biome_map_cell_size": 64,
                    "biomes": [{"name": "rich", "color": "#2E8B57", "spawn_rate_multiplier": 1.0}],
                    "biome_noise": {
                        "scale": 0.003,
                        "octaves": 2,
                        "persistence": 0.55,
                        "lacunarity": 2.2,
                        "threshold": 0.5,
                        "seed": 1,
                    },
                },
            }
        )
        root = world.compound_system.get_root("red_ant")
        self.assertTrue(root.is_colony_compound)


if __name__ == "__main__":
    unittest.main()
