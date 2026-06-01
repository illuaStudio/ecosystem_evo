"""world.instances[] と legacy sections の相互変換。"""
import copy
import unittest

from src.sim.systems.world import World
from src.sim.utils.world_instances import (
    collapse_legacy_to_instances,
    expand_instances_to_legacy,
    instance_to_source_entry,
    normalize_world_layout,
    source_entry_to_instance,
    uses_instances_format,
)


def _minimal_biome_world(**overrides):
    data = {
        "name": "InstanceTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"springtail": 10},
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
    return data


class TestWorldInstances(unittest.TestCase):
    def test_collapse_legacy_to_instances(self):
        data = _minimal_biome_world(
            obstacles={"sources": [{"type": "rock", "x": 10, "y": 20}]},
            zones={"sources": [{"type": "poison_fog", "x": 30, "y": 40, "radius": 80}]},
            spawn_emitters={"sources": [{"type": "patch", "x": 50, "y": 60}]},
            affiliation={"profiles": {"red_ant": {"nest_x": 100, "nest_y": 110}}},
        )
        instances = collapse_legacy_to_instances(data)
        layers = {inst["layer"] for inst in instances}
        self.assertEqual(layers, {"obstacle", "zone", "spawn", "colony_site", "colony_access"})
        self.assertEqual(len(instances), 5)

    def test_expand_instances_to_legacy(self):
        data = _minimal_biome_world(
            instances=[
                {"layer": "obstacle", "type": "rock", "x": 10, "y": 20},
                {"layer": "spawn", "type": "patch", "x": 50, "y": 60, "radius": 70},
                {"id": "red_ant", "layer": "nest", "type": "red_ant", "x": 100, "y": 110},
            ],
            affiliation={"profiles": {"red_ant": {"territory_radius": 180}}},
        )
        expand_instances_to_legacy(data)
        self.assertEqual(len(data["obstacles"]["sources"]), 1)
        self.assertEqual(data["obstacles"]["sources"][0]["type"], "rock")
        self.assertEqual(len(data["spawn_emitters"]["sources"]), 1)
        self.assertAlmostEqual(data["spawn_emitters"]["sources"][0]["radius"], 70.0)
        self.assertAlmostEqual(data["affiliation"]["profiles"]["red_ant"]["nest_x"], 100.0)
        self.assertAlmostEqual(data["affiliation"]["profiles"]["red_ant"]["nest_y"], 110.0)
        self.assertEqual(data["affiliation"]["profiles"]["red_ant"]["territory_radius"], 180)

    def test_roundtrip_entry_conversion(self):
        inst = source_entry_to_instance("zone", {"type": "poison_fog", "x": 1, "y": 2, "radius": 95})
        entry = instance_to_source_entry(inst)
        self.assertEqual(entry["type"], "poison_fog")
        self.assertAlmostEqual(entry["radius"], 95.0)

    def test_normalize_world_layout_expands_instances(self):
        raw = _minimal_biome_world(
            instances=[{"layer": "spawn", "type": "patch", "x": 200, "y": 300, "radius": 60}],
            spawn_emitters={"defaults": {"radius": 70}, "types": {"patch": {}}, "sources": []},
        )
        layout = normalize_world_layout(raw)
        self.assertEqual(len(layout["spawn_emitters"]["sources"]), 1)
        self.assertAlmostEqual(layout["spawn_emitters"]["sources"][0]["x"], 200.0)

    def test_world_loads_spawn_from_instances(self):
        world = World.from_json(
            _minimal_biome_world(
                instances=[
                    {"layer": "spawn", "type": "patch", "x": 200, "y": 300, "radius": 60},
                ],
                spawn_emitters={
                    "defaults": {"radius": 70, "species_pool": ["springtail"], "target_population": 5},
                    "types": {"patch": {}},
                    "sources": [],
                },
            )
        )
        self.assertEqual(len(world.spawn_system.emitters), 1)
        emitter = world.spawn_system.emitters[0]
        self.assertAlmostEqual(emitter.x, 200.0)
        self.assertAlmostEqual(emitter.radius, 60.0)

    def test_legacy_without_instances_still_works(self):
        world = World.from_json(
            _minimal_biome_world(
                spawn_emitters={
                    "defaults": {"radius": 70, "species_pool": ["springtail"], "target_population": 5},
                    "types": {"patch": {}},
                    "sources": [{"type": "patch", "x": 111, "y": 222}],
                },
            )
        )
        self.assertEqual(len(world.spawn_system.emitters), 1)
        self.assertAlmostEqual(world.spawn_system.emitters[0].x, 111.0)

    def test_uses_instances_format(self):
        self.assertFalse(uses_instances_format({"obstacles": {"sources": []}}))
        self.assertTrue(uses_instances_format({"instances": []}))

    def test_build_test_world_adds_colony_instances(self):
        from tests.sim.world_fixtures import build_test_world

        data = build_test_world(name="FixtureTest")
        layers = {inst["layer"] for inst in data["instances"]}
        self.assertIn("colony_site", layers)
        self.assertIn("colony_access", layers)
        world = World.from_json(data)
        self.assertTrue(world.world_object_system.has_colony_root("red_ant"))


if __name__ == "__main__":
    unittest.main()
