"""tests/game: World 生成時にコロニー進行を紐付ける。"""
from __future__ import annotations

import pytest

from src.sim.systems.world import World


@pytest.fixture(autouse=True)
def _bind_colony_for_game_tests(monkeypatch):
    from tests.sim.colony_binding import bind_colony

    original_init = World._init_from_data

    def _init_from_data(self, world_data):
        original_init(self, world_data)
        # Use runtime attachment as the signal (no more on_creature_added hook)
        try:
            from src.game.colony_session import get_colony_orchestrator

            get_colony_orchestrator(self)
            already_bound = True
        except Exception:
            already_bound = False
        if not already_bound:
            bind_colony(self)
            # Trigger game reactions for initial spawns (event-driven path).
            from src.game.colony_session import ensure_creature_affiliations
            ensure_creature_affiliations(self)

    monkeypatch.setattr(World, "_init_from_data", _init_from_data)
    yield
