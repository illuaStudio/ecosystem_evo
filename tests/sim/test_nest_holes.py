"""??????? ID?????????????"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.creature_helpers import (
    is_in_creature_territory,
    is_point_in_nest_territory,
    resolve_colony_id,
)
from tests.sim.world_fixtures import affiliation_settings, set_colony_stored_food


def _colony_world(**overrides) -> World:
    data = {
        "name": "HoleTest",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "population_limits": {
            "red_ant": 20,
            "red_ant_soldier": 10,
            "blue_ant": 20,
            "yellow_ant": 20,
        },
        "affiliation": {
            "access_food_cost": 250,
            "max_access_points": 8,
            "min_access_spacing": 120,
            **affiliation_settings(),
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestNestHolesAndColonyId(unittest.TestCase):
    def test_soldier_shares_colony_id_with_worker(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=110, y=100)
        world.add_creature(soldier)

        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        self.assertEqual(get_creature_affiliation_id(worker), "red_ant")
        self.assertEqual(get_creature_affiliation_id(soldier), "red_ant")
        self.assertIs(
            world.nest_system.get_creature_nest(soldier),
            world.nest_system.get_creature_nest(worker),
        )

    def test_distinct_colony_ids(self):
        world = _colony_world()
        factory = CreatureFactory()
        red = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(red)
        blue = factory.create("blue_ant", world=world, x=800, y=800)
        world.add_creature(blue)
        yellow = factory.create("yellow_ant", world=world, x=800, y=100)
        world.add_creature(yellow)

        red_nest = world.nest_system.get_creature_nest(red)
        blue_nest = world.nest_system.get_creature_nest(blue)
        yellow_nest = world.nest_system.get_creature_nest(yellow)
        ids = {red_nest.colony_id, blue_nest.colony_id, yellow_nest.colony_id}
        self.assertEqual(ids, {"red_ant", "blue_ant", "yellow_ant"})

    def test_place_hole_extends_territory(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        set_colony_stored_food(world, nest.colony_id, 5000.0)

        radius = 180.0
        edge_x = 200.0 + radius - 10
        self.assertTrue(is_point_in_nest_territory(world, nest, edge_x, 200.0))

        far_x = edge_x + radius - 10
        self.assertFalse(is_point_in_nest_territory(world, nest, far_x, 200.0))

        ok, _ = world.nest_system.try_place_hole(nest, edge_x, 200.0)
        self.assertTrue(ok)
        self.assertTrue(is_point_in_nest_territory(world, nest, far_x, 200.0))

    def test_place_hole_outside_territory_rejected(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=200, y=200)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        set_colony_stored_food(world, nest.colony_id, 5000.0)

        ok, msg = world.nest_system.try_place_hole(nest, 600.0, 600.0)
        self.assertFalse(ok)
        self.assertTrue(msg)

    def test_place_hole_costs_food(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=300, y=300)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        set_colony_stored_food(world, nest.colony_id, 400.0)
        before = nest.stored_food

        ok, _ = world.nest_system.try_place_hole(nest, 450.0, 300.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(nest.stored_food, before - 250.0)

    def test_place_hole_too_close_rejected(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        set_colony_stored_food(world, nest.colony_id, 5000.0)

        ok, _ = world.nest_system.try_place_hole(nest, 250.0, 100.0)
        self.assertTrue(ok)
        ok2, msg = world.nest_system.try_place_hole(nest, 260.0, 100.0)
        self.assertFalse(ok2)
        self.assertIn("120", msg)

    def test_soldier_territory_after_hole_expansion(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("red_ant_soldier", world=world, x=105, y=100)
        world.add_creature(soldier)
        nest = world.nest_system.get_creature_nest(worker)
        set_colony_stored_food(world, nest.colony_id, 5000.0)

        prey_x = 100.0 + 180 + 150
        prey = factory.create("Spider", world=world, x=prey_x, y=100)
        world.add_creature(prey)
        self.assertFalse(is_in_creature_territory(soldier, prey))

        world.nest_system.try_place_hole(nest, 270.0, 100.0)
        self.assertTrue(is_in_creature_territory(soldier, prey))

    def test_resolve_colony_id_join_species(self):
        from src.config import config

        soldier_cfg = config.get_species("red_ant_soldier").get("colony", {})
        self.assertEqual(resolve_colony_id("red_ant_soldier", soldier_cfg), "red_ant")


if __name__ == "__main__":
    unittest.main()
