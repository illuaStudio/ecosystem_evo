"""汎用 SpawnSystem（エミッター + ambient）のテスト。"""
import unittest

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.systems.spawn_system import count_alive_in_pool, count_alive_in_radius
from src.sim.systems.world import World
from src.sim.utils.stats_helpers import count_alive_by_species


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
        "spawn_emitters": {
            "ambient": {
                "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
                "target_population": 5,
                "spawn_rate_per_dt": 5.0,
                "nest_exclusion_radius": 120.0,
                "max_spawns_per_tick": 5,
                "position_attempts": 16,
                "margin": 80,
            },
        },
        "affiliation": {
            "profiles": {
                "red_ant": {
                    "nest_x": 120,
                    "nest_y": 120,
                    "territory_radius": 180,
                    "max_mass": 5000,
                    "initial_mass": 80,
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


class TestSpawnSystemAmbient(unittest.TestCase):
    def test_spawns_toward_target_population(self):
        world = World.from_json(_minimal_world_data())
        world.nest_system.create_nest(120, 120, "red_ant", affiliation_id="red_ant")
        pool = list(DEFAULT_MICRO_FAUNA_SPECIES)

        self.assertEqual(count_alive_in_pool(world, pool), 0)
        for _ in range(20):
            world.spawn_system.update(1.0)

        alive = count_alive_in_pool(world, pool)
        self.assertGreater(alive, 0)
        self.assertLessEqual(alive, 5)

    def test_respects_nest_exclusion_radius(self):
        world = World.from_json(_minimal_world_data())
        world.nest_system.create_nest(500, 500, "red_ant", affiliation_id="red_ant")
        pool = list(DEFAULT_MICRO_FAUNA_SPECIES)

        for _ in range(30):
            world.spawn_system.update(1.0)

        exclusion = float(world.spawn_system.ambient.nest_exclusion_radius)
        for creature in world.creatures:
            if creature.species.name not in pool:
                continue
            dist = ((creature.position.x - 500) ** 2 + (creature.position.y - 500) ** 2) ** 0.5
            self.assertGreaterEqual(dist, exclusion)

    def test_legacy_ambient_spawns_config(self):
        data = _minimal_world_data()
        data.pop("spawn_emitters")
        data["ambient_spawns"] = {
            "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
            "target_population": 3,
            "spawn_rate_per_dt": 5.0,
            "nest_exclusion_radius": 0.0,
            "max_spawns_per_tick": 3,
        }
        world = World.from_json(data)
        self.assertIsNotNone(world.spawn_system.ambient)
        for _ in range(10):
            world.spawn_system.update(1.0)
        self.assertGreater(count_alive_in_pool(world, DEFAULT_MICRO_FAUNA_SPECIES), 0)


class TestSpawnSystemPointEmitters(unittest.TestCase):
    def test_point_emitter_spawns_within_radius(self):
        data = _minimal_world_data(
            spawn_emitters={
                "defaults": {
                    "species_pool": ["soil_mite"],
                    "target_population": 4,
                    "spawn_rate_per_dt": 5.0,
                    "radius": 60.0,
                    "max_spawns_per_tick": 4,
                    "use_biome_weight": False,
                },
                "sources": [{"x": 700, "y": 300, "radius": 60.0}],
            }
        )
        world = World.from_json(data)
        for _ in range(15):
            world.spawn_system.update(1.0)

        self.assertGreater(count_alive_by_species(world, "soil_mite"), 0)
        for creature in world.creatures:
            if creature.species.name != "soil_mite":
                continue
            dist = ((creature.position.x - 700) ** 2 + (creature.position.y - 300) ** 2) ** 0.5
            self.assertLessEqual(dist, 60.0)

    def test_point_emitter_uses_local_population_cap(self):
        data = _minimal_world_data(
            spawn_emitters={
                "defaults": {
                    "species_pool": ["springtail"],
                    "target_population": 3,
                    "spawn_rate_per_dt": 10.0,
                    "radius": 50.0,
                    "max_spawns_per_tick": 5,
                    "use_biome_weight": False,
                },
                "sources": [{"x": 200, "y": 200}],
            }
        )
        world = World.from_json(data)
        emitter = world.spawn_system.emitters[0]
        for _ in range(20):
            world.spawn_system.update(1.0)

        local = count_alive_in_radius(world, ["springtail"], emitter.x, emitter.y, emitter.radius)
        self.assertLessEqual(local, 3)

    def test_typed_emitter_species_pool(self):
        data = _minimal_world_data(
            spawn_emitters={
                "defaults": {
                    "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
                    "target_population": 5,
                    "spawn_rate_per_dt": 5.0,
                    "radius": 55.0,
                    "use_biome_weight": False,
                },
                "types": {
                    "mite_only": {"species_pool": ["soil_mite"], "target_population": 4}
                },
                "sources": [{"x": 500, "y": 500, "type": "mite_only"}],
            }
        )
        world = World.from_json(data)
        for _ in range(20):
            world.spawn_system.update(1.0)

        mites = count_alive_by_species(world, "soil_mite")
        others = count_alive_in_pool(world, DEFAULT_MICRO_FAUNA_SPECIES) - mites
        self.assertGreater(mites, 0)
        self.assertEqual(others, 0)


if __name__ == "__main__":
    unittest.main()
