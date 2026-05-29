"""巣穴設置・勢力 ID・テリトリー拡張のテスト。"""
import unittest

from src.entities.creature_factory import CreatureFactory
from src.systems.world import World
from src.utils.creature_helpers import (
    is_in_creature_territory,
    is_point_in_nest_territory,
    resolve_colony_id,
)


def _colony_world(**overrides) -> World:
    data = {
        "name": "HoleTest",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "population_limits": {
            "Ant": 20,
            "AntSoldier": 10,
            "EnemyAnt": 20,
        },
        "colony": {
            "hole_food_cost": 250,
            "max_holes": 8,
            "min_hole_spacing": 120,
            "hole_min_food_reserve": 72,
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestNestHolesAndColonyId(unittest.TestCase):
    def test_soldier_shares_colony_id_with_worker(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("AntSoldier", world=world, x=110, y=100)
        world.add_creature(soldier)

        self.assertEqual(worker.colony.colony_id, "ant")
        self.assertEqual(soldier.colony.colony_id, "ant")
        self.assertIs(
            world.nest_system.get_creature_nest(soldier),
            world.nest_system.get_creature_nest(worker),
        )

    def test_enemy_colony_id_distinct(self):
        world = _colony_world()
        factory = CreatureFactory()
        ant = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(ant)
        enemy = factory.create("EnemyAnt", world=world, x=800, y=800)
        world.add_creature(enemy)

        ant_nest = world.nest_system.get_creature_nest(ant)
        enemy_nest = world.nest_system.get_creature_nest(enemy)
        self.assertEqual(ant_nest.colony_id, "ant")
        self.assertEqual(enemy_nest.colony_id, "enemy_ant")
        self.assertNotEqual(ant_nest.colony_id, enemy_nest.colony_id)

    def test_place_hole_extends_territory(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=200, y=200)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        nest.stored_food = 5000.0

        radius = 180.0
        edge_x = 200.0 + radius - 10
        edge_y = 200.0
        self.assertTrue(is_point_in_nest_territory(world, nest, edge_x, edge_y))

        far_x = edge_x + radius - 10
        self.assertFalse(is_point_in_nest_territory(world, nest, far_x, 200.0))

        ok, _ = world.nest_system.try_place_hole(nest, edge_x, edge_y)
        self.assertTrue(ok)
        self.assertTrue(is_point_in_nest_territory(world, nest, far_x, 200.0))

    def test_place_hole_outside_territory_rejected(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=200, y=200)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        nest.stored_food = 5000.0

        ok, msg = world.nest_system.try_place_hole(nest, 600.0, 600.0)
        self.assertFalse(ok)
        self.assertIn("テリトリー外", msg)

    def test_place_hole_costs_food(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=300, y=300)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        nest.stored_food = 400.0
        before = nest.stored_food

        ok, _ = world.nest_system.try_place_hole(nest, 300.0 + 150.0, 300.0)
        self.assertTrue(ok)
        self.assertAlmostEqual(nest.stored_food, before - 250.0)

    def test_place_hole_too_close_rejected(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        nest = world.nest_system.get_creature_nest(worker)
        nest.stored_food = 5000.0

        ok, _ = world.nest_system.try_place_hole(nest, 250.0, 100.0)
        self.assertTrue(ok)
        ok2, msg = world.nest_system.try_place_hole(nest, 260.0, 100.0)
        self.assertFalse(ok2)
        self.assertIn("近すぎ", msg)

    def test_soldier_territory_after_hole_expansion(self):
        world = _colony_world()
        factory = CreatureFactory()
        worker = factory.create("Ant", world=world, x=100, y=100)
        world.add_creature(worker)
        soldier = factory.create("AntSoldier", world=world, x=105, y=100)
        world.add_creature(soldier)
        nest = world.nest_system.get_creature_nest(worker)
        nest.stored_food = 5000.0

        prey_x = 100.0 + 180 + 150
        prey = factory.create("Spider", world=world, x=prey_x, y=100)
        world.add_creature(prey)
        self.assertFalse(is_in_creature_territory(soldier, prey))

        world.nest_system.try_place_hole(nest, 100.0 + 170, 100.0)
        self.assertTrue(is_in_creature_territory(soldier, prey))

    def test_resolve_colony_id_join_species(self):
        from src.config import config

        soldier_cfg = config.get_species("AntSoldier").get("colony", {})
        self.assertEqual(resolve_colony_id("AntSoldier", soldier_cfg), "ant")


if __name__ == "__main__":
    unittest.main()
