"""object_capabilities 正規化（Phase 0）。"""
import unittest

from src.sim.utils.object_capabilities import (
    capabilities_of,
    has_capability,
    merge_type_with_instance,
    normalize_capabilities,
    resolve_geometry,
    type_definition,
    zone_effects_from_data,
)


class TestObjectCapabilities(unittest.TestCase):
    def test_capabilities_format_preserved(self):
        raw = {
            "id": "rock",
            "label": "岩",
            "capabilities": {
                "collision": {"shape": "circle", "radius": 22},
                "render": {"color": [1, 2, 3]},
            },
        }
        norm = normalize_capabilities(raw)
        self.assertEqual(norm["capabilities"]["collision"]["radius"], 22)
        self.assertEqual(norm["shape"], "circle")
        self.assertEqual(norm["radius"], 22)

    def test_legacy_obstacle_promoted_to_collision(self):
        raw = {
            "id": "rock",
            "category": "obstacle",
            "shape": "circle",
            "radius": 22,
        }
        caps = capabilities_of(raw)
        self.assertIn("collision", caps)
        self.assertEqual(caps["collision"]["radius"], 22)

    def test_legacy_zone_promoted(self):
        raw = {
            "id": "poison_fog",
            "category": "zone",
            "hp_drain_per_dt": 0.07,
            "field_tags": ["poison"],
        }
        caps = capabilities_of(raw)
        self.assertIn("zone", caps)
        effects = zone_effects_from_data(normalize_capabilities(raw))
        self.assertAlmostEqual(effects.hp_drain_per_dt, 0.07)
        self.assertIn("poison", effects.field_tags)

    def test_legacy_colony_storage_and_access(self):
        site = normalize_capabilities(
            {
                "id": "colony_site",
                "category": "colony",
                "role": "root",
                "max_food": 5000,
            }
        )
        self.assertIn("storage", capabilities_of(site))
        self.assertEqual(site["max_food"], 5000)

        access = normalize_capabilities(
            {
                "id": "colony_access",
                "category": "colony",
                "role": "access",
                "shelter": True,
                "deposit_access": True,
                "max_hp": 120,
            }
        )
        self.assertIn("access", capabilities_of(access))
        self.assertIn("combat", capabilities_of(access))
        self.assertTrue(has_capability(access, "access"))

    def test_merge_type_with_instance_overrides_zone(self):
        type_def = normalize_capabilities(
            {
                "id": "poison_belt",
                "category": "zone",
                "capabilities": {
                    "zone": {
                        "shape": "rect",
                        "width": 200,
                        "height": 60,
                        "hp_drain_per_dt": 0.08,
                    }
                },
            }
        )
        merged = merge_type_with_instance(
            type_def,
            {"layer": "zone", "type": "poison_belt", "x": 1, "y": 2, "width": 240},
            reserved_keys=frozenset({"id", "layer", "type", "x", "y"}),
        )
        shape, _r, half_w, half_h = resolve_geometry(merged, capability="zone")
        self.assertEqual(shape, "rect")
        self.assertAlmostEqual(half_w, 120.0)

    def test_type_definition_strips_meta(self):
        raw = {
            "id": "rock",
            "category": "obstacle",
            "label": "岩",
            "capabilities": {"collision": {"shape": "circle", "radius": 22}},
        }
        payload = type_definition(raw)
        self.assertNotIn("id", payload)
        self.assertNotIn("label", payload)
        self.assertEqual(payload["radius"], 22)


if __name__ == "__main__":
    unittest.main()
