"""死亡フラグ・死亡イベント（死後レシピは PostLife / death_policy）。"""
from __future__ import annotations

from typing import Any


class DeathComponent:
    def __init__(self, owner: Any) -> None:
        self.owner = owner

    def mark_dead(self, cause: str = "unknown") -> None:
        owner = self.owner
        if not owner.alive:
            return

        was_alive = owner.alive
        owner.alive = False
        owner.hp = 0

        if was_alive and owner.world is not None:
            owner.world.on_creature_became_corpse(owner)
            from src.sim.emitters import emit_death
            from src.sim.events import DeathCause

            death_cause: DeathCause = cause
            emit_death(owner.world, owner, cause=death_cause)
