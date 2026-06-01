"""WorldObjectSystem（親子階層・備蓄）の Phase D テスト。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.world_object_helpers import (
    deposit_carried_to_parent,
    resolve_deposit_target,
    resolve_shelter_from_parents,
    set_creature_nest_parent_ids,
    iter_colony_access_xy,
    colony_food_ratio,
    colony_access_count,
)
from tests.sim.test_hole_combat_helpers import damage_colony_access, list_colony_access, primary_access


def _object_world(**overrides):
    data = {
        "name": "ObjectWorld",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "instances": [
            {
                "id": "red_ant",
                "layer": "colony_site",
                "type": "colony_site",
                "role": "root",
                "x": 200,
                "y": 200,
            },
            {
                "id": "red_ant_access_main",
                "layer": "colony_access",
                "type": "colony_access",
                "parent": "red_ant",
                "x": 200,
                "y": 200,
            },
        ],
        "colony": {
            "min_food_reserve": 72,
            "profiles": {
                "red_ant": {
                    "nest_x": 200,
                    "nest_y": 200,
                    "territory_radius": 180,
                    "max_food": 5000,
                    "initial_stored_food": 100,
                    "food_leak_per_tick": 0,
                    "food_leak_reserve_ratio": 0.15,
                    "spawn_spread": 28,
                    "spawn_exclusion_radius": 150,
                }
            },
        },
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


class TestWorldObjectSystem(unittest.TestCase):
    def test_bootstrap_creates_nest_from_parent(self):
        world = _object_world()
        root = world.world_object_system.get("red_ant")
        self.assertIsNotNone(root)
        self.assertAlmostEqual(root.storage.stored_food, 100.0)
        nest = world.nest_system.get_colony_nest("red_ant")
        self.assertIsNotNone(nest)
        self.assertAlmostEqual(nest.stored_food, 100.0)
        self.assertEqual(len(list_colony_access(world, "red_ant")), 1)

    def test_parent_child_hierarchy(self):
        world = _object_world()
        children = world.world_object_system.get_children("red_ant")
        self.assertEqual(len(children), 1)
        self.assertEqual(children[0].parent_id, "red_ant")

    def test_deposit_to_parent_inventory(self):
        world = _object_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=200, y=200)
        set_creature_nest_parent_ids(ant, ("red_ant",))
        world.add_creature(ant)

        from src.sim.components.inventory import BiomassItem

        ant.inventory.slots[0].item = BiomassItem(amount=25.0)

        deposited = deposit_carried_to_parent(ant)
        self.assertAlmostEqual(deposited, 25.0)
        root = world.world_object_system.get("red_ant")
        self.assertAlmostEqual(root.storage.stored_food, 125.0)
        nest = world.nest_system.get_colony_nest("red_ant")
        self.assertAlmostEqual(nest.stored_food, 125.0)

    def test_shelter_resolves_child_access(self):
        world = _object_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=210, y=200)
        set_creature_nest_parent_ids(ant, ("red_ant",))
        ref = resolve_shelter_from_parents(ant)
        self.assertIsNotNone(ref)
        self.assertEqual(ref.kind, "compound_access")
        self.assertEqual(ref.parent_id, "red_ant")

    def test_resolve_deposit_target(self):
        world = _object_world()
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=205, y=200)
        set_creature_nest_parent_ids(ant, ("red_ant",))
        parent, access = resolve_deposit_target(ant)
        self.assertIsNotNone(parent)
        self.assertIsNotNone(access)
        self.assertEqual(parent.id, "red_ant")

    def test_hole_damage_syncs_access_hp(self):
        world = _object_world()
        world.affiliation_species = {"red_ant": ("red_ant",), "blue_ant": ("blue_ant",)}
        access = primary_access(world, "red_ant")
        self.assertIsNotNone(access)
        self.assertAlmostEqual(access.hp, 120.0)

        damage_colony_access(
            world, "red_ant", access, 30.0, attacker_colony_id="blue_ant"
        )
        access = primary_access(world, "red_ant")
        self.assertIsNotNone(access)
        self.assertAlmostEqual(access.hp, 90.0)

    def test_hole_destroy_removes_access_object(self):
        world = _object_world()
        world.affiliation_species = {"red_ant": ("red_ant",), "blue_ant": ("blue_ant",)}
        access = primary_access(world, "red_ant")
        access.hp = 0.8
        damage_colony_access(
            world, "red_ant", access, 1.0, attacker_colony_id="blue_ant"
        )
        self.assertEqual(world.world_object_system.count_active_access("red_ant"), 0)

    def test_defeat_colony_clears_all_access(self):
        world = _object_world()
        world.affiliation_species = {"red_ant": ("red_ant",), "blue_ant": ("blue_ant",)}
        ws = world.world_object_system
        ws.add_access_point("red_ant", 210, 210)
        self.assertEqual(ws.count_active_access("red_ant"), 2)

        world.nest_system.defeat_colony("red_ant")
        self.assertEqual(ws.count_active_access("red_ant"), 0)
        self.assertIn("red_ant", world.defeated_colonies)
        self.assertIsNone(world.nest_system.get_colony_nest("red_ant"))
        self.assertIsNotNone(ws.get("red_ant"))

    def test_try_place_hole_deducts_parent_storage(self):
        world = _object_world()
        nest = world.nest_system.get_colony_nest("red_ant")
        root = world.world_object_system.get("red_ant")
        root.storage.stored_food = 1000.0
        nest.stored_food = 1000.0
        cost = float(world.colony_settings.get("access_food_cost", world.colony_settings.get("hole_food_cost", 250)))

        ok, _msg = world.nest_system.try_place_hole(nest, 360, 200)
        self.assertTrue(ok)
        self.assertAlmostEqual(root.storage.stored_food, 1000.0 - cost)
        self.assertAlmostEqual(nest.stored_food, root.storage.stored_food)
        self.assertEqual(world.world_object_system.count_active_access("red_ant"), 2)

    def test_colony_display_helpers(self):
        world = _object_world()
        nest = world.nest_system.get_colony_nest("red_ant")
        root = world.world_object_system.get("red_ant")
        root.storage.stored_food = 250.0
        root.storage.max_food = 500.0

        pts = iter_colony_access_xy(world, "red_ant")
        self.assertEqual(len(pts), 1)
        self.assertAlmostEqual(colony_food_ratio(world, "red_ant"), 0.5)
        self.assertEqual(colony_access_count(world, "red_ant"), 1)

    def test_obstacle_instances_load_geometry(self):
        world = World.from_json(
            {
                "name": "ObstacleObjectWorld",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "instances": [
                    {
                        "id": "rock_a",
                        "layer": "obstacle",
                        "type": "rock",
                        "x": 500,
                        "y": 500,
                    },
                    {
                        "id": "log_a",
                        "layer": "obstacle",
                        "type": "fallen_log",
                        "x": 200,
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
        )
        ws = world.world_object_system
        rock = ws.get("rock_a")
        log = ws.get("log_a")
        self.assertTrue(rock.is_obstacle)
        self.assertAlmostEqual(rock.radius, 22.0)
        self.assertTrue(log.is_obstacle)
        self.assertAlmostEqual(log.half_w, 42.0)
        self.assertAlmostEqual(log.half_h, 8.0)
        self.assertFalse(world.is_valid_position(500, 500, body_radius=0))
        self.assertFalse(world.is_valid_position(200, 300, body_radius=3))

    def test_zone_instances_load_into_world_objects(self):
        world = World.from_json(
            {
                "name": "ZoneObjectWorld",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "instances": [
                    {
                        "id": "poison_a",
                        "layer": "zone",
                        "type": "poison_fog",
                        "x": 300,
                        "y": 300,
                    }
                ],
                "zones": {"defaults": {"radius": 95.0}, "sources": []},
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
        ws = world.world_object_system
        zone_obj = ws.get("poison_a")
        self.assertIsNotNone(zone_obj)
        self.assertTrue(zone_obj.is_zone)
        self.assertAlmostEqual(zone_obj.radius, 95.0)
        sample = world.zone_system.sample_at(300, 300)
        self.assertAlmostEqual(sample.hp_drain_per_dt, 0.07)
        self.assertIn("poison", sample.field_tags)
        self.assertAlmostEqual(world.zone_system.sample_at(900, 900).hp_drain_per_dt, 0.0)


if __name__ == "__main__":
    unittest.main()
