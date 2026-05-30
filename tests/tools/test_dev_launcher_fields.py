"""dev_launcher_fields の単体テスト。"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from dev_launcher_fields import (
    FieldSpec,
    _get_nested,
    _set_nested,
    coerce_value,
    read_field_value,
    write_field_value,
)


class TestDevLauncherFields(unittest.TestCase):
    def test_nested_get_set(self):
        data = {"traits": {"max_hp": 100.0}}
        self.assertEqual(_get_nested(data, ("traits", "max_hp")), 100.0)
        _set_nested(data, ("traits", "max_hp"), 200.0)
        self.assertEqual(data["traits"]["max_hp"], 200.0)

    def test_coerce_types(self):
        spec_f = FieldSpec("x", "c", "l", "h", "a.json", "float")
        spec_i = FieldSpec("x", "c", "l", "h", "a.json", "int")
        spec_b = FieldSpec("x", "c", "l", "h", "a.json", "bool")
        self.assertEqual(coerce_value(spec_f, "1.5"), 1.5)
        self.assertEqual(coerce_value(spec_i, "3"), 3)
        self.assertTrue(coerce_value(spec_b, "1"))

    def test_read_write_roundtrip(self):
        spec = FieldSpec(
            "test_hp",
            "女王",
            "HP",
            "help",
            "sim/species/red_ant_queen.json",
            "float",
            ("traits", "max_hp"),
        )
        original = read_field_value(spec)
        try:
            write_field_value(spec, float(original) + 1.0)
            self.assertEqual(read_field_value(spec), float(original) + 1.0)
        finally:
            write_field_value(spec, original)

    def test_reproduction_profile_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "queen_repro_food_cost")
        value = read_field_value(spec)
        self.assertEqual(value, 55)

    def test_territory_hp_regen_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "world_territory_hp_regen")
        value = read_field_value(spec)
        self.assertEqual(value, 0.012)

    def test_starvation_mult_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "sim_starvation_hp_mult")
        value = read_field_value(spec)
        self.assertEqual(value, 0.12)


if __name__ == "__main__":
    unittest.main()
