"""GameConfigStore と共有状態のテスト。"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))

from editor_server import shared_state
from editor_server.store import (
    GameConfigStore,
    validate_object_type,
    validate_resource_id,
    validate_species,
)


class TestEditorStore(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.species_dir = root / "species"
        self.object_types_dir = root / "object_types"
        self.species_dir.mkdir()
        self.object_types_dir.mkdir()
        self.store = GameConfigStore(
            species_dir=self.species_dir,
            object_types_dir=self.object_types_dir,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_catalog_lists_entries(self) -> None:
        (self.species_dir / "foo.json").write_text(
            json.dumps({"name": "foo", "description": "test ant"}),
            encoding="utf-8",
        )
        (self.object_types_dir / "rock.json").write_text(
            json.dumps({"id": "rock", "category": "obstacle", "label": "岩"}),
            encoding="utf-8",
        )
        cat = self.store.catalog()
        self.assertEqual(len(cat["species"]), 1)
        self.assertEqual(cat["species"][0]["id"], "foo")
        self.assertEqual(len(cat["object_types"]), 1)
        self.assertEqual(cat["object_types"][0]["id"], "rock")

    def test_save_species_rejects_name_mismatch(self) -> None:
        errors = self.store.save_species("foo", {"name": "bar"})
        self.assertTrue(errors)

    def test_save_species_roundtrip(self) -> None:
        data = {"name": "foo", "description": "ok", "traits": {}}
        self.assertEqual(self.store.save_species("foo", data), [])
        loaded = self.store.load_species("foo")
        self.assertEqual(loaded["name"], "foo")

    def test_save_object_type_rejects_id_mismatch(self) -> None:
        errors = self.store.save_object_type("rock", {"id": "boulder"})
        self.assertTrue(errors)

    def test_validate_species_color(self) -> None:
        errors = validate_species({"name": "x", "color": [1, 2]}, expected_name="x")
        self.assertTrue(any("color" in e for e in errors))

    def test_create_and_delete_species(self) -> None:
        self.assertEqual(self.store.create_species("new_bug"), [])
        self.assertTrue(self.store.species_path("new_bug").is_file())
        loaded = self.store.load_species("new_bug")
        self.assertEqual(loaded["name"], "new_bug")
        self.assertEqual(self.store.create_species("new_bug"), ["species already exists: new_bug"])
        self.assertEqual(self.store.delete_species("new_bug"), [])
        self.assertFalse(self.store.species_path("new_bug").is_file())

    def test_create_and_delete_object_type(self) -> None:
        self.assertEqual(self.store.create_object_type("test_rock"), [])
        self.assertTrue(self.store.object_type_path("test_rock").is_file())
        self.assertEqual(self.store.delete_object_type("test_rock"), [])

    def test_validate_resource_id(self) -> None:
        self.assertEqual(validate_resource_id("my_ant"), [])
        self.assertTrue(validate_resource_id("My_Ant"))
        self.assertTrue(validate_resource_id("../x"))


class TestSharedState(unittest.TestCase):
    def setUp(self) -> None:
        self._old = shared_state.SHARED_STATE_PATH
        self.tmp = tempfile.TemporaryDirectory()
        shared_state.SHARED_STATE_PATH = Path(self.tmp.name) / "state.json"

    def tearDown(self) -> None:
        shared_state.SHARED_STATE_PATH = self._old
        self.tmp.cleanup()

    def test_map_selection_roundtrip(self) -> None:
        shared_state.set_map_selection(uid="a1", layer="obstacle", type_id="rock", x=10.0, y=20.0)
        sel = shared_state.get_map_selection()
        self.assertEqual(sel["uid"], "a1")
        self.assertEqual(sel["layer"], "obstacle")
        shared_state.clear_map_selection()
        self.assertIsNone(shared_state.get_map_selection().get("uid"))


if __name__ == "__main__":
    unittest.main()
