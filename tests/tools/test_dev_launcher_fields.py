"""dev_launcher_fields の単体テスト。"""
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from dev_launcher_fields import (
    FieldSpec,
    SimRateContext,
    _get_nested,
    _set_nested,
    coerce_value,
    format_live_rate_preview,
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

        spec = next(s for s in FIELD_SPECS if s.field_id == "queen_repro_max_members")
        value = read_field_value(spec)
        self.assertEqual(value, 10)

    def test_format_config_key(self):
        from dev_launcher_fields import FIELD_SPECS, format_config_key, format_field_reference

        queen_hp = next(s for s in FIELD_SPECS if s.field_id == "queen_max_hp")
        self.assertEqual(format_config_key(queen_hp), "traits.max_hp")
        self.assertIn("traits.max_hp", format_field_reference(queen_hp))

        feed = next(s for s in FIELD_SPECS if s.field_id == "queen_nest_feed_per_tick")
        key = format_config_key(feed)
        self.assertEqual(key, "nest_feed.feed_per_tick")
        self.assertIn("nest_feed.feed_per_tick", format_field_reference(feed))

        inv = next(s for s in FIELD_SPECS if s.field_id == "worker_inv_slot_count")
        self.assertEqual(format_config_key(inv), "inventory.slot_count")

    def test_nested_ai_subtabs(self):
        from dev_launcher_fields import (
            FIELD_SPECS,
            ai_subtab_key,
            ai_subtabs_for_category,
            fields_for_ai_subtab,
            fields_for_category_main,
            fields_for_main_section,
            has_nested_ai_tabs,
            launcher_tabs,
        )

        self.assertIn("女王", launcher_tabs())
        self.assertNotIn("AI", " ".join(launcher_tabs()))
        self.assertTrue(has_nested_ai_tabs("女王"))

        queen_main = fields_for_category_main("女王")
        queen_hp = next(s for s in FIELD_SPECS if s.field_id == "queen_max_hp")
        self.assertIn(queen_hp, queen_main)
        self.assertIn(queen_hp, fields_for_main_section("女王", "個体"))

        worker_feed = next(
            s for s in FIELD_SPECS if s.field_id == "worker_nest_feed_per_tick"
        )
        self.assertIn(worker_feed, fields_for_main_section("働きアリ", "食事"))
        self.assertNotIn(
            worker_feed,
            fields_for_ai_subtab("働きアリ", "食事"),
        )

        queen_subtabs = ai_subtabs_for_category("女王")
        self.assertIn("食事", queen_subtabs)

    def test_main_sections_group_nest_fields(self):
        from dev_launcher_fields import fields_for_main_section, main_sections_for_category

        queen_sections = main_sections_for_category("女王")
        self.assertLess(
            queen_sections.index("個体"),
            queen_sections.index("食事"),
        )
        queen_body = fields_for_main_section("女王", "個体")
        queen_feed = fields_for_main_section("女王", "食事")
        queen_nest = fields_for_main_section("女王", "巣・コロニー")
        self.assertTrue(any(s.field_id == "queen_max_hp" for s in queen_body))
        self.assertTrue(any(s.field_id == "queen_metabolism" for s in queen_feed))
        self.assertFalse(any(s.field_id == "queen_nest_food_init" for s in queen_body))
        self.assertTrue(any(s.field_id == "queen_nest_food_init" for s in queen_nest))

        world_sections = main_sections_for_category("ワールド")
        self.assertIn("開始時の個体", world_sections)
        self.assertIn("赤コロニー（巣）", world_sections)

    def test_all_scanned_params_covered(self):
        from dev_launcher_fields import (
            FIELD_SPECS,
            _SKIP_ACTION_PARAMS,
            _SKIP_JSON_PATHS,
            _spec_lookup_key,
            load_json,
            _get_nested,
        )

        covered = {_spec_lookup_key(s) for s in FIELD_SPECS}
        missing: list[tuple] = []

        for rel in (
            "sim/species/red_ant_queen.json",
            "sim/species/red_ant.json",
            "sim/species/red_ant_soldier.json",
        ):
            data = load_json(rel)
            for act in data.get("mind", {}).get("actions", []):
                for pk, pv in (act.get("params") or {}).items():
                    if (act["name"], pk) in _SKIP_ACTION_PARAMS:
                        continue
                    if pv is None or not isinstance(pv, (int, float, bool)):
                        continue
                    key = ("action", rel, "", act["name"], pk)
                    if key not in covered:
                        missing.append(key)
            for key, val in (data.get("traits") or {}).items():
                if isinstance(val, (int, float, bool)):
                    path = ("traits", key)
                    if path not in _SKIP_JSON_PATHS:
                        tkey = ("path", rel, path)
                        if tkey not in covered:
                            missing.append(tkey)

        repro = load_json("game/reproduction_profiles.json")
        for pid, prof in repro.items():
            for act in prof.get("actions", []):
                for pk, pv in (act.get("params") or {}).items():
                    if pv is None or not isinstance(pv, (int, float, bool)):
                        continue
                    key = (
                        "action",
                        "game/reproduction_profiles.json",
                        pid,
                        act["name"],
                        pk,
                    )
                    if key not in covered:
                        missing.append(key)

        self.assertEqual(missing, [], f"未掲載: {missing[:5]}")

    def test_territory_hp_regen_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "world_territory_hp_regen")
        value = read_field_value(spec)
        self.assertEqual(value, 0.012)

    def test_worker_starvation_hp_read(self):
        from dev_launcher_fields import FIELD_SPECS

        spec = next(s for s in FIELD_SPECS if s.field_id == "worker_starvation_hp_per_tick")
        value = read_field_value(spec)
        self.assertAlmostEqual(value, 0.0012)

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


class TestLiveRatePreview(unittest.TestCase):
    def setUp(self):
        from dev_launcher_fields import FIELD_SPECS

        self.ctx = SimRateContext(fps=60, sim_ticks_per_step=10, simulation_speed=1.0)
        self.worker_metabolism = next(
            s for s in FIELD_SPECS if s.field_id == "worker_metabolism"
        )
        self.worker_feed = next(
            s for s in FIELD_SPECS if s.field_id == "worker_nest_feed_per_tick"
        )

    def test_metabolism_preview_per_second(self):
        text = format_live_rate_preview(self.worker_metabolism, 0.01, self.ctx)
        self.assertIn("1 秒あたり", text)
        self.assertIn("0.6000", text)

    def test_feed_preview_uses_sim_steps_not_dt(self):
        text = format_live_rate_preview(self.worker_feed, 0.5, self.ctx)
        self.assertIn("1 秒あたり", text)
        self.assertIn("3.00", text)

    def test_feed_preview_includes_bite_gain_from_get_field(self):
        def get_field(field_id: str) -> float | None:
            values = {
                "worker_nest_feed_bite_gain": 1.15,
                "worker_max_satiety": 100.0,
            }
            return values.get(field_id)

        text = format_live_rate_preview(
            self.worker_feed, 0.5, self.ctx, get_field=get_field
        )
        self.assertIn("0.5750", text)


if __name__ == "__main__":
    unittest.main()
