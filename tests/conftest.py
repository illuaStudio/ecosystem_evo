"""pytest 共通。"""
import pytest


@pytest.fixture(scope="session", autouse=True)
def _register_game_actions():
    from src.game.ai import register_game_actions

    register_game_actions()
