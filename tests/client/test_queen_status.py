"""女王 HUD ヘルパーのテスト。"""
import unittest

from src.client.queen_status import build_queen_panel_lines, find_colony_queen
from src.game.game_state import GameState
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from tests.sim.world_fixtures import colony_settings


def _player_world(**overrides) -> World:
    data = {
        "name": "QueenPanelTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"red_ant": 20, "red_ant_queen": 3},
        "colony": colony_settings(
            factions={"red_ant": {"label": "R"}},
            faction_species={
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_queen"],
            },
        ),
    }
    data.update(overrides)
    return World.from_json(data)


class TestQueenStatus(unittest.TestCase):
    def test_find_colony_queen(self):
        world = _player_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")

        found = find_colony_queen(world, "red_ant")
        self.assertIs(found, queen)

    def test_panel_shows_sheltered_queen(self):
        world = _player_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        queen.shelter = object()

        state = GameState(player_colony_id="red_ant")
        lines = build_queen_panel_lines(world, "red_ant", state)
        texts = [t for t, _ in lines]

        self.assertTrue(any("【女王】" in t for t in texts))
        self.assertTrue(any("巣穴内" in t for t in texts))
        self.assertTrue(any("進行:" in t for t in texts))
        self.assertTrue(any("産卵: ゲーム進行待ち" in t for t in texts))

    def test_panel_shows_reproduction_when_unlocked(self):
        world = _player_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        queen.shelter = object()

        from src.game.command_builder import apply_mind_profile
        from src.sim.bridge import SimBridge

        apply_mind_profile(
            SimBridge(world),
            queen,
            "queen_feed_and_workers",
            mode="replace",
        )

        state = GameState(player_colony_id="red_ant")
        state.flags["queen_can_reproduce"] = True
        lines = build_queen_panel_lines(world, "red_ant", state)
        texts = [t for t, _ in lines]

        self.assertTrue(any(t.startswith("産卵:") for t in texts))
        self.assertFalse(any("ゲーム進行待ち" in t for t in texts))


if __name__ == "__main__":
    unittest.main()
