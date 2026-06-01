"""死亡後レシピ — 共通 behavior parts を順に実行。"""
from __future__ import annotations

from typing import List, Sequence, Tuple

from src.sim.behavior.parts import BehaviorPart, create_part, parse_step_spec

StepSpec = Tuple[str, dict]

_TICK_PARTS = frozenset({"move_to"})


class PostLifeRunner:
    """death_policy の step 列を順に実行する。"""

    def __init__(self) -> None:
        self._steps: Tuple[StepSpec, ...] = ()
        self._step_index = 0
        self._started = False
        self._current_part: BehaviorPart | None = None

    def reset(self, steps: Sequence) -> None:
        parsed: List[StepSpec] = []
        for step in steps:
            if isinstance(step, tuple) and len(step) == 2 and isinstance(step[0], str):
                parsed.append((step[0], dict(step[1])))
            else:
                parsed.append(parse_step_spec(step))
        self._steps = tuple(parsed)
        self._step_index = 0
        self._started = False
        self._current_part = None

    def start(self, creature) -> bool:
        if self._started:
            return False
        self._started = True
        return self._run_until_pause(creature, dt=0.0)

    def tick(self, creature, dt: float = 1.0) -> None:
        if not self._started:
            if self.start(creature):
                return
        self._run_until_pause(creature, dt)

    def _run_until_pause(self, creature, dt: float) -> bool:
        while self._step_index < len(self._steps) or self._current_part is not None:
            if self._current_part is None:
                if self._step_index >= len(self._steps):
                    break
                kind, params = self._steps[self._step_index]
                self._current_part = create_part(kind, **params)

            result = self._current_part.tick(creature, dt)
            if result.removed_creature:
                self._current_part = None
                return True

            if not result.finished:
                return False

            self._step_index += 1
            self._current_part = None

            if self._step_index < len(self._steps):
                next_kind, _ = self._steps[self._step_index]
                if next_kind in _TICK_PARTS:
                    return False
                dt = 0.0
                continue
            break
        return False
