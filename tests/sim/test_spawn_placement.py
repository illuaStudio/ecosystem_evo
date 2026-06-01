"""SpawnPlacementResolver ? initial_spawns ?????"""
import unittest

from src.sim.constants.micro_fauna import DEFAULT_MICRO_FAUNA_SPECIES
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from src.sim.utils.position_helpers import entity_xy
from src.sim.utils.spawn_placement import (
    SpawnAnchor,
    SpawnPlacementOptions,
    SpawnPlacementResolver,
    expand_initial_spawns,
)


def _placement_world(**overrides):
    data = {
        "name": "PlacementTest",
        "world_width": 1000,
        "world_height": 1000,
        "population_limits": {name: 50 for name in DEFAULT_MICRO_FAUNA_SPECIES},
        "affiliation": {
            "profiles": {
                "red_ant": {
                    "nest_x": 200,
                    "nest_y": 200,
                    "territory_radius": 180,
                    "spawn_exclusion_radius": 150,
                    "spawn_spread": 24,
                    "max_mass": 5000,
                    "initial_mass": 80,
                    "storage_leak_per_tick": 0,
                    "storage_leak_reserve_ratio": 0.15,
                }
            },
            "min_storage_reserve": 72,
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
                "seed": 11,
            },
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestSpawnPlacementResolver(unittest.TestCase):
    def test_area_anchor_stays_within_radius(self):
        world = _placement_world()
        resolver = SpawnPlacementResolver(world)
        anchor = SpawnAnchor(type="area", x=700, y=300, radius=60)
        opts = SpawnPlacementOptions(respect_zones=False, use_biome_weight=False, attempts=40)

        for _ in range(30):
            pos = resolver.pick(anchor, opts)
            self.assertIsNotNone(pos)
            x, y = pos
            dist = ((x - 700) ** 2 + (y - 300) ** 2) ** 0.5
            self.assertLessEqual(dist, 60.5)

    def test_profile_nest_anchor_near_colony_profile(self):
        world = _placement_world()
        resolver = SpawnPlacementResolver(world)
        anchor = SpawnAnchor(type="profile_nest", affiliation_id="red_ant", spread=24)
        pos = resolver.pick(
            anchor,
            SpawnPlacementOptions(respect_zones=False, use_biome_weight=False),
        )
        self.assertIsNotNone(pos)
        x, y = pos
        dist = ((x - 200) ** 2 + (y - 200) ** 2) ** 0.5
        self.assertLessEqual(dist, 24.5)

    def test_nest_anchor_uses_existing_nest(self):
        world = _placement_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=350, y=350)
        world.add_creature(queen)

        resolver = SpawnPlacementResolver(world)
        anchor = SpawnAnchor(type="nest", affiliation_id="red_ant", spread=24)
        pos = resolver.pick(
            anchor,
            SpawnPlacementOptions(respect_zones=False, use_biome_weight=False),
        )
        self.assertIsNotNone(pos)
        nest = world.nest_system.get_affiliation_root("red_ant")
        x, y = pos
        dist = ((x - nest.x) ** 2 + (y - nest.y) ** 2) ** 0.5
        self.assertLessEqual(dist, 24.5)

    def test_respect_zones_blocks_nest_clearing(self):
        world = _placement_world()
        resolver = SpawnPlacementResolver(world)
        anchor = SpawnAnchor(type="world")
        opts = SpawnPlacementOptions(respect_zones=True, attempts=40)

        for _ in range(40):
            pos = resolver.pick(anchor, opts)
            if pos is None:
                continue
            self.assertTrue(world.zone_system.is_spawn_allowed(pos[0], pos[1]))


class TestInitialSpawnsConfig(unittest.TestCase):
    def test_initial_spawns_places_in_configured_areas(self):
        world = _placement_world(
            initial_spawns={
                "defaults": {"respect_zones": False, "use_biome_weight": False},
                "groups": [
                    {
                        "anchor": {"type": "area", "x": 800, "y": 400, "radius": 50},
                        "entries": [{"species": "springtail", "count": 3}],
                    }
                ],
            }
        )
        springtails = [c for c in world.creatures if c.species.name == "springtail"]
        self.assertEqual(len(springtails), 3)
        for creature in springtails:
            x, y = entity_xy(creature)
            dist = ((x - 800) ** 2 + (y - 400) ** 2) ** 0.5
            self.assertLessEqual(dist, 50.5)

    def test_initial_entities_shorthand_still_works(self):
        world = _placement_world(
            initial_entities={"springtail": 2},
        )
        self.assertEqual(
            sum(1 for c in world.creatures if c.species.name == "springtail"),
            2,
        )

    def test_expand_initial_spawns_colony_group(self):
        world = _placement_world(
            initial_spawns={
                "groups": [
                    {
                        "placement": {"respect_zones": False},
                        "entries": [
                            {
                                "species": "red_ant_queen",
                                "count": 1,
                                "anchor": {"type": "profile_nest", "affiliation_id": "red_ant"},
                            },
                            {
                                "species": "red_ant",
                                "count": 1,
                                "anchor": {"type": "nest", "affiliation_id": "red_ant"},
                            },
                        ],
                    }
                ],
            }
        )
        entries = expand_initial_spawns(
            {
                "initial_spawns": {
                    "groups": [
                        {
                            "placement": {"respect_zones": False},
                            "entries": [
                                {
                                    "species": "red_ant_queen",
                                    "count": 1,
                                    "anchor": {"type": "profile_nest", "affiliation_id": "red_ant"},
                                }
                            ],
                        }
                    ]
                }
            },
            world,
        )
        self.assertEqual(entries[0].species, "red_ant_queen")
        self.assertEqual(entries[0].anchor.type, "profile_nest")
        queens = sum(1 for c in world.creatures if c.species.name == "red_ant_queen")
        workers = sum(1 for c in world.creatures if c.species.name == "red_ant")
        self.assertEqual(queens, 1)
        self.assertEqual(workers, 1)


if __name__ == "__main__":
    unittest.main()
