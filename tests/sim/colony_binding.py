"""sim テスト用: game 層 ColonyOrchestrator を World に紐付ける。"""
from __future__ import annotations

from src.game.colony_orchestrator import ColonyOrchestrator
from src.game.colony_session import attach_colony_orchestrator


def bind_colony(world):
    orch = ColonyOrchestrator(world)
    attach_colony_orchestrator(world, orch)
    world.on_sim_tick = orch.update  # type: ignore[attr-defined]
    return orch
