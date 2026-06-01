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
        if getattr(self, "on_creature_added", None) is None:
            bind_colony(self)

    monkeypatch.setattr(World, "_init_from_data", _init_from_data)
    yield
