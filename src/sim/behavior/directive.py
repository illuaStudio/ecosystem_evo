"""ゲーム・イベント由来の強制行動（Mind より優先）。"""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.sim.behavior.parts import BehaviorPart, create_part


class CreatureDirective(ABC):
    @abstractmethod
    def tick(self, creature, dt: float = 1.0) -> None:
        pass

    @abstractmethod
    def is_done(self) -> bool:
        pass


class PartDirective(CreatureDirective):
    """共通 behavior part を 1 件だけ実行する強制命令。"""

    def __init__(self, part: BehaviorPart) -> None:
        self._part = part

    def tick(self, creature, dt: float = 1.0) -> None:
        self._part.tick(creature, dt)

    def is_done(self) -> bool:
        return self._part.is_finished()


class MoveToDirective(PartDirective):
    """後方互換: move_to part のラッパ。"""

    def __init__(
        self,
        x: float,
        y: float,
        *,
        speed_multiplier: float = 1.0,
        arrival_radius: float = 8.0,
    ) -> None:
        super().__init__(
            create_part(
                "move_to",
                x=x,
                y=y,
                speed_multiplier=speed_multiplier,
                arrival_radius=arrival_radius,
            )
        )


class WarpDirective(PartDirective):
    def __init__(self, x: float, y: float) -> None:
        super().__init__(create_part("warp_to", x=x, y=y))


def create_directive(kind: str, **params) -> CreatureDirective:
    return PartDirective(create_part(kind, **params))
