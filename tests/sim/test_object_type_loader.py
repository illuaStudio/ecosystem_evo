"""object_types グローバル catalog と world インライン types のマージ。"""
import unittest

from src.config import config
from src.sim.systems.world import World
from src.sim.utils.object_type_loader import (
    list_type_ids,
    merge_obstacle_config,
    merge_zone_config,
    resolve_type_def,
    type_definition,
)


class TestObjectTypeLoader(unittest.TestCase):
    def test_config_loads_global_object_types(self):
        self.assertIn("rock", config.object_types)
        self.assertIn("poison_fog", config.object_types)
        self.assertEqual(config.object_types["rock"]["category"], "obstacle")
        self.assertEqual(config.object_types["poison_fog"]["category"], "zone")

    def test_type_definition_strips_meta_keys(self):
        raw = {
            "id": "rock",
            "category": "obstacle",
            "label": "岩",
            "shape": "circle",
            "radius": 22,
        }
        payload = type_definition(raw)
        self.assertNotIn("id", payload)
        self.assertIn("capabilities", payload)
        self.assertEqual(payload["shape"], "circle")
        self.assertEqual(payload["radius"], 22)

    def test_merge_obstacle_config_includes_global_types(self):
        merged = merge_obstacle_config({"sources": []})
        self.assertIn("rock", merged["types"])
        self.assertEqual(merged["types"]["rock"]["shape"], "circle")
        self.assertIn("fallen_log", merged["types"])

    def test_inline_types_override_global(self):
        merged = merge_obstacle_config(
            {
                "types": {"rock": {"shape": "circle", "radius": 99}},
                "sources": [],
            }
        )
        self.assertEqual(merged["types"]["rock"]["radius"], 99)

    def test_merge_zone_config_includes_nest_clearing(self):
        merged = merge_zone_config({"defaults": {"radius": 95.0}, "sources": []})
        self.assertIn("nest_clearing", merged["types"])
        self.assertEqual(merged["types"]["nest_clearing"]["spawn_rate_multiplier"], 0.0)

    def test_world_loads_obstacle_from_global_type(self):
        world = World.from_json(
            {
                "name": "ObjectTypeTest",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "obstacles": {
                    "sources": [{"type": "rock", "x": 100, "y": 100}],
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
        )
        self.assertEqual(len(world.obstacle_system.obstacles), 1)
        obs = world.obstacle_system.obstacles[0]
        self.assertAlmostEqual(obs.radius, 22.0)

    def test_world_loads_zone_from_global_type(self):
        world = World.from_json(
            {
                "name": "ObjectTypeZoneTest",
                "world_width": 500,
                "world_height": 500,
                "initial_entities": {},
                "zones": {
                    "defaults": {"radius": 95.0},
                    "sources": [{"type": "poison_fog", "x": 200, "y": 200}],
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
        )
        sample = world.zone_system.sample_at(200, 200)
        self.assertAlmostEqual(sample.hp_drain_per_dt, 0.07)
        self.assertIn("poison", sample.field_tags)

    def test_list_type_ids_merges_inline(self):
        ids = list_type_ids("obstacle", inline_types={"custom_rock": {"radius": 10}})
        self.assertIn("rock", ids)
        self.assertIn("custom_rock", ids)

    def test_resolve_type_def_prefers_inline(self):
        tdef = resolve_type_def(
            "obstacle",
            "rock",
            inline_types={"rock": {"radius": 55}},
        )
        self.assertEqual(tdef["radius"], 55)


if __name__ == "__main__":
    unittest.main()
