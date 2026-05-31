"""ZoneSystem（スポーン除外・毒霧）の Phase 1 テスト。"""
import unittest

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.spawn_system import count_alive_in_pool
from src.sim.systems.world import World
from src.sim.utils.field_modifiers import apply_field_hp_effects, sample_field_modifiers


def _zone_world(**overrides):
    data = {
        "name": "ZoneTest",
        "world_width": 1000,
        "world_height": 1000,
        "initial_entities": {},
        "population_limits": {name: 50 for name in DEFAULT_MICRO_FAUNA_SPECIES},
        "colony": {
            "profiles": {
                "red_ant": {
                    "nest_x": 200,
                    "nest_y": 200,
                    "territory_radius": 180,
                    "spawn_exclusion_radius": 150,
                    "max_food": 5000,
                    "initial_stored_food": 80,
                }
            }
        },
        "spawn_emitters": {
            "ambient": {
                "species_pool": list(DEFAULT_MICRO_FAUNA_SPECIES),
                "target_population": 8,
                "spawn_rate_per_dt": 5.0,
                "max_spawns_per_tick": 5,
                "position_attempts": 24,
                "margin": 80,
                "nest_exclusion_radius": 0.0,
            }
        },
        "world": {
            "biome_map_cell_size": 64,
            "biomes": [
                {"name": "rich", "color": "#2E8B57", "spawn_rate_multiplier": 1.0},
            ],
            "biome_noise": {
                "scale": 0.003,
                "octaves": 2,
                "persistence": 0.55,
                "lacunarity": 2.2,
                "threshold": 0.5,
                "seed": 3,
            },
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestZoneSpawnExclusion(unittest.TestCase):
    def test_colony_profile_generates_nest_clearing_zone(self):
        world = _zone_world()
        clearing = [
            z
            for z in world.zone_system.zones
            if z.colony_id == "red_ant" and z.effects.spawn_rate_multiplier == 0.0
        ]
        self.assertEqual(len(clearing), 1)
        self.assertAlmostEqual(clearing[0].x, 200.0)
        self.assertAlmostEqual(clearing[0].radius, 150.0)

    def test_spawn_blocked_inside_nest_clearing(self):
        world = _zone_world()
        self.assertFalse(world.zone_system.is_spawn_allowed(200, 200))
        self.assertTrue(world.zone_system.is_spawn_allowed(500, 500))

    def test_ambient_spawns_respect_nest_clearing_zone(self):
        world = _zone_world()
        pool = list(DEFAULT_MICRO_FAUNA_SPECIES)
        for _ in range(30):
            world.spawn_system.update(1.0)

        self.assertGreater(count_alive_in_pool(world, pool), 0)
        for creature in world.creatures:
            if creature.species.name not in pool:
                continue
            dist = (
                (creature.position.x - 200) ** 2 + (creature.position.y - 200) ** 2
            ) ** 0.5
            self.assertGreaterEqual(dist, 150.0)

    def test_spawn_multiplier_uses_min_across_zones(self):
        world = _zone_world(
            zones={
                "sources": [
                    {
                        "type": "nest_clearing",
                        "x": 400,
                        "y": 400,
                        "radius": 100,
                        "spawn_rate_multiplier": 0.0,
                    },
                    {
                        "x": 400,
                        "y": 400,
                        "radius": 100,
                        "effects": {"spawn_rate_multiplier": 0.5},
                    },
                ]
            }
        )
        self.assertEqual(world.zone_system.sample_at(400, 400).spawn_rate_multiplier, 0.0)
        self.assertAlmostEqual(world.zone_system.sample_at(600, 600).spawn_rate_multiplier, 1.0)


class TestZonePoisonFog(unittest.TestCase):
    def test_poison_zone_drains_hp(self):
        world = World.from_json(
            {
                "name": "PoisonZone",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "zones": {
                    "sources": [
                        {
                            "type": "poison_fog",
                            "x": 300,
                            "y": 300,
                            "radius": 80,
                            "hp_drain_per_dt": 0.12,
                            "field_tags": ["poison"],
                        }
                    ]
                },
            }
        )
        factory = CreatureFactory()
        ant = factory.create("red_ant", world=world, x=300, y=300)
        ant.hp = 100.0

        modifiers = sample_field_modifiers(world, ant)
        self.assertAlmostEqual(modifiers.hp_drain_per_dt, 0.12)

        apply_field_hp_effects(ant, dt=10.0)
        self.assertLess(ant.hp, 100.0)

    def test_legacy_field_emitters_imported_as_zones(self):
        world = World.from_json(
            {
                "name": "LegacyFog",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "field_emitters": {
                    "sources": [
                        {
                            "type": "poison_fog",
                            "x": 100,
                            "y": 100,
                            "radius": 50,
                            "hp_drain_per_dt": 0.05,
                            "tags": ["poison"],
                        }
                    ]
                },
            }
        )
        self.assertEqual(len(world.zone_system.zones), 1)
        self.assertAlmostEqual(world.zone_system.zones[0].effects.hp_drain_per_dt, 0.05)


if __name__ == "__main__":
    unittest.main()
