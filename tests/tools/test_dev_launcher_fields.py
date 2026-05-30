"""dev_launcher_fields の単体テスト。"""
import json
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

    def test_worker_carry_speed_ref_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "worker_carry_speed_ref")
        value = read_field_value(spec)
        self.assertEqual(value, 160.0)

    def test_inventory_slot_count_roundtrip(self):
        import tempfile
        from pathlib import Path

        import dev_launcher_fields as mod
        from dev_launcher_fields import FieldSpec

        with tempfile.TemporaryDirectory() as tmp:
            cfg_dir = Path(tmp) / "config"
            cfg_dir.mkdir()
            path = cfg_dir / "ant.json"
            path.write_text(
                json.dumps(
                    {
                        "name": "test_ant",
                        "inventory": {
                            "slot_count": 2,
                            "slots": [
                                {"max_mass": 50, "allowed_kinds": ["biomass"]},
                                {"max_mass": 50, "allowed_kinds": ["biomass"]},
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )
            old_root = mod.project_root
            mod.project_root = lambda: Path(tmp)
            try:
                count_spec = FieldSpec(
                    "c",
                    "働きアリ",
                    "c",
                    "h",
                    "ant.json",
                    "int",
                    handler="inventory_slot_count",
                )
                mass_spec = FieldSpec(
                    "m",
                    "働きアリ",
                    "m",
                    "h",
                    "ant.json",
                    "float",
                    handler="inventory_uniform_slot_max_mass",
                )
                self.assertEqual(read_field_value(count_spec), 2)
                write_field_value(count_spec, 3)
                self.assertEqual(read_field_value(count_spec), 3)
                write_field_value(mass_spec, 120.0)
                data = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(len(data["inventory"]["slots"]), 3)
                self.assertTrue(
                    all(s["max_mass"] == 120.0 for s in data["inventory"]["slots"])
                )
            finally:
                mod.project_root = old_root

    def test_soldier_combat_attack_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "soldier_combat_attack")
        value = read_field_value(spec)
        self.assertEqual(value, 1.45)


if __name__ == "__main__":
    unittest.main()
