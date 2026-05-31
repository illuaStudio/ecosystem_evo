"""環境スポーン（AmbientSpawner）のテスト。"""
import unittest

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.systems.ambient_spawner import count_alive_in_pool
from src.sim.systems.world import World


def _minimal_world_data(**overrides):
    data = {
        "name": "Test",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {
            "red_ant_queen": 0,
            "red_ant": 0,
        },
        "population_limits": {
            name: 50 for name in DEFAULT_MICRO_FAUNA_SPECIES
        },
        "ambient_spawns": {
            "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
            "target_population": 5,
            "spawn_rate_per_dt": 5.0,
            "nest_exclusion_radius": 120.0,
            "max_attempts_per_tick": 5,
            "position_attempts": 16,
            "margin": 80,
        },
        "colony": {
            "profiles": {
                "red_ant": {
                    "nest_x": 120,
                    "nest_y": 120,
                    "territory_radius": 180,
                    "max_food": 5000,
                    "initial_stored_food": 80,
                }
            }
        },
        "world": {
            "biome_map_cell_size": 64,
            "biomes": [
                {"name": "rich", "color": "#2E8B57", "spawn_rate_multiplier": 1.0},
                {"name": "poor", "color": "#8F9E6E", "spawn_rate_multiplier": 0.25},
            ],
            "biome_noise": {
                "scale": 0.003,
                "octaves": 2,
                "persistence": 0.55,
                "lacunarity": 2.2,
                "threshold": 0.5,
                "seed": 7,
            },
        },
    }
    data.update(overrides)
    return data


class TestAmbientSpawner(unittest.TestCase):
    def test_spawns_toward_target_population(self):
        world = World.from_json(_minimal_world_data())
        world.nest_system.create_nest(120, 120, "red_ant", colony_id="red_ant")
        pool = list(DEFAULT_MICRO_FAUNA_SPECIES)

        self.assertEqual(count_alive_in_pool(world, pool), 0)
        for _ in range(20):
            world.ambient_spawner.update(1.0)

        alive = count_alive_in_pool(world, pool)
        self.assertGreater(alive, 0)
        self.assertLessEqual(alive, 5)

    def test_respects_nest_exclusion_radius(self):
        world = World.from_json(_minimal_world_data())
        world.nest_system.create_nest(500, 500, "red_ant", colony_id="red_ant")
        pool = list(DEFAULT_MICRO_FAUNA_SPECIES)

        for _ in range(30):
            world.ambient_spawner.update(1.0)

        exclusion = float(world.ambient_spawner.config["nest_exclusion_radius"])
        for creature in world.creatures:
            if creature.species.name not in pool:
                continue
            dist = ((creature.position.x - 500) ** 2 + (creature.position.y - 500) ** 2) ** 0.5
            self.assertGreaterEqual(dist, exclusion)


if __name__ == "__main__":
    unittest.main()
