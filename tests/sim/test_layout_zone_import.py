"""layout の旧 zones / field_emitters → instances 正規化。"""
import unittest

from src.sim.systems.world import World
from src.sim.layout.import_layout import expand_layout_instances
from src.sim.layout.zone_import import instances_from_field_emitters_block


class TestLayoutZoneImport(unittest.TestCase):
    def test_field_emitters_become_zone_instances(self):
        inst = instances_from_field_emitters_block(
            {
                "sources": [
                    {
                        "type": "poison_fog",
                        "x": 10,
                        "y": 20,
                        "radius": 40,
                        "hp_drain_per_dt": 0.05,
                        "tags": ["poison"],
                    }
                ]
            }
        )
        self.assertEqual(len(inst), 1)
        self.assertEqual(inst[0]["layer"], "zone")
        self.assertEqual(inst[0]["type"], "poison_fog")

    def test_world_loads_legacy_field_emitters_as_zones(self):
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
        zone_objs = world.world_object_system.iter_zones()
        self.assertEqual(len(list(zone_objs)), 1)

    def test_expand_does_not_duplicate_explicit_instances(self):
        layout = {
            "instances": [{"layer": "zone", "type": "poison_belt", "x": 1, "y": 2}],
            "field_emitters": {
                "sources": [{"type": "poison_fog", "x": 3, "y": 4, "radius": 10}]
            },
        }
        expanded = expand_layout_instances(layout)
        self.assertEqual(len(expanded), 2)


if __name__ == "__main__":
    unittest.main()
