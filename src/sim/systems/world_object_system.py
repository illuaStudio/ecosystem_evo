"""ワールドオブジェクトの読み込み・親子階層・備蓄。"""
from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Sequence

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
from src.sim.components.spawn_capability import SpawnCapability
from src.sim.layout.import_layout import expand_layout_instances
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
FIELD_LAYERS = frozenset({"field"})
SPAWN_LAYERS = frozenset({"spawn"})
RESERVED_INSTANCE_KEYS = frozenset(
    {
        "id",
        "layer",
        "type",
        "x",
        "y",
        "parent",
        "role",
        "editor_group",
        "affiliation_id",
        "origin",
        "pickup_species_filter",
    }
)


class WorldObjectSystem:
    def __init__(self, world: "World") -> None:
        self.world = world
        self.objects: Dict[str, WorldObject] = {}
        self._children: Dict[str, List[str]] = {}

    def init_from_layout(self, layout: Dict[str, Any]) -> None:
        self.objects.clear()
        self._children.clear()

        if "instances" in layout:
            instances = list(layout.get("instances") or [])
        else:
            instances = expand_layout_instances(layout)
        self._load_from_instances(instances, layout)
        self._ensure_default_access_children(layout)
        self._rebuild_child_index()

    def _load_from_instances(self, instances: List[Dict], layout: Dict) -> None:
        affiliation_settings = dict(layout.get("affiliation") or {})
        access_max_hp = get_access_max_hp(affiliation_settings)
        zone_defaults = dict((layout.get("zones") or {}).get("defaults") or {})
        spawn_defaults = dict((layout.get("spawn_emitters") or {}).get("defaults") or {})
        spawn_type_defaults = {
            str(key): dict(value)
            for key, value in ((layout.get("spawn_emitters") or {}).get("types") or {}).items()
            if isinstance(value, dict)
        }

        for raw in instances:
            if not isinstance(raw, dict):
                continue
            layer = str(raw.get("layer", ""))
            raw_id = raw.get("id")
            if raw_id is not None and str(raw_id).strip():
                obj_id = str(raw_id)
            else:
                obj_id = f"{layer}_{uuid.uuid4().hex[:8]}"

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
                max_mass = float(
                    raw.get(
                        "max_mass",
                        profile.get("max_mass", storage.get("max_mass", 400.0)),
                    )
                )
                initial = float(
                    raw.get(
                        "initial_mass",
                        profile.get(
                            "initial_mass",
                            storage.get("initial_mass", 0.0),
                        ),
                    )
                )
                storage = ObjectStorage.from_config(
                    {
                        **storage,
                        "max_mass": max_mass,
                        "initial_mass": initial,
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
                    zone_affiliation_id=str(
                        raw.get("zone_affiliation_id", raw.get("affiliation_id", ""))
                    ),
                )
                continue

            if layer in FIELD_LAYERS:
                if obj_id in self.objects:
                    continue
                type_ref = str(raw.get("type", "field_bulk"))
                type_def = config.get_object_type(type_ref)
                merged = merge_type_with_instance(
                    type_def,
                    raw,
                    reserved_keys=RESERVED_INSTANCE_KEYS,
                )
                obj = self._build_field_object(
                    obj_id,
                    type_ref,
                    merged,
                    raw,
                    origin=str(raw.get("origin", "map")),
                )
                fill = raw.get("fill")
                if fill:
                    self._apply_fill(obj, fill, creature=None)
                self.objects[obj_id] = obj
                continue

            if layer in SPAWN_LAYERS:
                if obj_id in self.objects:
                    continue
                type_ref = str(raw.get("type", "spawn"))
                type_def = config.get_object_type(type_ref) if type_ref != "spawn" else {}
                merged = merge_type_with_instance(
                    type_def,
                    raw,
                    reserved_keys=RESERVED_INSTANCE_KEYS,
                )
                spawn_block = capability_block(merged, "spawn")
                spawn_data = {**spawn_defaults, **spawn_block, **raw}
                spawn_data["type"] = type_ref
                spawn_cap = SpawnCapability.from_mapping(
                    spawn_data,
                    global_defaults=spawn_defaults,
                    type_defaults=spawn_type_defaults,
                )
                self.objects[obj_id] = WorldObject(
                    id=obj_id,
                    type_ref=type_ref,
                    x=float(raw.get("x", 0.0)),
                    y=float(raw.get("y", 0.0)),
                    label=str(raw.get("label", spawn_cap.label or type_ref)),
                    layer="spawn",
                    origin=str(raw.get("origin", "map")),
                    spawn=spawn_cap,
                )
                continue

        self._ensure_affiliation_clearing_objects(layout)

    def _ensure_affiliation_clearing_objects(self, layout: Dict) -> None:
        profiles = (layout.get("affiliation") or {}).get("profiles") or {}
        for affiliation_id, profile in profiles.items():
            if not isinstance(profile, dict):
                continue
            radius = float(profile.get("spawn_exclusion_radius", 0.0))
            if radius <= 0:
                continue
            nest_x = profile.get("nest_x")
            nest_y = profile.get("nest_y")
            if nest_x is None or nest_y is None:
                root = self.objects.get(str(affiliation_id))
                if root is None:
                    continue
                nest_x, nest_y = root.x, root.y
            self.ensure_affiliation_clearing(
                str(affiliation_id),
                float(nest_x),
                float(nest_y),
                radius=radius,
            )

    def ensure_affiliation_clearing(
        self,
        affiliation_id: str,
        x: float,
        y: float,
        *,
        radius: float,
    ) -> WorldObject:
        clearing_id = f"{affiliation_id}_clearing"
        existing = self.objects.get(clearing_id)
        if existing is not None:
            existing.x = float(x)
            existing.y = float(y)
            existing.radius = max(0.0, float(radius))
            existing.zone_affiliation_id = str(affiliation_id)
            return existing

        type_def = config.get_object_type("nest_clearing")
        effects = zone_effects_from_data(
            {
                **type_def,
                "spawn_rate_multiplier": 0.0,
                "radius": max(0.0, float(radius)),
            }
        )
        shape, rad, half_w, half_h = resolve_geometry(
            {"shape": "circle", "radius": radius},
            capability="zone",
        )
        obj = WorldObject(
            id=clearing_id,
            type_ref="nest_clearing",
            x=float(x),
            y=float(y),
            role="zone",
            label=f"{affiliation_id}_clearing",
            shape=shape,
            radius=rad,
            half_w=half_w,
            half_h=half_h,
            zone_effects=effects,
            zone_affiliation_id=str(affiliation_id),
            origin="runtime",
        )
        self.objects[clearing_id] = obj
        return obj

    def sync_affiliation_clearing(
        self, affiliation_id: str, x: float, y: float, *, radius: float | None = None
    ) -> None:
        from src.sim.utils.affiliation_config_helpers import get_affiliation_profile

        profile = get_affiliation_profile(self.world, affiliation_id)
        rad = float(
            radius
            if radius is not None
            else profile.get("spawn_exclusion_radius", 150.0)
        )
        self.ensure_affiliation_clearing(affiliation_id, x, y, radius=rad)

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
        return [
            obj
            for obj in self.objects.values()
            if obj.is_obstacle and not obj.is_zone
        ]

    def iter_zones(self) -> List[WorldObject]:
        return [obj for obj in self.objects.values() if obj.is_zone]

    def iter_spawn_emitters(self) -> List[WorldObject]:
        return [obj for obj in self.objects.values() if obj.is_spawn_emitter]

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

    def stored_mass(self, parent_id: str) -> float:
        parent = self.get(parent_id)
        if parent is None or parent.storage is None:
            return 0.0
        return float(parent.storage.stored_mass)

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
        max_mass: float = 400.0,
        stored_mass: float = 0.0,
    ) -> WorldObject:
        """runtime Nest から affiliation_site を生成。"""
        existing = self.get(affiliation_id)
        if existing is not None and existing.is_root:
            return existing
        cap = float(max_mass)
        food = max(0.0, min(float(stored_mass), cap))
        root = WorldObject(
            id=str(affiliation_id),
            type_ref="affiliation_site",
            x=float(x),
            y=float(y),
            role="root",
            storage=ObjectStorage.from_config(
                {"max_mass": cap, "initial_mass": food}
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

    def _container_config_from_merged(self, merged: Dict[str, Any]) -> Dict[str, Any]:
        container = capability_block(merged, "container")
        if container:
            return dict(container)
        return dict(capability_block(merged, "storage"))

    def _build_field_object(
        self,
        obj_id: str,
        type_ref: str,
        merged: Dict[str, Any],
        raw: Dict[str, Any],
        *,
        origin: str = "map",
    ) -> WorldObject:
        type_def = config.get_object_type(type_ref)
        container_cfg = self._container_config_from_merged(merged)
        pickup = capability_block(merged, "pickup")
        storage = ObjectStorage.from_config(container_cfg)
        color = resolve_render_color(merged, (140, 120, 90))
        render = capability_block(merged, "render")
        modes = pickup.get("modes", ["consume", "haul"])
        if isinstance(modes, str):
            modes = [modes]
        return WorldObject(
            id=obj_id,
            type_ref=type_ref,
            x=float(raw.get("x", merged.get("x", 0.0))),
            y=float(raw.get("y", merged.get("y", 0.0))),
            storage=storage,
            label=str(raw.get("label", type_def.get("label", type_ref))),
            color=color,
            layer="field",
            origin=str(origin),
            lifecycle=str(pickup.get("lifecycle", "ephemeral")),
            pickup_radius=float(pickup.get("radius", 12.0)),
            pickup_modes=tuple(str(m) for m in modes),
            deplete_when_empty=bool(pickup.get("deplete_when_empty", True)),
            pickup_species_filter=str(raw.get("pickup_species_filter", "")),
            size_from_fill_ratio=bool(render.get("size_from_fill_ratio", False)),
        )

    def _apply_fill(
        self,
        obj: WorldObject,
        fill: Dict[str, Any],
        *,
        creature=None,
    ) -> None:
        if obj.storage is None:
            return
        mode = str(fill.get("mode", "creature_metric"))
        if mode == "creature_metric" and creature is not None:
            trait_key = str(fill.get("from_trait", "base_size"))
            scale = float(fill.get("scale", 55.0))
            size = float(creature.traits.get(trait_key, 9.0))
            amount = max(0.0, size * scale)
            obj.storage.stack.set_amount_for_kind("biomass", amount)
            obj.initial_fill = amount
            return
        if mode == "fixed_amount":
            kind = str(fill.get("kind", "biomass"))
            amount = max(0.0, float(fill.get("amount", 0.0)))
            obj.storage.stack.set_amount_for_kind(kind, amount)
            obj.initial_fill = amount
            return
        if mode == "stack_item":
            item_type = str(fill.get("item_type", fill.get("type", "generic")))
            quantity = max(1, int(fill.get("quantity", 1)))
            mass_per_unit = float(fill.get("mass_per_unit", 1.0))
            obj.storage.stack.set_stack_item(
                item_type,
                quantity,
                mass_per_unit=mass_per_unit,
            )
            obj.initial_fill = float(quantity * mass_per_unit)
            return

    def spawn_instance(
        self,
        *,
        type_ref: str,
        x: float,
        y: float,
        fill: Dict[str, Any] | None = None,
        overrides: Dict[str, Any] | None = None,
        origin: str = "spawn",
        creature=None,
    ) -> WorldObject:
        type_def = config.get_object_type(type_ref)
        instance = {"layer": "field", "type": type_ref, "x": x, "y": y}
        if overrides:
            instance.update(overrides)
        merged = merge_type_with_instance(
            type_def,
            instance,
            reserved_keys=RESERVED_INSTANCE_KEYS,
        )
        obj_id = f"field_{uuid.uuid4().hex[:10]}"
        raw = {
            "x": float(x),
            "y": float(y),
            **(overrides or {}),
        }
        obj = self._build_field_object(
            obj_id,
            type_ref,
            merged,
            raw,
            origin=origin,
        )
        self._apply_fill(obj, dict(fill or {"mode": "creature_metric"}), creature=creature)
        self.objects[obj_id] = obj
        return obj

    def remove_instance(self, object_id: str) -> None:
        self.objects.pop(str(object_id), None)

    def iter_field_pickups(self) -> List[WorldObject]:
        return [obj for obj in self.objects.values() if obj.is_field_pickup]

    def iter_field_pickup_in_radius(
        self,
        x: float,
        y: float,
        radius: float,
        *,
        species_names: Iterable[str] | None = None,
    ) -> List[WorldObject]:
        names = set(species_names) if species_names is not None else None
        r = float(radius)
        out: List[WorldObject] = []
        for obj in self.iter_field_pickups():
            if obj.is_pickup_depleted():
                continue
            if names is not None and obj.pickup_species_filter not in names:
                continue
            if math.hypot(obj.x - x, obj.y - y) <= r:
                out.append(obj)
        return out

    def update_field_objects(self, dt: float = 1.0) -> None:
        dt = float(dt)
        to_remove: List[str] = []
        for obj in list(self.iter_field_pickups()):
            if obj.is_pickup_depleted():
                if obj.deplete_when_empty and obj.lifecycle == "ephemeral":
                    to_remove.append(obj.id)
                continue
            if obj.is_pickup_depleted() and obj.deplete_when_empty:
                if obj.lifecycle == "ephemeral":
                    to_remove.append(obj.id)
        for oid in to_remove:
            self.remove_instance(oid)
