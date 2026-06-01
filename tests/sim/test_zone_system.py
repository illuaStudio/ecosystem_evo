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
        "affiliation": {
            "profiles": {
                "red_ant": {
                    "nest_x": 200,
                    "nest_y": 200,
                    "territory_radius": 180,
                    "spawn_exclusion_radius": 150,
                    "max_mass": 5000,
                    "initial_mass": 80,
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
            if z.affiliation_id == "red_ant" and z.effects.spawn_rate_multiplier == 0.0
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

    def test_nest_creation_syncs_clearing_zone_to_actual_position(self):
        world = World()
        for creature in list(world.creatures):
            world.remove_creature(creature)
        world.nest_system.clear_all_affiliation_sites()
        world.zone_system.zones.clear()
        world.world_object_system.objects.clear()
        world.world_object_system._children.clear()

        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=310, y=290)
        world.add_creature(queen)

        clearing = [
            z
            for z in world.zone_system.zones
            if z.affiliation_id == "red_ant" and z.effects.spawn_rate_multiplier == 0.0
        ]
        self.assertEqual(len(clearing), 1)
        nest = world.nest_system.get_affiliation_root("red_ant")
        self.assertIsNotNone(nest)
        self.assertAlmostEqual(clearing[0].x, nest.x)
        self.assertAlmostEqual(clearing[0].y, nest.y)
        self.assertFalse(world.zone_system.is_spawn_allowed(nest.x, nest.y))


class TestZoneRectShape(unittest.TestCase):
    def test_rect_zone_contains_axis_aligned(self):
        world = _zone_world(
            zones={
                "sources": [
                    {
                        "type": "poison_belt",
                        "shape": "rect",
                        "x": 400,
                        "y": 400,
                        "width": 200,
                        "height": 60,
                        "hp_drain_per_dt": 0.1,
                        "field_tags": ["poison"],
                    }
                ]
            }
        )
        zone = world.zone_system.zones[0]
        self.assertTrue(zone.is_rect)
        self.assertAlmostEqual(zone.half_w, 100.0)
        self.assertAlmostEqual(zone.half_h, 30.0)
        self.assertTrue(zone.contains(400, 400))
        self.assertTrue(zone.contains(450, 415))
        self.assertFalse(zone.contains(510, 400))
        self.assertFalse(zone.contains(400, 440))

    def test_rect_poison_applies_inside_only(self):
        world = World.from_json(
            {
                "name": "RectPoison",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "zones": {
                    "sources": [
                        {
                            "type": "poison_belt",
                            "shape": "rect",
                            "x": 300,
                            "y": 300,
                            "width": 120,
                            "height": 80,
                            "hp_drain_per_dt": 0.15,
                            "field_tags": ["poison"],
                        }
                    ]
                },
            }
        )
        factory = CreatureFactory()
        inside = factory.create("red_ant", world=world, x=300, y=300)
        outside = factory.create("red_ant", world=world, x=500, y=500)

        inside_mod = sample_field_modifiers(world, inside)
        outside_mod = sample_field_modifiers(world, outside)
        self.assertAlmostEqual(inside_mod.hp_drain_per_dt, 0.15)
        self.assertAlmostEqual(outside_mod.hp_drain_per_dt, 0.0)

    def test_instances_rect_zone_loads_from_object_type(self):
        world = World.from_json(
            {
                "name": "RectInstance",
                "world_width": 1000,
                "world_height": 1000,
                "initial_entities": {},
                "instances": [
                    {
                        "layer": "zone",
                        "type": "poison_belt",
                        "x": 200,
                        "y": 200,
                    }
                ],
                "zones": {"defaults": {"radius": 95.0}, "sources": []},
            }
        )
        zone = next(z for z in world.zone_system.zones if z.zone_type == "poison_belt")
        self.assertTrue(zone.is_rect)
        self.assertAlmostEqual(zone.half_w, 100.0)
        self.assertAlmostEqual(zone.half_h, 30.0)
        self.assertTrue(world.zone_system.sample_at(200, 200).hp_drain_per_dt > 0)
        self.assertAlmostEqual(world.zone_system.sample_at(400, 400).hp_drain_per_dt, 0.0)


if __name__ == "__main__":
    unittest.main()
