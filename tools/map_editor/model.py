"""マップエディタ: 統一 MapObject モデルと world.json 読み書き。"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

WORLD_REL_PATH = "sim/worlds/world.json"


@dataclass
class MapObject:
    """マップ上の1配置（将来 object_types 参照に拡張可能）。"""

    uid: str
    layer: str
    type_ref: str
    x: float
    y: float
    props: Dict[str, Any] = field(default_factory=dict)
    source_id: Optional[str] = None

    def get(self, key: str, default: Any = None) -> Any:
        if key in self.props:
            return self.props[key]
        return default


class WorldMapDocument:
    """world.json を MapObject 列として編集し、保存時に各セクションへ展開する。"""

    def __init__(self, data: Dict[str, Any]) -> None:
        self.data = data
        self.objects: List[MapObject] = []
        self._load_objects()

    @classmethod
    def load(cls, relpath: str = WORLD_REL_PATH) -> "WorldMapDocument":
        from dev_launcher_fields import load_json

        return cls(copy.deepcopy(load_json(relpath)))

    def save(self, relpath: str = WORLD_REL_PATH) -> None:
        from dev_launcher_fields import save_json

        self._flush_objects()
        self.validate()
        save_json(relpath, self.data)

    def validate(self) -> None:
        from src.sim.systems.world import World

        preview = self.build_preview_data()
        World.from_json(preview)

    def build_preview_data(self) -> Dict[str, Any]:
        """プレビュー用: 初期スポーンなし・生態系 tick なし。"""
        data = copy.deepcopy(self.data)
        data["initial_spawns"] = {"defaults": data.get("initial_spawns", {}).get("defaults", {}), "groups": []}
        return data

    def rebuild_preview_world(self):
        from src.sim.systems.world import World

        return World.from_json(self.build_preview_data())

    def _load_objects(self) -> None:
        self.objects.clear()
        self._load_obstacles()
        self._load_zones()
        self._load_spawns()
        self._load_nests()

    def _flush_objects(self) -> None:
        by_layer: Dict[str, List[MapObject]] = {}
        for obj in self.objects:
            by_layer.setdefault(obj.layer, []).append(obj)
        self._flush_obstacles(by_layer.get("obstacle", []))
        self._flush_zones(by_layer.get("zone", []))
        self._flush_spawns(by_layer.get("spawn", []))
        self._flush_nests(by_layer.get("nest", []))

    def _new_uid(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    def _load_obstacles(self) -> None:
        block = self.data.get("obstacles") or {}
        for entry in block.get("sources") or []:
            if not isinstance(entry, dict):
                continue
            type_ref = str(entry.get("type", entry.get("shape", "rock")))
            props = {k: v for k, v in entry.items() if k not in ("type", "shape", "x", "y", "id")}
            self.objects.append(
                MapObject(
                    uid=self._new_uid("obs"),
                    layer="obstacle",
                    type_ref=type_ref,
                    x=float(entry.get("x", 0)),
                    y=float(entry.get("y", 0)),
                    props=props,
                    source_id=entry.get("id"),
                )
            )

    def _flush_obstacles(self, objects: List[MapObject]) -> None:
        block = self.data.setdefault("obstacles", {})
        block.setdefault("types", block.get("types") or {})
        sources = []
        for obj in objects:
            entry: Dict[str, Any] = {"type": obj.type_ref, "x": obj.x, "y": obj.y}
            if obj.source_id:
                entry["id"] = obj.source_id
            for key, val in obj.props.items():
                entry[key] = val
            sources.append(entry)
        block["sources"] = sources

    def _load_zones(self) -> None:
        block = self.data.get("zones") or {}
        for entry in block.get("sources") or []:
            if not isinstance(entry, dict):
                continue
            type_ref = str(entry.get("type", "poison_fog"))
            props = {k: v for k, v in entry.items() if k not in ("type", "x", "y", "id")}
            self.objects.append(
                MapObject(
                    uid=self._new_uid("zone"),
                    layer="zone",
                    type_ref=type_ref,
                    x=float(entry.get("x", 0)),
                    y=float(entry.get("y", 0)),
                    props=props,
                    source_id=entry.get("id"),
                )
            )

    def _flush_zones(self, objects: List[MapObject]) -> None:
        block = self.data.setdefault("zones", {})
        block.setdefault("defaults", block.get("defaults") or {"radius": 95.0})
        block.setdefault("types", block.get("types") or {})
        sources = []
        for obj in objects:
            entry: Dict[str, Any] = {"type": obj.type_ref, "x": obj.x, "y": obj.y}
            if obj.source_id:
                entry["id"] = obj.source_id
            for key, val in obj.props.items():
                entry[key] = val
            sources.append(entry)
        block["sources"] = sources

    def _load_spawns(self) -> None:
        block = self.data.get("spawn_emitters") or {}
        for entry in block.get("sources") or []:
            if not isinstance(entry, dict):
                continue
            type_ref = str(entry.get("type", "micro_fauna_mixed"))
            props = {k: v for k, v in entry.items() if k not in ("type", "x", "y", "id")}
            self.objects.append(
                MapObject(
                    uid=self._new_uid("spawn"),
                    layer="spawn",
                    type_ref=type_ref,
                    x=float(entry.get("x", 0)),
                    y=float(entry.get("y", 0)),
                    props=props,
                    source_id=entry.get("id"),
                )
            )

    def _flush_spawns(self, objects: List[MapObject]) -> None:
        block = self.data.setdefault("spawn_emitters", {})
        block.setdefault("defaults", block.get("defaults") or {})
        block.setdefault("types", block.get("types") or {})
        sources = []
        for obj in objects:
            entry: Dict[str, Any] = {"type": obj.type_ref, "x": obj.x, "y": obj.y}
            if obj.source_id:
                entry["id"] = obj.source_id
            for key, val in obj.props.items():
                entry[key] = val
            sources.append(entry)
        block["sources"] = sources

    def _load_nests(self) -> None:
        profiles = (self.data.get("colony") or {}).get("profiles") or {}
        for colony_id, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            if "nest_x" not in profile or "nest_y" not in profile:
                continue
            self.objects.append(
                MapObject(
                    uid=self._new_uid("nest"),
                    layer="nest",
                    type_ref=str(colony_id),
                    x=float(profile["nest_x"]),
                    y=float(profile["nest_y"]),
                    props={},
                    source_id=str(colony_id),
                )
            )

    def _flush_nests(self, objects: List[MapObject]) -> None:
        colony = self.data.setdefault("colony", {})
        profiles = colony.setdefault("profiles", {})
        for obj in objects:
            profile = profiles.setdefault(obj.type_ref, {})
            profile["nest_x"] = float(obj.x)
            profile["nest_y"] = float(obj.y)

    def objects_in_layer(self, layer: str) -> List[MapObject]:
        return [o for o in self.objects if o.layer == layer]

    def type_options(self, layer: str) -> List[str]:
        if layer == "obstacle":
            types = (self.data.get("obstacles") or {}).get("types") or {}
            return list(types.keys()) or ["rock", "fallen_log"]
        if layer == "zone":
            types = (self.data.get("zones") or {}).get("types") or {}
            return list(types.keys()) or ["poison_fog"]
        if layer == "spawn":
            types = (self.data.get("spawn_emitters") or {}).get("types") or {}
            return list(types.keys()) or ["micro_fauna_mixed"]
        if layer == "nest":
            profiles = (self.data.get("colony") or {}).get("profiles") or {}
            return list(profiles.keys()) or ["red_ant"]
        return []

    def resolve_radius(self, obj: MapObject) -> float:
        if obj.layer == "obstacle":
            types = (self.data.get("obstacles") or {}).get("types") or {}
            tdef = types.get(obj.type_ref) or {}
            if str(tdef.get("shape", "circle")).lower() == "rect":
                return max(float(tdef.get("width", 40)), float(tdef.get("height", 16))) * 0.5
            return float(obj.get("radius", tdef.get("radius", 20.0)))
        if obj.layer == "zone":
            defaults = (self.data.get("zones") or {}).get("defaults") or {}
            types = (self.data.get("zones") or {}).get("types") or {}
            tdef = types.get(obj.type_ref) or {}
            return float(obj.get("radius", tdef.get("radius", defaults.get("radius", 95.0))))
        if obj.layer == "spawn":
            defaults = (self.data.get("spawn_emitters") or {}).get("defaults") or {}
            types = (self.data.get("spawn_emitters") or {}).get("types") or {}
            tdef = types.get(obj.type_ref) or {}
            return float(obj.get("radius", tdef.get("radius", defaults.get("radius", 85.0))))
        if obj.layer == "nest":
            profile = ((self.data.get("colony") or {}).get("profiles") or {}).get(obj.type_ref) or {}
            return float(profile.get("territory_radius", 180.0))
        return 24.0

    def add_object(self, layer: str, type_ref: str, x: float, y: float) -> MapObject:
        if layer == "nest":
            existing = [o for o in self.objects if o.layer == "nest" and o.type_ref == type_ref]
            if existing:
                existing[0].x = float(x)
                existing[0].y = float(y)
                return existing[0]
        obj = MapObject(
            uid=self._new_uid(layer[:4]),
            layer=layer,
            type_ref=type_ref,
            x=float(x),
            y=float(y),
            props={},
        )
        self.objects.append(obj)
        return obj

    def remove_object(self, uid: str) -> None:
        self.objects = [o for o in self.objects if o.uid != uid]

    def find_at(self, layer: str, wx: float, wy: float, *, all_layers: bool = False) -> Optional[MapObject]:
        layers = [layer] if not all_layers else ["nest", "spawn", "zone", "obstacle"]
        best: Optional[MapObject] = None
        best_dist = float("inf")
        for obj in self.objects:
            if obj.layer not in layers:
                continue
            if obj.layer == "obstacle":
                types = (self.data.get("obstacles") or {}).get("types") or {}
                tdef = types.get(obj.type_ref) or {}
                if str(tdef.get("shape", "circle")).lower() == "rect":
                    hw = float(obj.get("width", tdef.get("width", 40))) * 0.5 + 4
                    hh = float(obj.get("height", tdef.get("height", 16))) * 0.5 + 4
                    if abs(wx - obj.x) <= hw and abs(wy - obj.y) <= hh:
                        dist = (wx - obj.x) ** 2 + (wy - obj.y) ** 2
                        if dist < best_dist:
                            best_dist = dist
                            best = obj
                    continue
            radius = self.resolve_radius(obj) + 6.0
            if obj.layer == "nest":
                radius = min(radius, 40.0)
            dist_sq = (wx - obj.x) ** 2 + (wy - obj.y) ** 2
            if dist_sq <= radius * radius and dist_sq < best_dist:
                best_dist = dist_sq
                best = obj
        return best
