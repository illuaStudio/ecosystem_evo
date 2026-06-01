"""ワールドオブジェクトの読み込み・親子階層・備蓄。"""
from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence

from src.sim.components.object_storage import ObjectStorage
from src.sim.entities.world_object import WorldObject
from src.config import config
from src.sim.utils.affiliation_config_helpers import get_access_max_hp
from src.sim.utils.compound_layers import (
    ACCESS_LAYERS,
    ROOT_LAYERS,
    default_access_type_for_root,
    profile_for_type,
)
from src.sim.utils.object_capabilities import (
    capability_block,
    merge_type_with_instance,
    resolve_geometry,
    resolve_render_color,
    zone_effects_from_data,
)

if TYPE_CHECKING:
    from src.sim.systems.world import World

SITE_LAYERS = ROOT_LAYERS
OBSTACLE_LAYERS = frozenset({"obstacle"})
ZONE_LAYERS = frozenset({"zone"})
RESERVED_INSTANCE_KEYS = frozenset({"id", "layer", "type", "x", "y", "parent", "role"})


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
        affiliation_settings = dict(layout.get("affiliation") or {})
        access_max_hp = get_access_max_hp(affiliation_settings)
        zone_defaults = dict((layout.get("zones") or {}).get("defaults") or {})

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
                aff_profiles = (layout.get("affiliation") or {}).get("profiles") or {}
                profile = dict(aff_profiles.get(obj_id) or {})
                type_ref = str(raw.get("type", "affiliation_site"))
                type_def = config.get_object_type(type_ref)
                merged = merge_type_with_instance(
                    type_def,
                    raw,
                    reserved_keys=RESERVED_INSTANCE_KEYS,
                )
                storage = capability_block(merged, "storage")
                compound = capability_block(merged, "compound")
                max_food = float(
                    raw.get(
                        "max_food",
                        profile.get("max_food", storage.get("max_food", 400.0)),
                    )
                )
                initial = float(
                    raw.get(
                        "initial_stored_food",
                        profile.get(
                            "initial_stored_food",
                            storage.get("initial_stored_food", 0.0),
                        ),
                    )
                )
                storage = ObjectStorage.from_config(
                    {
                        **storage,
                        "max_food": max_food,
                        "initial_stored_food": initial,
                    }
                )
                self.objects[obj_id] = WorldObject(
                    id=obj_id,
                    type_ref=type_ref,
                    x=float(raw.get("x", profile.get("nest_x", 0.0))),
                    y=float(raw.get("y", profile.get("nest_y", 0.0))),
                    role=str(raw.get("role", compound.get("role", "root"))),
                    storage=storage,
                    label=str(raw.get("label", type_def.get("label", obj_id))),
                    compound_profile=str(
                        raw.get(
                            "compound_profile",
                            compound.get("profile", profile_for_type(type_ref)),
                        )
                    ),
                )
                continue

            if layer in ACCESS_LAYERS:
                parent_id = str(raw.get("parent", ""))
                if not parent_id:
                    continue
                type_ref = str(raw.get("type", "affiliation_access"))
                type_def = config.get_object_type(type_ref)
                merged = merge_type_with_instance(
                    type_def,
                    raw,
                    reserved_keys=RESERVED_INSTANCE_KEYS,
                )
                access = capability_block(merged, "access")
                combat = capability_block(merged, "combat")
                max_hp = float(
                    raw.get("max_hp", combat.get("max_hp", access_max_hp))
                )
                hp = float(raw.get("hp", max_hp))
                child_id = obj_id or f"{parent_id}_access_{uuid.uuid4().hex[:6]}"
                self.objects[child_id] = WorldObject(
                    id=child_id,
                    type_ref=type_ref,
                    x=float(raw.get("x", 0.0)),
                    y=float(raw.get("y", 0.0)),
                    parent_id=parent_id,
                    role=str(raw.get("role", access.get("role", "access"))),
                    shelter=bool(raw.get("shelter", access.get("shelter", True))),
                    deposit_access=bool(
                        raw.get(
                            "deposit_access",
                            access.get(
                                "deposit_access",
                                access.get("deposit", True),
                            ),
                        )
                    ),
                    withdraw_access=bool(
                        raw.get(
                            "withdraw_access",
                            access.get(
                                "withdraw_access",
                                access.get("withdraw", False),
                            ),
                        )
                    ),
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
                merged = merge_type_with_instance(
                    type_def,
                    raw,
                    reserved_keys=RESERVED_INSTANCE_KEYS,
                )
                shape, radius, half_w, half_h = resolve_geometry(
                    merged,
                    capability="collision",
                )
                x = float(raw.get("x", merged.get("x", 0.0)))
                y = float(raw.get("y", merged.get("y", 0.0)))
                default_color = (92, 64, 40) if shape == "rect" else (120, 118, 110)
                color = resolve_render_color(merged, default_color)
                label = str(raw.get("label", type_def.get("label", type_ref)))
                if shape == "rect":
                    self.objects[obj_id] = WorldObject(
                        id=obj_id,
                        type_ref=type_ref,
                        x=x,
                        y=y,
                        role=str(raw.get("role", "obstacle")),
                        label=label,
                        shape="rect",
                        half_w=half_w,
                        half_h=half_h,
                        color=color,
                    )
                else:
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
                continue

            if layer in ZONE_LAYERS:
                if obj_id in self.objects:
                    continue
                type_ref = str(raw.get("type", "custom"))
                type_def = config.get_object_type(type_ref)
                merged = merge_type_with_instance(
                    type_def,
                    raw,
                    reserved_keys=RESERVED_INSTANCE_KEYS,
                )
                shape, radius, half_w, half_h = resolve_geometry(
                    merged,
                    capability="zone",
                    global_defaults=zone_defaults,
                )
                effects = zone_effects_from_data(merged)
                x = float(raw.get("x", merged.get("x", 0.0)))
                y = float(raw.get("y", merged.get("y", 0.0)))
                label = str(raw.get("label", type_def.get("label", type_ref)))
                self.objects[obj_id] = WorldObject(
                    id=obj_id,
                    type_ref=type_ref,
                    x=x,
                    y=y,
                    role=str(raw.get("role", "zone")),
                    label=label,
                    shape=shape,
                    radius=radius,
                    half_w=half_w,
                    half_h=half_h,
                    zone_effects=effects,
                )

    def _ensure_default_access_children(self, layout: Dict) -> None:
        affiliation_settings = dict(layout.get("affiliation") or {})
        access_max_hp = get_access_max_hp(affiliation_settings)
        for obj_id, parent in list(self.objects.items()):
            if not parent.is_root:
                continue
            if not parent.is_affiliation_compound:
                continue
            if self.get_children(obj_id):
                continue
            access_type = default_access_type_for_root(parent.type_ref)
            type_def = config.get_object_type(access_type)
            access = capability_block(type_def, "access")
            combat = capability_block(type_def, "combat")
            max_hp = float(access_max_hp)
            if not parent.is_affiliation_compound and combat.get("max_hp") is not None:
                max_hp = float(combat["max_hp"])
            child_id = f"{obj_id}_access_main"
            self.objects[child_id] = WorldObject(
                id=child_id,
                type_ref=access_type,
                x=parent.x,
                y=parent.y,
                parent_id=obj_id,
                role=str(access.get("role", "access")),
                shelter=bool(access.get("shelter", True)),
                deposit_access=bool(
                    access.get("deposit_access", access.get("deposit", True))
                ),
                withdraw_access=bool(
                    access.get("withdraw_access", access.get("withdraw", False))
                ),
                hp=max_hp,
                max_hp=max_hp,
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

    def iter_zones(self) -> List[WorldObject]:
        return [obj for obj in self.objects.values() if obj.is_zone]

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
        require_withdraw: bool = False,
        require_shelter: bool = False,
    ) -> List[WorldObject]:
        out: List[WorldObject] = []
        for child in self.get_children(parent_id):
            if child.is_destroyed:
                continue
            if require_deposit and not child.deposit_access:
                continue
            if require_withdraw and not child.withdraw_access:
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
        affiliation_settings = getattr(self.world, "affiliation_settings", {}) or {}
        hp_cap = float(max_hp if max_hp is not None else get_access_max_hp(affiliation_settings))
        access_type = default_access_type_for_root(parent.type_ref)
        type_def = config.get_object_type(access_type)
        access = capability_block(type_def, "access")
        if not parent.is_affiliation_compound:
            combat = capability_block(type_def, "combat")
            type_hp = combat.get("max_hp")
            if type_hp is not None and max_hp is None:
                hp_cap = float(type_hp)
        child_id = f"{parent_id}_access_{uuid.uuid4().hex[:6]}"
        child = WorldObject(
            id=child_id,
            type_ref=access_type,
            x=float(x),
            y=float(y),
            parent_id=parent_id,
            role=str(access.get("role", "access")),
            shelter=bool(access.get("shelter", True)),
            deposit_access=bool(
                access.get("deposit_access", access.get("deposit", True))
            ),
            withdraw_access=bool(
                access.get("withdraw_access", access.get("withdraw", False))
            ),
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
        require_withdraw: bool = False,
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
                require_withdraw=require_withdraw,
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
        """破壊されていない access の数。"""
        return len(self.iter_access_points(parent_id))

    def has_affiliation_root(self, affiliation_id: str) -> bool:
        root = self.get(affiliation_id)
        return root is not None and root.is_root

    def ensure_affiliation_site(
        self,
        affiliation_id: str,
        x: float,
        y: float,
        *,
        max_food: float = 400.0,
        stored_food: float = 0.0,
    ) -> WorldObject:
        """runtime Nest から affiliation_site を生成。"""
        existing = self.get(affiliation_id)
        if existing is not None and existing.is_root:
            return existing
        cap = float(max_food)
        food = max(0.0, min(float(stored_food), cap))
        root = WorldObject(
            id=str(affiliation_id),
            type_ref="affiliation_site",
            x=float(x),
            y=float(y),
            role="root",
            storage=ObjectStorage.from_config(
                {"max_food": cap, "initial_stored_food": food}
            ),
            label=str(affiliation_id),
            compound_profile="affiliation",
        )
        self.objects[affiliation_id] = root
        self._children.setdefault(affiliation_id, [])
        return root

    def clear_affiliation_access(self, affiliation_id: str) -> None:
        """勢力の接続点をすべて削除（敗北時など）。"""
        for child in list(self.get_children(affiliation_id)):
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
