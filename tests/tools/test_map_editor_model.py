"""WorldMapDocument の roundtrip テスト。"""
import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from map_editor.model import WorldMapDocument


def _minimal_world():
    return {
        "name": "EditorTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"springtail": 10},
        "obstacles": {
            "types": {"rock": {"shape": "circle", "radius": 20}},
            "sources": [{"type": "rock", "x": 100, "y": 100}],
        },
        "zones": {
            "defaults": {"radius": 80},
            "types": {"poison_fog": {"hp_drain_per_dt": 0.05}},
            "sources": [{"type": "poison_fog", "x": 400, "y": 400}],
        },
        "spawn_emitters": {
            "defaults": {"radius": 70},
            "types": {"patch": {}},
            "sources": [{"type": "patch", "x": 200, "y": 300, "radius": 60}],
        },
        "affiliation": {
            "profiles": {
                "red_ant": {"nest_x": 120, "nest_y": 120, "territory_radius": 100},
            }
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


def _instances_world():
    data = _minimal_world()
    doc = WorldMapDocument(copy.deepcopy(data))
    doc.migrate_to_instances_format()
    return doc.data


class TestWorldMapDocument(unittest.TestCase):
    def test_loads_all_layers_from_legacy(self):
        doc = WorldMapDocument(_minimal_world())
        layers = {o.layer for o in doc.objects}
        self.assertEqual(layers, {"obstacle", "zone", "spawn", "affiliation_site", "affiliation_access"})

    def test_loads_all_layers_from_instances(self):
        doc = WorldMapDocument(_instances_world())
        layers = {o.layer for o in doc.objects}
        self.assertIn("affiliation_site", layers)
        self.assertIn("obstacle", layers)

    def test_roundtrip_flush_writes_instances(self):
        doc = WorldMapDocument(_instances_world())
        rock = next(o for o in doc.objects if o.layer == "obstacle")
        rock.x = 150
        doc._flush_objects()
        instances = doc.data["instances"]
        rock_inst = next(i for i in instances if i["layer"] == "obstacle")
        self.assertAlmostEqual(rock_inst["x"], 150)
        self.assertEqual(doc.data["obstacles"]["sources"], [])

    def test_validate_preview(self):
        doc = WorldMapDocument(_instances_world())
        doc.validate()

    def test_find_and_remove(self):
        doc = WorldMapDocument(_instances_world())
        hit = doc.find_at("obstacle", 100, 100)
        self.assertIsNotNone(hit)
        uid = hit.uid
        doc.remove_object(uid)
        self.assertIsNone(doc.find_at("obstacle", 100, 100))

    def test_nest_move_updates_profile_and_instances(self):
        doc = WorldMapDocument(_instances_world())
        nest = next(o for o in doc.objects if o.layer == "affiliation_site")
        doc.move_site_with_access(nest, 999, 888)
        doc._flush_objects()
        profile = doc.data["affiliation"]["profiles"]["red_ant"]
        self.assertAlmostEqual(profile["nest_x"], 999)
        self.assertAlmostEqual(profile["nest_y"], 888)
        nest_inst = next(i for i in doc.data["instances"] if i["layer"] == "affiliation_site")
        self.assertAlmostEqual(nest_inst["x"], 999)
        access_inst = next(i for i in doc.data["instances"] if i["layer"] == "affiliation_access")
        self.assertAlmostEqual(access_inst["x"], 999)
        self.assertAlmostEqual(access_inst["y"], 888)

    def test_move_site_drags_access_children(self):
        doc = WorldMapDocument(_instances_world())
        site = next(o for o in doc.objects if o.layer == "affiliation_site")
        access = next(o for o in doc.objects if o.layer == "affiliation_access")
        doc.move_site_with_access(site, site.x + 50, site.y + 30)
        self.assertAlmostEqual(access.x, site.x)
        self.assertAlmostEqual(access.y, site.y)

    def test_global_object_types_without_inline(self):
        data = _instances_world()
        data["obstacles"] = {"sources": []}
        data["zones"] = {"defaults": {"radius": 80}, "sources": []}
        doc = WorldMapDocument(data)
        self.assertIn("rock", doc.type_options("obstacle"))
        self.assertIn("poison_fog", doc.type_options("zone"))
        doc.validate()
        doc._flush_objects()
        self.assertNotIn("types", doc.data.get("obstacles", {}))
        self.assertNotIn("types", doc.data.get("zones", {}))

    def test_migrate_to_instances_format(self):
        doc = WorldMapDocument(_minimal_world())
        doc.migrate_to_instances_format()
        self.assertIn("instances", doc.data)
        self.assertEqual(len(doc.data["instances"]), 5)

    def test_multiple_obstacles_get_unique_instance_ids(self):
        from src.sim.systems.world import World

        doc = WorldMapDocument(_instances_world())
        for i in range(3):
            doc.add_object("obstacle", "rock", 100.0 + i * 40, 200.0)
        doc._flush_objects()
        rock_ids = [
            i["id"]
            for i in doc.data["instances"]
            if i.get("layer") == "obstacle"
        ]
        self.assertEqual(len(rock_ids), 4)
        self.assertEqual(len(set(rock_ids)), len(rock_ids))

        world = World.from_json(doc.build_preview_data())
        rocks = [o for o in world.world_object_system.iter_obstacles() if o.type_ref == "rock"]
        self.assertEqual(len(rocks), 4)
        self.assertEqual(len(world.obstacle_system.obstacles), 4)


if __name__ == "__main__":
    unittest.main()
