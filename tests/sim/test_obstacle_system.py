"""ObstacleSystem（円・矩形）の歩行判定と移動解決。"""
import unittest

from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.movement_system import MovementSystem
from src.sim.systems.world import World
from src.sim.utils.spawn_placement import (
    SpawnAnchor,
    SpawnPlacementOptions,
    SpawnPlacementResolver,
)


def _obstacle_world(**overrides):
    data = {
        "name": "ObstacleTest",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "population_limits": {"springtail": 50},
        "obstacles": {
            "sources": [
                {"shape": "circle", "x": 500, "y": 500, "radius": 40},
                {"shape": "rect", "x": 200, "y": 300, "width": 80, "height": 20},
            ]
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


class TestObstacleSystem(unittest.TestCase):
    def test_circle_blocks_center(self):
        world = _obstacle_world()
        self.assertFalse(world.is_valid_position(500, 500, body_radius=0))
        self.assertFalse(world.is_valid_position(500, 500, body_radius=5))
        self.assertTrue(world.is_valid_position(500, 500 + 80, body_radius=5))

    def test_rect_blocks_center(self):
        world = _obstacle_world()
        self.assertFalse(world.is_valid_position(200, 300, body_radius=3))
        self.assertTrue(world.is_valid_position(200, 300 + 60, body_radius=3))

    def test_spawn_rejects_obstacle_interior(self):
        world = _obstacle_world()
        resolver = SpawnPlacementResolver(world)
        opts = SpawnPlacementOptions(
            respect_zones=False,
            use_biome_weight=False,
            attempts=40,
            spawn_body_radius=5.0,
        )
        found_inside = False
        for _ in range(40):
            pos = resolver.pick(SpawnAnchor(type="world"), opts)
            if pos is None:
                continue
            x, y = pos
            if (x - 500) ** 2 + (y - 500) ** 2 < 30 ** 2:
                found_inside = True
        self.assertFalse(found_inside)

    def test_movement_pushes_out_of_rock(self):
        world = _obstacle_world()
        factory = CreatureFactory()
        creature = factory.create("springtail", world=world, x=500, y=500)
        world.add_creature(creature)
        creature.traits["base_size"] = 5.0

        MovementSystem.finish_move(creature, world)

        self.assertTrue(world.is_valid_position(creature.position.x, creature.position.y, 5.0))
        dist = ((creature.position.x - 500) ** 2 + (creature.position.y - 500) ** 2) ** 0.5
        self.assertGreaterEqual(dist, 40 + 5 - 0.5)

    def test_spatial_index_returns_only_nearby(self):
        world = _obstacle_world()
        system = world.obstacle_system
        near = list(system.iter_near(500, 500, 50))
        far = list(system.iter_near(50, 50, 10))
        self.assertEqual(len(near), 1)
        self.assertEqual(len(far), 0)
        self.assertIsInstance(near[0], type(system.obstacles[0]))


if __name__ == "__main__":
    unittest.main()
