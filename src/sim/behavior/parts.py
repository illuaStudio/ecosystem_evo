"""イベント・死後レシピで共通利用する行動パーツ（小さな処理単位）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from src.sim.utils.movement_helpers import move_toward_point
from src.sim.utils.position_helpers import sync_legacy_pos


@dataclass(frozen=True)
class PartResult:
    """パーツ 1 tick の結果。"""

    finished: bool = False
    removed_creature: bool = False


class BehaviorPart(ABC):
    """強制命令・死後レシピから共用する処理パーツ。"""

    @abstractmethod
    def tick(self, creature, dt: float = 1.0) -> PartResult:
        pass

    @abstractmethod
    def is_finished(self) -> bool:
        pass

    def reset(self) -> None:
        pass


def warp_creature(creature, x: float, y: float) -> None:
    """座標を即座に書き換える。"""
    px = float(x)
    py = float(y)
    creature.position.x = px
    creature.position.y = py
    creature.pos[0] = px
    creature.pos[1] = py
    sync_legacy_pos(creature, update_last=True)


def spawn_creature_drop(creature, params: dict | None = None) -> None:
    from src.sim.utils.drop_helpers import apply_spawn_drop_step

    apply_spawn_drop_step(creature, params or {})


def convert_creature_corpse_mass(creature) -> None:
    size = float(creature.traits.get("base_size", 9.0))
    mass = size * 200.0
    creature.corpse.remaining_mass = mass
    creature.corpse.initial_mass = mass


def remove_creature_from_world(creature) -> bool:
    world = getattr(creature, "world", None)
    if world is not None and creature in world.creatures:
        world.remove_creature(creature)
        return True
    return False


class InstantPart(BehaviorPart):
    """1 tick で完了する同期パーツ。"""

    def __init__(self, fn, *, removes_creature: bool = False) -> None:
        self._fn = fn
        self._removes_creature = removes_creature
        self._finished = False

    def tick(self, creature, dt: float = 1.0) -> PartResult:
        if self._finished:
            return PartResult(
                finished=True,
                removed_creature=self._removes_creature and self._creature_gone(creature),
            )
        if self._removes_creature:
            remove_creature_from_world(creature)
        else:
            self._fn(creature)
        self._finished = True
        return PartResult(
            finished=True,
            removed_creature=self._removes_creature and self._creature_gone(creature),
        )

    def is_finished(self) -> bool:
        return self._finished

    @staticmethod
    def _creature_gone(creature) -> bool:
        world = getattr(creature, "world", None)
        return world is None or creature not in world.creatures


class WarpPart(BehaviorPart):
    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self._finished = False

    def tick(self, creature, dt: float = 1.0) -> PartResult:
        if not self._finished:
            warp_creature(creature, self.x, self.y)
            self._finished = True
        return PartResult(finished=True)

    def is_finished(self) -> bool:
        return self._finished


class MoveToPart(BehaviorPart):
    def __init__(
        self,
        x: float,
        y: float,
        *,
        speed_multiplier: float = 1.0,
        arrival_radius: float = 8.0,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.speed_multiplier = float(speed_multiplier)
        self.arrival_radius = float(arrival_radius)
        self._finished = False

    def tick(self, creature, dt: float = 1.0) -> PartResult:
        if self._finished:
            return PartResult(finished=True)
        dist = move_toward_point(
            creature,
            self.x,
            self.y,
            self.speed_multiplier,
            dt,
        )
        sync_legacy_pos(creature, update_last=True)
        if dist <= self.arrival_radius:
            self._finished = True
        return PartResult(finished=self._finished)

    def is_finished(self) -> bool:
        return self._finished


class DecomposeUntilEmptyPart(BehaviorPart):
    def __init__(self) -> None:
        self._finished = False

    def tick(self, creature, dt: float = 1.0) -> PartResult:
        creature.corpse.update(dt)
        self._finished = creature.corpse.is_depleted()
        return PartResult(finished=self._finished)

    def is_finished(self) -> bool:
        return self._finished


_PART_BUILDERS = {
    "warp_to": lambda p: WarpPart(p["x"], p["y"]),
    "move_to": lambda p: MoveToPart(
        p["x"],
        p["y"],
        speed_multiplier=float(p.get("speed_multiplier", 1.0)),
        arrival_radius=float(p.get("arrival_radius", 8.0)),
    ),
    "convert_corpse_mass": lambda _p: InstantPart(convert_creature_corpse_mass),
    "spawn_drop": lambda p: InstantPart(lambda c: spawn_creature_drop(c, p)),
    "remove": lambda _p: InstantPart(remove_creature_from_world, removes_creature=True),
    "decompose_until_empty": lambda _p: DecomposeUntilEmptyPart(),
}


def create_part(kind: str, **params) -> BehaviorPart:
    builder = _PART_BUILDERS.get(kind)
    if builder is None:
        raise KeyError(f"unknown behavior part: {kind!r}")
    if kind in ("warp_to", "move_to") and "x" not in params:
        raise KeyError(f"{kind} requires x and y")
    return builder(params)


def parse_step_spec(step) -> tuple[str, dict]:
    """death_policy の 1 step を (kind, params) へ。"""
    if isinstance(step, str):
        return step, {}
    if isinstance(step, dict):
        kind = step.get("step") or step.get("kind") or step.get("name")
        if not kind:
            raise KeyError(f"step dict missing name: {step!r}")
        params = {
            k: v
            for k, v in step.items()
            if k not in ("step", "kind", "name")
        }
        return str(kind), params
    raise TypeError(f"invalid step spec: {step!r}")
