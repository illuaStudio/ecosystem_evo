"""WorldMapDocument の roundtrip テスト。"""
import copy
import unittest

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
        "colony": {
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


class TestWorldMapDocument(unittest.TestCase):
    def test_loads_all_layers(self):
        doc = WorldMapDocument(_minimal_world())
        layers = {o.layer for o in doc.objects}
        self.assertEqual(layers, {"obstacle", "zone", "spawn", "nest"})

    def test_roundtrip_flush(self):
        data = _minimal_world()
        doc = WorldMapDocument(copy.deepcopy(data))
        doc.objects[0].x = 150
        doc._flush_objects()
        self.assertAlmostEqual(doc.data["obstacles"]["sources"][0]["x"], 150)

    def test_validate_preview(self):
        doc = WorldMapDocument(_minimal_world())
        doc.validate()

    def test_find_and_remove(self):
        doc = WorldMapDocument(_minimal_world())
        hit = doc.find_at("obstacle", 100, 100)
        self.assertIsNotNone(hit)
        uid = hit.uid
        doc.remove_object(uid)
        self.assertIsNone(doc.find_at("obstacle", 100, 100))

    def test_nest_move_updates_profile(self):
        doc = WorldMapDocument(_minimal_world())
        nest = doc.objects_in_layer("nest")[0]
        nest.x = 999
        nest.y = 888
        doc._flush_objects()
        profile = doc.data["colony"]["profiles"]["red_ant"]
        self.assertAlmostEqual(profile["nest_x"], 999)
        self.assertAlmostEqual(profile["nest_y"], 888)


if __name__ == "__main__":
    unittest.main()
