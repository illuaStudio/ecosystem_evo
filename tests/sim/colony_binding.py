"""sim テスト用: game 層 ColonyOrchestrator を World に紐付ける。

`tests/sim/` 内テストは `conftest.py` が `@pytest.mark.no_colony` 以外で自動 bind。
他パッケージは `load_test_world()` または明示的 `bind_colony(world)` を使う。
"""
from __future__ import annotations

from src.game.colony_orchestrator import ColonyOrchestrator
from src.game.colony_session import attach_colony_orchestrator


def bind_colony(world):
    orch = ColonyOrchestrator(world)
    attach_colony_orchestrator(world, orch)
    world.on_sim_tick = orch.update  # type: ignore[attr-defined]
    return orch
