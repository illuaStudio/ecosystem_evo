"""ゲーム層イベントの発火。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.game.colony_session import get_colony_runtime
from src.game.events import AffiliationDefeatedEvent

if TYPE_CHECKING:
    from src.sim.systems.world import World


def _sim_time(world: "World") -> float:
    return float(getattr(world, "_sim_time", 0.0))


def emit_affiliation_defeated(world: "World", affiliation_id: str, message: str) -> None:
    if world is None or not affiliation_id:
        return
    runtime = get_colony_runtime(world)
    if runtime is None:
        return
    runtime.pending_events.append(
        AffiliationDefeatedEvent(
            sim_time=_sim_time(world),
            affiliation_id=str(affiliation_id),
            message=str(message),
        )
    )
