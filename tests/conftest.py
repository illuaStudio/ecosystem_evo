"""pytest 共通。"""
import pytest

from src.sim.systems.world import World


@pytest.fixture(scope="session", autouse=True)
def _register_game_actions():
    from src.game.ai import register_game_actions

    register_game_actions()


@pytest.fixture(autouse=True)
def _auto_bind_colony_for_test_worlds(monkeypatch):
    """`World()` / `World.from_json` 後、game 未接続なら bind_colony（sim は tests を import しない）。"""
    from tests.sim.colony_binding import bind_colony

    original_init = World._init_from_data

    def _init_from_data(self, world_data):
        original_init(self, world_data)
        if getattr(self, "on_creature_added", None) is None:
            bind_colony(self)

    monkeypatch.setattr(World, "_init_from_data", _init_from_data)
