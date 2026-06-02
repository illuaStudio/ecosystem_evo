"""tests/sim 専用: コロニー進行が要るテストはデフォルトで bind_colony。

純 Sim のみのテストは `@pytest.mark.no_colony` を付ける。
"""
from __future__ import annotations

import pytest

from src.sim.systems.world import World


@pytest.fixture(autouse=True)
def _bind_colony_for_sim_tests(request, monkeypatch):
    if request.node.get_closest_marker("no_colony"):
        yield
        return

    from tests.sim.colony_binding import bind_colony

    original_init = World._init_from_data

    def _init_from_data(self, world_data):
        original_init(self, world_data)
        # Use runtime attachment as the signal that colony is bound (no more on_* hooks)
        try:
            from src.game.colony_session import get_colony_orchestrator

            get_colony_orchestrator(self)
            already_bound = True
        except Exception:
            already_bound = False
        if not already_bound:
            bind_colony(self)
            # Trigger game reactions (affiliation assignment) for spawns that happened
            # during world creation, simulating event processing.
            from src.game.colony_session import ensure_creature_affiliations
            ensure_creature_affiliations(self)

    monkeypatch.setattr(World, "_init_from_data", _init_from_data)
    yield
