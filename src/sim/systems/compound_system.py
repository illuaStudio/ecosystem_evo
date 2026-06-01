"""compound 親子（storage root + access 点）の汎用ランタイム。"""
from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Callable, List, Optional, Sequence

from src.config import config
from src.sim.components.object_storage import ObjectStorage
from src.sim.entities.world_object import WorldObject
from src.sim.utils.affiliation_config_helpers import get_access_max_hp
from src.sim.utils.compound_layers import default_access_type_for_root, profile_for_type
from src.sim.utils.object_capabilities import capability_block

if TYPE_CHECKING:
    from src.sim.systems.world import World

HOLE_DESTROY_HP = 1.0
DEFAULT_ACCESS_TYPE = "affiliation_access"
DEFAULT_ACCESS_TYPE = "affiliation_access"


class CompoundSystem:
    """storage 親 + 複数 access 子の汎用 API。WorldObjectSystem 上の compound を操作する。"""

    def __init__(self, world: "World") -> None:
        self.world = world

    @property
    def _ws(self):
        return self.world.world_object_system

    def get_root(self, compound_id: str) -> Optional[WorldObject]:
        root = self._ws.get(str(compound_id))
        if root is not None and root.is_root:
            return root
        return None

    def has_root(self, compound_id: str) -> bool:
        return self.get_root(compound_id) is not None

    def iter_roots(self) -> List[WorldObject]:
        return self._ws.iter_roots()

    def iter_access_points(
        self,
        parent_id: str,
        *,
        require_deposit: bool = False,
        require_withdraw: bool = False,
        require_shelter: bool = False,
    ) -> List[WorldObject]:
        out: List[WorldObject] = []
        for child in self._ws.iter_access_points(
            parent_id,
            require_deposit=require_deposit,
            require_withdraw=require_withdraw,
            require_shelter=require_shelter,
        ):
            out.append(child)
        return out

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
        best_parent: Optional[WorldObject] = None
        best_child: Optional[WorldObject] = None
        best_dist = float("inf")

        for pid in parent_ids:
            parent = self.get_root(pid)
            if parent is None:
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

    def ensure_root(
        self,
        compound_id: str,
        x: float,
        y: float,
        *,
        type_ref: str = "affiliation_site",
        max_mass: float = 400.0,
        stored_mass: float = 0.0,
        compound_profile: str = "",
    ) -> WorldObject:
        existing = self.get_root(compound_id)
        if existing is not None:
            return existing
        cap = float(max_mass)
        food = max(0.0, min(float(stored_mass), cap))
        root = WorldObject(
            id=str(compound_id),
            type_ref=type_ref,
            x=float(x),
            y=float(y),
            role="root",
            storage=ObjectStorage.from_config(
                {
                    "max_mass": cap,
                    "initial_mass": food,
                }
            ),
            label=str(compound_id),
            compound_profile=compound_profile or profile_for_type(type_ref),
        )
        self._ws.objects[compound_id] = root
        self._ws._children.setdefault(compound_id, [])
        return root

    def add_access_point(
        self,
        parent_id: str,
        x: float,
        y: float,
        *,
        type_ref: str | None = None,
        max_hp: float | None = None,
        shelter: bool | None = None,
        deposit_access: bool | None = None,
        withdraw_access: bool | None = None,
    ) -> WorldObject | None:
        parent = self.get_root(parent_id)
        if parent is None:
            return None

        access_type = type_ref or default_access_type_for_root(parent.type_ref)
        type_def = config.get_object_type(access_type)
        access = capability_block(type_def, "access")
        combat = capability_block(type_def, "combat")

        if max_hp is not None:
            hp_cap = float(max_hp)
        elif parent.is_affiliation_compound:
            settings = getattr(self.world, "affiliation_settings", None) or getattr(self.world, "affiliation_settings", {}) or {}
            hp_cap = float(get_access_max_hp(settings))
        else:
            hp_cap = float(combat.get("max_hp", 0.0))
        child_id = f"{parent_id}_access_{uuid.uuid4().hex[:6]}"
        child = WorldObject(
            id=child_id,
            type_ref=access_type,
            x=float(x),
            y=float(y),
            parent_id=parent_id,
            role=str(access.get("role", "access")),
            shelter=bool(shelter if shelter is not None else access.get("shelter", False)),
            deposit_access=bool(
                deposit_access
                if deposit_access is not None
                else access.get("deposit_access", access.get("deposit", False))
            ),
            withdraw_access=bool(
                withdraw_access
                if withdraw_access is not None
                else access.get("withdraw_access", access.get("withdraw", False))
            ),
            hp=hp_cap,
            max_hp=hp_cap,
            label=child_id,
        )
        self._ws.objects[child_id] = child
        self._ws._children.setdefault(parent_id, []).append(child_id)
        return child

    def remove_access_point(self, access_id: str) -> None:
        self._ws.remove_access_point(access_id)

    def clear_access_points(self, parent_id: str) -> None:
        self._ws.clear_affiliation_access(parent_id)

    def count_active_access(self, parent_id: str) -> int:
        return self._ws.count_active_access(parent_id)

    def access_exhausted(self, parent_id: str) -> bool:
        if not self.has_root(parent_id):
            return True
        return self.count_active_access(parent_id) == 0

    def deposit_to_parent(self, parent_id: str, amount: float) -> float:
        return self._ws.deposit_to_parent(parent_id, amount)

    def withdraw_from_parent(self, parent_id: str, amount: float) -> float:
        return self._ws.withdraw_from_parent(parent_id, amount)

    def stored_mass(self, parent_id: str) -> float:
        return self._ws.stored_mass(parent_id)

    def sync_access_hp(self, parent_id: str, access_id: str, hp: float) -> None:
        self._ws.sync_access_hp(parent_id, access_id, hp)

    def find_access_at(
        self,
        parent_id: str,
        x: float,
        y: float,
        *,
        epsilon: float = 2.0,
    ) -> Optional[WorldObject]:
        return self._ws.find_access_at(parent_id, x, y, epsilon=epsilon)

    def damage_access(
        self,
        access: WorldObject,
        parent_id: str,
        amount: float,
        *,
        on_access_removed: Callable[[str, WorldObject], None] | None = None,
        on_all_access_removed: Callable[[str], None] | None = None,
    ) -> float:
        """access 点へダメージ。破壊時にコールバック（コロニー敗北等）。"""
        if access is None or amount <= 0 or not parent_id:
            return 0.0
        if str(access.parent_id or "") != str(parent_id):
            return 0.0
        if float(getattr(access, "max_hp", 0)) <= 0 or float(access.hp) <= 0:
            return 0.0

        dealt = min(float(access.hp), float(amount))
        access.hp = max(0.0, access.hp - dealt)

        if access.hp <= HOLE_DESTROY_HP:
            access.hp = 0.0
            if on_access_removed is not None:
                on_access_removed(str(parent_id), access)
            self.remove_access_point(access.id)
            if self.access_exhausted(parent_id) and on_all_access_removed is not None:
                on_all_access_removed(str(parent_id))
        return dealt

    def iter_access_xy(self, parent_id: str) -> list[tuple[float, float]]:
        if not self.has_root(parent_id):
            return []
        return [(float(c.x), float(c.y)) for c in self.iter_access_points(parent_id)]

    def can_place_access(
        self,
        parent_id: str,
        x: float,
        y: float,
        *,
        min_spacing: float,
        max_access: int | None = None,
    ) -> tuple[bool, str]:
        if not self.has_root(parent_id):
            return False, "親 compound が存在しません"
        if max_access is not None and self.count_active_access(parent_id) >= max_access:
            return False, f"接続点上限 ({max_access} 個)"
        for ax, ay in self.iter_access_xy(parent_id):
            if math.hypot(ax - x, ay - y) < min_spacing:
                return False, f"既存の接続点に近すぎます (要 {min_spacing:.0f}px 以上)"
        return True, ""


def _clamp_to_world(world, x: float, y: float, margin: float = 30.0) -> tuple[float, float]:
    x = max(margin, min(world.width - margin, float(x)))
    y = max(margin, min(world.height - margin, float(y)))
    return x, y
