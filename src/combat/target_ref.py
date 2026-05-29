"""戦闘・狩猟の対象ハンドル（段階A: Creature と NestHole を統一参照）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.systems.nest_system import Nest, NestHole


class TargetKind(Enum):
    CREATURE = "creature"
    SPAWN_NODE = "spawn_node"


@dataclass(frozen=True, slots=True)
class TargetRef:
    kind: TargetKind
    creature: object | None = None
    nest: Nest | None = None
    hole: NestHole | None = None

    @staticmethod
    def from_creature(creature) -> TargetRef:
        return TargetRef(kind=TargetKind.CREATURE, creature=creature)

    @staticmethod
    def from_spawn_node(nest: Nest, hole: NestHole) -> TargetRef:
        return TargetRef(kind=TargetKind.SPAWN_NODE, nest=nest, hole=hole)

    def as_creature(self):
        if self.kind is TargetKind.CREATURE:
            return self.creature
        return None

    def as_spawn_pair(self) -> tuple | None:
        if self.kind is TargetKind.SPAWN_NODE and self.nest is not None and self.hole is not None:
            return (self.hole, self.nest)
        return None
