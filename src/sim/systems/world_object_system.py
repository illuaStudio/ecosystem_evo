"""ワールドオブジェクトの読み込み・親子階層・備蓄。"""
from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from src.sim.components.object_storage import ObjectStorage
from src.sim.entities.world_object import WorldObject
from src.config import config
from src.sim.utils.colony_config_helpers import get_access_max_hp
from src.sim.systems.obstacle_system import _parse_color

if TYPE_CHECKING:
    from src.sim.systems.world import World

SITE_LAYERS = frozenset({"colony_site", "nest"})
ACCESS_LAYERS = frozenset({"colony_access"})
OBSTACLE_LAYERS = frozenset({"obstacle"})


class WorldObjectSystem:
    def __init__(self, world: "World") -> None:
        self.world = world
        self.objects: Dict[str, WorldObject] = {}
        self._children: Dict[str, List[str]] = {}

    def init_from_layout(self, layout: Dict[str, Any]) -> None:
        self.objects.clear()
        self._children.clear()

        instances = list(layout.get("instances") or [])
        self._load_from_instances(instances, layout)
        self._ensure_default_access_children(layout)
        self._rebuild_child_index()

    def _load_from_instances(self, instances: List[Dict], layout: Dict) -> None:
        colony_settings = (layout.get("colony") or {})
        access_max_hp = get_access_max_hp(colony_settings)

        for raw in instances:
            if not isinstance(raw, dict):
                continue
            layer = str(raw.get("layer", ""))
            obj_id = str(raw.get("id", raw.get("type", "")))
            if not obj_id:
                continue

            if layer in SITE_LAYERS:
                if obj_id in self.objects:
                    continue
                profiles = (layout.get("colony") or {}).get("profiles") or {}
                profile = dict(profiles.get(obj_id) or {})
                type_def = config.get_object_type(str(raw.get("type", "colony_site")))
                max_food = float(raw.get("max_food", profile.get("max_food", type_def.get("max_food", 400.0))))
                initial = float(
                    raw.get(
                        "initial_stored_food",
                        profile.get("initial_stored_food", type_def.get("initial_stored_food", 0.0)),
                    )
                )
                self.objects[obj_id] = WorldObject(
                    id=obj_id,
                    type_ref=str(raw.get("type", "colony_site")),
                    x=float(raw.get("x", profile.get("nest_x", 0.0))),
                    y=float(raw.get("y", profile.get("nest_y", 0.0))),
                    role=str(raw.get("role", "root")),
                    storage=ObjectStorage(
                        stored_food=max(0.0, min(initial, max_food)),
                        max_food=max_food,
                    ),
                    label=str(raw.get("label", obj_id)),
                )
                continue

            if layer in ACCESS_LAYERS:
                parent_id = str(raw.get("parent", ""))
                if not parent_id:
                    continue
                type_def = config.get_object_type(str(raw.get("type", "colony_access")))
                max_hp = float(raw.get("max_hp", type_def.get("max_hp", access_max_hp)))
                hp = float(raw.get("hp", max_hp))
                child_id = obj_id or f"{parent_id}_access_{uuid.uuid4().hex[:6]}"
                self.objects[child_id] = WorldObject(
                    id=child_id,
                    type_ref=str(raw.get("type", "colony_access")),
                    x=float(raw.get("x", 0.0)),
                    y=float(raw.get("y", 0.0)),
                    parent_id=parent_id,
                    role=str(raw.get("role", "access")),
                    shelter=bool(raw.get("shelter", type_def.get("shelter", True))),
                    deposit_access=bool(raw.get("deposit_access", type_def.get("deposit_access", True))),
                    hp=hp,
                    max_hp=max_hp,
                    label=str(raw.get("label", child_id)),
                )
                continue

            if layer in OBSTACLE_LAYERS:
                if obj_id in self.objects:
                    continue
                type_ref = str(raw.get("type", "rock"))
                type_def = config.get_object_type(type_ref)
                merged = dict(type_def)
                for key, value in raw.items():
                    if key not in ("id", "layer", "type", "x", "y"):
                        merged[key] = value
                shape = str(merged.get("shape", "circle")).lower()
                x = float(raw.get("x", merged.get("x", 0.0)))
                y = float(raw.get("y", merged.get("y", 0.0)))
                render = merged.get("render") or {}
                default_color = (92, 64, 40) if shape == "rect" else (120, 118, 110)
                color = _parse_color(render.get("color"), default_color)
                label = str(raw.get("label", type_def.get("label", type_ref)))
                if shape == "rect":
                    width = float(merged.get("width", 40.0))
                    height = float(merged.get("height", 16.0))
                    self.objects[obj_id] = WorldObject(
                        id=obj_id,
                        type_ref=type_ref,
                        x=x,
                        y=y,
                        role=str(raw.get("role", "obstacle")),
                        label=label,
                        shape="rect",
                        half_w=max(1.0, width * 0.5),
                        half_h=max(1.0, height * 0.5),
                        color=color,
                    )
                else:
                    radius = float(merged.get("radius", 20.0))
                    self.objects[obj_id] = WorldObject(
                        id=obj_id,
                        type_ref=type_ref,
                        x=x,
                        y=y,
                        role=str(raw.get("role", "obstacle")),
                        label=label,
                        shape="circle",
                        radius=max(1.0, radius),
                        color=color,
                    )

    def _ensure_default_access_children(self, layout: Dict) -> None:
        colony_settings = (layout.get("colony") or {})
        access_max_hp = get_access_max_hp(colony_settings)
        for obj_id, parent in list(self.objects.items()):
            if not parent.is_root:
                continue
            if self.get_children(obj_id):
                continue
            child_id = f"{obj_id}_access_main"
            self.objects[child_id] = WorldObject(
                id=child_id,
                type_ref="colony_access",
                x=parent.x,
                y=parent.y,
                parent_id=obj_id,
                role="access",
                shelter=True,
                deposit_access=True,
                hp=access_max_hp,
                max_hp=access_max_hp,
                label=f"{obj_id}_access",
            )

    def _rebuild_child_index(self) -> None:
        self._children.clear()
        for obj in self.objects.values():
            if obj.parent_id:
                self._children.setdefault(obj.parent_id, []).append(obj.id)

    def get(self, object_id: str) -> Optional[WorldObject]:
        return self.objects.get(object_id)

    def iter_roots(self) -> List[WorldObject]:
        return [obj for obj in self.objects.values() if obj.is_root]

    def iter_obstacles(self) -> List[WorldObject]:
        return [obj for obj in self.objects.values() if obj.is_obstacle]

    def get_children(self, parent_id: str) -> List[WorldObject]:
        return [
            self.objects[cid]
            for cid in self._children.get(parent_id, ())
            if cid in self.objects
        ]

    def iter_access_points(
        self,
        parent_id: str,
        *,
        require_deposit: bool = False,
        require_shelter: bool = False,
    ) -> List[WorldObject]:
        out: List[WorldObject] = []
        for child in self.get_children(parent_id):
            if child.is_destroyed:
                continue
            if require_deposit and not child.deposit_access:
                continue
            if require_shelter and not child.shelter:
                continue
            out.append(child)
        return out

    def add_access_point(
        self,
        parent_id: str,
        x: float,
        y: float,
        *,
        max_hp: float | None = None,
    ) -> WorldObject | None:
        parent = self.get(parent_id)
        if parent is None or not parent.is_root:
            return None
        colony_settings = getattr(self.world, "colony_settings", {}) or {}
        hp_cap = float(max_hp if max_hp is not None else get_access_max_hp(colony_settings))
        child_id = f"{parent_id}_access_{uuid.uuid4().hex[:6]}"
        child = WorldObject(
            id=child_id,
            type_ref="colony_access",
            x=float(x),
            y=float(y),
            parent_id=parent_id,
            role="access",
            shelter=True,
            deposit_access=True,
            hp=hp_cap,
            max_hp=hp_cap,
            label=child_id,
        )
        self.objects[child_id] = child
        self._children.setdefault(parent_id, []).append(child_id)
        return child

    def find_nearest_access(
        self,
        parent_ids: Sequence[str],
        x: float,
        y: float,
        *,
        require_deposit: bool = False,
        require_shelter: bool = False,
    ) -> tuple[Optional[WorldObject], Optional[WorldObject]]:
        """(親, 最寄りの子) を返す。"""
        best_parent: Optional[WorldObject] = None
        best_child: Optional[WorldObject] = None
        best_dist = float("inf")

        for pid in parent_ids:
            parent = self.get(pid)
            if parent is None or not parent.is_root:
                continue
            for child in self.iter_access_points(
                pid,
                require_deposit=require_deposit,
                require_shelter=require_shelter,
            ):
                dist = math.hypot(child.x - x, child.y - y)
                if dist < best_dist:
                    best_dist = dist
                    best_parent = parent
                    best_child = child
        return best_parent, best_child

    def deposit_to_parent(self, parent_id: str, amount: float) -> float:
        parent = self.get(parent_id)
        if parent is None or parent.storage is None:
            return 0.0
        return parent.storage.deposit(amount)

    def withdraw_from_parent(self, parent_id: str, amount: float) -> float:
        parent = self.get(parent_id)
        if parent is None or parent.storage is None:
            return 0.0
        return parent.storage.withdraw(amount)

    def stored_food(self, parent_id: str) -> float:
        parent = self.get(parent_id)
        if parent is None or parent.storage is None:
            return 0.0
        return float(parent.storage.stored_food)

    def find_access_at(
        self,
        parent_id: str,
        x: float,
        y: float,
        *,
        epsilon: float = 2.0,
    ) -> Optional[WorldObject]:
        for child in self.get_children(parent_id):
            if math.hypot(child.x - x, child.y - y) <= epsilon:
                return child
        return None

    def sync_access_hp(self, parent_id: str, access_id: str, hp: float) -> None:
        child = self.get(access_id)
        if child is None or child.parent_id != parent_id:
            return
        child.hp = max(0.0, float(hp))

    def count_active_access(self, parent_id: str) -> int:
        """破壊されていない colony_access の数。"""
        return len(self.iter_access_points(parent_id))

    def has_colony_root(self, colony_id: str) -> bool:
        root = self.get(colony_id)
        return root is not None and root.is_root

    def ensure_colony_site(
        self,
        colony_id: str,
        x: float,
        y: float,
        *,
        max_food: float = 400.0,
        stored_food: float = 0.0,
    ) -> WorldObject:
        """runtime Nest から colony_site を生成（legacy 合流用）。"""
        existing = self.get(colony_id)
        if existing is not None and existing.is_root:
            return existing
        cap = float(max_food)
        food = max(0.0, min(float(stored_food), cap))
        root = WorldObject(
            id=str(colony_id),
            type_ref="colony_site",
            x=float(x),
            y=float(y),
            role="root",
            storage=ObjectStorage(stored_food=food, max_food=cap),
            label=str(colony_id),
        )
        self.objects[colony_id] = root
        self._children.setdefault(colony_id, [])
        return root

    def clear_colony_access(self, colony_id: str) -> None:
        """勢力の接続点をすべて削除（敗北時など）。"""
        for child in list(self.get_children(colony_id)):
            self.remove_access_point(child.id)

    def remove_access_point(self, access_id: str) -> None:
        child = self.get(access_id)
        if child is None or not child.parent_id:
            return
        parent_id = child.parent_id
        self.objects.pop(access_id, None)
        children = self._children.get(parent_id, [])
        if access_id in children:
            children.remove(access_id)
