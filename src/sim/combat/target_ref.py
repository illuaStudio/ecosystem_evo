"""戦闘・狩猟の対象ハンドル（Creature / WorldObject）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.sim.entities.world_object import WorldObject


class TargetKind(Enum):
    CREATURE = "creature"
    WORLD_OBJECT = "world_object"


@dataclass(frozen=True, slots=True)
class TargetRef:
    kind: TargetKind
    creature: object | None = None
    world_object: Optional["WorldObject"] = None
    affiliation_id: str | None = None

    @staticmethod
    def from_creature(creature) -> TargetRef:
        return TargetRef(kind=TargetKind.CREATURE, creature=creature)

    @staticmethod
    def from_world_object(obj: "WorldObject", affiliation_id: str) -> TargetRef:
        return TargetRef(
            kind=TargetKind.WORLD_OBJECT,
            world_object=obj,
            affiliation_id=str(affiliation_id),
        )

    def as_creature(self):
        if self.kind is TargetKind.CREATURE:
            return self.creature
        return None

    def as_world_object(self) -> Optional["WorldObject"]:
        if self.kind is TargetKind.WORLD_OBJECT:
            return self.world_object
        return None
