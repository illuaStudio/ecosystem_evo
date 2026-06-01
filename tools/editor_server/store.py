"""config/game の species / object_types の読み書きと検証。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from editor_server.paths import OBJECT_TYPES_DIR, SPECIES_DIR

_RESOURCE_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
_MAX_RESOURCE_ID_LEN = 64


@dataclass(frozen=True)
class CatalogEntry:
    id: str
    file: str
    label: str
    summary: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "id": self.id,
            "file": self.file,
            "label": self.label,
            "summary": self.summary,
        }


class GameConfigStore:
    def __init__(
        self,
        species_dir: Path = SPECIES_DIR,
        object_types_dir: Path = OBJECT_TYPES_DIR,
    ) -> None:
        self.species_dir = species_dir
        self.object_types_dir = object_types_dir

    def catalog(self) -> Dict[str, List[Dict[str, str]]]:
        return {
            "species": [e.to_dict() for e in self.list_species()],
            "object_types": [e.to_dict() for e in self.list_object_types()],
        }

    def list_species(self) -> List[CatalogEntry]:
        entries: List[CatalogEntry] = []
        if not self.species_dir.is_dir():
            return entries
        for path in sorted(self.species_dir.glob("*.json")):
            data = self._read_json(path)
            if data is None:
                continue
            name = str(data.get("name") or path.stem)
            desc = str(data.get("description") or "")[:120]
            entries.append(
                CatalogEntry(
                    id=name,
                    file=path.name,
                    label=name,
                    summary=desc,
                )
            )
        return entries

    def list_object_types(self) -> List[CatalogEntry]:
        entries: List[CatalogEntry] = []
        if not self.object_types_dir.is_dir():
            return entries
        for path in sorted(self.object_types_dir.glob("*.json")):
            data = self._read_json(path)
            if data is None:
                continue
            type_id = str(data.get("id") or path.stem)
            label = str(data.get("label") or type_id)
            category = str(data.get("category") or "")
            summary = f"{category}" if category else label
            entries.append(
                CatalogEntry(
                    id=type_id,
                    file=path.name,
                    label=label,
                    summary=summary,
                )
            )
        return entries

    def species_path(self, name: str) -> Path:
        return self.species_dir / f"{name}.json"

    def object_type_path(self, type_id: str) -> Path:
        return self.object_types_dir / f"{type_id}.json"

    def load_species(self, name: str) -> Dict[str, Any]:
        path = self.species_path(name)
        if not path.is_file():
            raise FileNotFoundError(f"species not found: {name}")
        data = self._read_json(path)
        if data is None:
            raise ValueError(f"invalid JSON: {path.name}")
        return data

    def load_object_type(self, type_id: str) -> Dict[str, Any]:
        path = self.object_type_path(type_id)
        if not path.is_file():
            raise FileNotFoundError(f"object type not found: {type_id}")
        data = self._read_json(path)
        if data is None:
            raise ValueError(f"invalid JSON: {path.name}")
        return data

    def save_species(self, name: str, data: Dict[str, Any]) -> List[str]:
        errors = validate_species(data, expected_name=name)
        if errors:
            return errors
        path = self.species_path(name)
        self._write_json(path, data)
        return []

    def save_object_type(self, type_id: str, data: Dict[str, Any]) -> List[str]:
        errors = validate_object_type(data, expected_id=type_id)
        if errors:
            return errors
        path = self.object_type_path(type_id)
        self._write_json(path, data)
        return []

    def create_species(
        self, name: str, data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        errors = validate_resource_id(name)
        if self.species_path(name).is_file():
            errors.append(f"species already exists: {name}")
        if errors:
            return errors
        payload = data if data is not None else default_species_template(name)
        return self.save_species(name, payload)

    def delete_species(self, name: str) -> List[str]:
        errors = validate_resource_id(name)
        path = self.species_path(name)
        if not path.is_file():
            errors.append(f"species not found: {name}")
        if errors:
            return errors
        path.unlink()
        return []

    def create_object_type(
        self, type_id: str, data: Optional[Dict[str, Any]] = None
    ) -> List[str]:
        errors = validate_resource_id(type_id)
        if self.object_type_path(type_id).is_file():
            errors.append(f"object type already exists: {type_id}")
        if errors:
            return errors
        payload = data if data is not None else default_object_type_template(type_id)
        return self.save_object_type(type_id, payload)

    def delete_object_type(self, type_id: str) -> List[str]:
        errors = validate_resource_id(type_id)
        path = self.object_type_path(type_id)
        if not path.is_file():
            errors.append(f"object type not found: {type_id}")
        if errors:
            return errors
        path.unlink()
        return []

    @staticmethod
    def _read_json(path: Path) -> Optional[Dict[str, Any]]:
        try:
            with open(path, encoding="utf-8") as f:
                item = json.load(f)
            return item if isinstance(item, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    @staticmethod
    def _write_json(path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")


def validate_resource_id(resource_id: str) -> List[str]:
    errors: List[str] = []
    if not resource_id or not str(resource_id).strip():
        errors.append("id is required")
        return errors
    rid = str(resource_id).strip()
    if len(rid) > _MAX_RESOURCE_ID_LEN:
        errors.append(f"id too long (max {_MAX_RESOURCE_ID_LEN})")
    if ".." in rid or "/" in rid or "\\" in rid:
        errors.append("invalid id")
    elif not _RESOURCE_ID_RE.match(rid):
        errors.append(
            "id must be lowercase letters, digits, underscore; "
            "start with a letter (e.g. my_rock)"
        )
    return errors


def default_species_template(name: str) -> Dict[str, Any]:
    return {
        "name": name,
        "description": "",
        "color": [160, 160, 160],
        "traits": {
            "base_size": 10.0,
            "base_speed": 0.5,
            "base_vision": 200.0,
            "max_hp": 100.0,
            "max_satiety": 100.0,
            "metabolism_per_tick": 0.01,
            "satiety_hungry_below": 0.15,
            "satiety_full_above": 0.85,
            "corpse_decompose_rate": 0.01,
            "starvation_hp_per_tick": 0.001,
        },
        "mind": {"type": "utility", "actions": []},
    }


def default_object_type_template(type_id: str) -> Dict[str, Any]:
    return {
        "id": type_id,
        "category": "obstacle",
        "label": type_id,
        "capabilities": {
            "collision": {"shape": "circle", "radius": 20},
            "render": {"color": [120, 120, 120]},
        },
    }


def validate_species(data: Any, *, expected_name: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["body must be a JSON object"]
    name = data.get("name")
    if not name:
        errors.append("missing required field 'name'")
    elif str(name) != expected_name:
        errors.append(f"'name' must be {expected_name!r} (got {name!r})")
    if "traits" in data and not isinstance(data["traits"], dict):
        errors.append("'traits' must be an object")
    if "color" in data:
        color = data["color"]
        if not isinstance(color, list) or len(color) != 3:
            errors.append("'color' must be an array of 3 numbers")
        elif not all(isinstance(c, (int, float)) for c in color):
            errors.append("'color' values must be numbers")
    return errors


def validate_object_type(data: Any, *, expected_id: str) -> List[str]:
    errors: List[str] = []
    if not isinstance(data, dict):
        return ["body must be a JSON object"]
    type_id = data.get("id")
    if not type_id:
        errors.append("missing required field 'id'")
    elif str(type_id) != expected_id:
        errors.append(f"'id' must be {expected_id!r} (got {type_id!r})")
    if "capabilities" in data and not isinstance(data["capabilities"], dict):
        errors.append("'capabilities' must be an object")
    return errors
