"""マップエディタ: 統一 MapObject モデルと world.json 読み書き。"""
from __future__ import annotations

import copy
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.sim.utils.object_type_loader import list_type_ids, resolve_type_def
from src.sim.utils.world_instances import (
    collapse_legacy_to_instances,
    instance_to_map_object_props,
    map_object_to_instance,
    uses_instances_format,
)

WORLD_REL_PATH = "sim/worlds/world.json"


@dataclass
class MapObject:
    """マップ上の1配置（world.instances[] と対応）。"""

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


from src.sim.utils.compound_layers import ACCESS_LAYERS, ROOT_LAYERS

SITE_LAYERS = ROOT_LAYERS
ACCESS_LAYER = "affiliation_access"


class WorldMapDocument:
    """world.json を MapObject 列として編集し、保存時に instances[] へ書き出す。"""

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
        data["initial_spawns"] = {
            "defaults": data.get("initial_spawns", {}).get("defaults", {}),
            "groups": [],
        }
        return data

    def rebuild_preview_world(self):
        from src.sim.systems.world import World

        return World.from_json(self.build_preview_data())

    def _load_objects(self) -> None:
        self.objects.clear()
        if uses_instances_format(self.data):
            self._load_from_instances()
            return
        self._load_from_legacy_sections()

    def _load_from_instances(self) -> None:
        for entry in self.data.get("instances") or []:
            if not isinstance(entry, dict):
                continue
            layer = str(entry.get("layer", ""))
            if not layer:
                continue
            self.objects.append(
                MapObject(
                    uid=self._new_uid(layer[:4]),
                    layer=layer,
                    type_ref=str(entry.get("type", "custom")),
                    x=float(entry.get("x", 0.0)),
                    y=float(entry.get("y", 0.0)),
                    props=instance_to_map_object_props(entry),
                    source_id=entry.get("id"),
                )
            )
            if entry.get("parent") is not None:
                self.objects[-1].props["parent"] = entry["parent"]
            if entry.get("role") is not None:
                self.objects[-1].props["role"] = entry["role"]

    def _load_from_legacy_sections(self) -> None:
        self._load_obstacles()
        self._load_zones()
        self._load_spawns()
        self._load_nests()

    def _flush_objects(self) -> None:
        self._flush_instances()
        site_objects = self.objects_in_layer("nest") + self.objects_in_layer("affiliation_site")
        self._flush_nests(site_objects)
        self._clear_legacy_sources()

    def _flush_instances(self) -> None:
        instances = [map_object_to_instance(obj) for obj in self.objects]
        self.data["instances"] = instances

    def _clear_legacy_sources(self) -> None:
        obstacles = self.data.setdefault("obstacles", {})
        if isinstance(obstacles, dict):
            obstacles.pop("types", None)
            obstacles["sources"] = []

        zones = self.data.setdefault("zones", {})
        if isinstance(zones, dict):
            zones.setdefault("defaults", zones.get("defaults") or {"radius": 95.0})
            zones.pop("types", None)
            zones["sources"] = []

        spawns = self.data.setdefault("spawn_emitters", {})
        if isinstance(spawns, dict):
            spawns["sources"] = []

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

    def _load_nests(self) -> None:
        profiles = (self.data.get("affiliation") or {}).get("profiles") or {}
        for affiliation_id, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            if "nest_x" not in profile or "nest_y" not in profile:
                continue
            self.objects.append(
                MapObject(
                    uid=self._new_uid("nest"),
                    layer="affiliation_site",
                    type_ref="affiliation_site",
                    x=float(profile["nest_x"]),
                    y=float(profile["nest_y"]),
                    props={"role": "root"},
                    source_id=str(affiliation_id),
                )
            )
            cid = str(affiliation_id)
            self.objects.append(
                MapObject(
                    uid=self._new_uid("acc"),
                    layer=ACCESS_LAYER,
                    type_ref="affiliation_access",
                    x=float(profile["nest_x"]),
                    y=float(profile["nest_y"]),
                    props={"parent": cid, "role": "access"},
                    source_id=f"{cid}_access_main",
                )
            )

    def _flush_nests(self, objects: List[MapObject]) -> None:
        aff_block = self.data.setdefault("affiliation", {})
        profiles = aff_block.setdefault("profiles", {})
        for obj in objects:
            profile_key = str(obj.source_id or obj.type_ref)
            profile = profiles.setdefault(profile_key, {})
            profile["nest_x"] = float(obj.x)
            profile["nest_y"] = float(obj.y)

    def affiliation_id_for_site(self, obj: MapObject) -> str:
        return str(obj.source_id or obj.type_ref)

    def affiliation_access_for(self, site: MapObject) -> List[MapObject]:
        affiliation_id = self.affiliation_id_for_site(site)
        return [
            o
            for o in self.objects
            if o.layer in ACCESS_LAYERS and str(o.props.get("parent", "")) == affiliation_id
        ]

    def move_site_with_access(self, site: MapObject, x: float, y: float) -> None:
        dx, dy = float(x) - site.x, float(y) - site.y
        for child in self.affiliation_access_for(site):
            child.x += dx
            child.y += dy
        site.x = float(x)
        site.y = float(y)

    def objects_in_layer(self, layer: str) -> List[MapObject]:
        if layer in SITE_LAYERS:
            return [o for o in self.objects if o.layer in SITE_LAYERS]
        return [o for o in self.objects if o.layer == layer]

    def _inline_obstacle_types(self) -> Dict[str, Any]:
        return dict((self.data.get("obstacles") or {}).get("types") or {})

    def _inline_zone_types(self) -> Dict[str, Any]:
        return dict((self.data.get("zones") or {}).get("types") or {})

    def _resolve_zone_merged_def(self, obj: MapObject) -> Dict[str, Any]:
        defaults = (self.data.get("zones") or {}).get("defaults") or {}
        merged = resolve_type_def(
            "zone",
            obj.type_ref,
            inline_types=self._inline_zone_types(),
        )
        result = dict(merged)
        result.update(obj.props)
        result.setdefault("radius", defaults.get("radius", 95.0))
        return result

    def _resolve_obstacle_merged_def(self, obj: MapObject) -> Dict[str, Any]:
        merged = resolve_type_def(
            "obstacle",
            obj.type_ref,
            inline_types=self._inline_obstacle_types(),
        )
        result = dict(merged)
        result.update(obj.props)
        return result

    def rect_half_extents(self, obj: MapObject) -> Optional[tuple[float, float]]:
        """矩形 shape の half_w, half_h。円形なら None。"""
        if obj.layer == "obstacle":
            tdef = self._resolve_obstacle_merged_def(obj)
        elif obj.layer == "zone":
            tdef = self._resolve_zone_merged_def(obj)
        else:
            return None
        if str(tdef.get("shape", "circle")).lower() != "rect":
            return None
        return (
            float(tdef.get("width", 160.0)) * 0.5,
            float(tdef.get("height", 80.0)) * 0.5,
        )

    def type_options(self, layer: str) -> List[str]:
        if layer == "obstacle":
            options = list_type_ids("obstacle", inline_types=self._inline_obstacle_types())
            return options or ["rock", "fallen_log"]
        if layer == "zone":
            options = list_type_ids("zone", inline_types=self._inline_zone_types())
            return options or ["poison_fog"]
        if layer == "spawn":
            types = (self.data.get("spawn_emitters") or {}).get("types") or {}
            return list(types.keys()) or ["micro_fauna_mixed"]
        if layer in SITE_LAYERS:
            profiles = (self.data.get("affiliation") or {}).get("profiles") or {}
            return list(profiles.keys()) or ["red_ant"]
        return []

    def resolve_radius(self, obj: MapObject) -> float:
        if obj.layer == "obstacle":
            tdef = resolve_type_def(
                "obstacle",
                obj.type_ref,
                inline_types=self._inline_obstacle_types(),
            )
            if str(tdef.get("shape", "circle")).lower() == "rect":
                return max(float(tdef.get("width", 40)), float(tdef.get("height", 16))) * 0.5
            return float(obj.get("radius", tdef.get("radius", 20.0)))
        if obj.layer == "zone":
            tdef = self._resolve_zone_merged_def(obj)
            if str(tdef.get("shape", "circle")).lower() == "rect":
                return max(float(tdef.get("width", 160.0)), float(tdef.get("height", 80.0))) * 0.5
            return float(tdef.get("radius", 95.0))
        if obj.layer == "spawn":
            defaults = (self.data.get("spawn_emitters") or {}).get("defaults") or {}
            types = (self.data.get("spawn_emitters") or {}).get("types") or {}
            tdef = types.get(obj.type_ref) or {}
            return float(obj.get("radius", tdef.get("radius", defaults.get("radius", 85.0))))
        if obj.layer in SITE_LAYERS:
            profile = ((self.data.get("affiliation") or {}).get("profiles") or {}).get(
                self.affiliation_id_for_site(obj)
            ) or {}
            return float(profile.get("territory_radius", 180.0))
        if obj.layer in ACCESS_LAYERS:
            return 18.0
        return 24.0

    def add_object(self, layer: str, type_ref: str, x: float, y: float) -> MapObject:
        if layer in SITE_LAYERS:
            affiliation_id = type_ref
            existing = [
                o
                for o in self.objects
                if o.layer in SITE_LAYERS and self.affiliation_id_for_site(o) == affiliation_id
            ]
            if existing:
                self.move_site_with_access(existing[0], x, y)
                return existing[0]
            obj = MapObject(
                uid=self._new_uid("site"),
                layer="affiliation_site",
                type_ref="affiliation_site",
                x=float(x),
                y=float(y),
                props={"role": "root"},
                source_id=affiliation_id,
            )
            self.objects.append(obj)
            self.objects.append(
                MapObject(
                    uid=self._new_uid("acc"),
                    layer=ACCESS_LAYER,
                    type_ref="affiliation_access",
                    x=float(x),
                    y=float(y),
                    props={"parent": affiliation_id, "role": "access"},
                    source_id=f"{affiliation_id}_access_main",
                )
            )
            return obj
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
        layers = [layer] if not all_layers else [
            "compound_root",
            "compound_access",
            "affiliation_site",
            "affiliation_access",
            "nest",
            "spawn",
            "zone",
            "obstacle",
        ]
        best: Optional[MapObject] = None
        best_dist = float("inf")
        for obj in self.objects:
            if obj.layer not in layers:
                continue
            if obj.layer in ("obstacle", "zone"):
                rect = self.rect_half_extents(obj)
                if rect is not None:
                    hw, hh = rect[0] + 4, rect[1] + 4
                    if abs(wx - obj.x) <= hw and abs(wy - obj.y) <= hh:
                        dist = (wx - obj.x) ** 2 + (wy - obj.y) ** 2
                        if dist < best_dist:
                            best_dist = dist
                            best = obj
                    continue
            radius = self.resolve_radius(obj) + 6.0
            if obj.layer in SITE_LAYERS:
                radius = min(radius, 40.0)
            dist_sq = (wx - obj.x) ** 2 + (wy - obj.y) ** 2
            if dist_sq <= radius * radius and dist_sq < best_dist:
                best_dist = dist_sq
                best = obj
        return best

    def migrate_to_instances_format(self) -> None:
        """legacy sections から instances[] へ移行（初回保存用）。"""
        if uses_instances_format(self.data):
            return
        self.data["instances"] = collapse_legacy_to_instances(self.data)
        self.objects.clear()
        self._load_from_instances()
