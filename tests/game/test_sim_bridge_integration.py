"""GameController + SimBridge 統合テスト。"""
import unittest

from src.game.game_controller import GameController
from src.game.ai.reproduction_actions import AffiliationReproduceAction
from src.sim.bridge import SimBridge
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from tests.sim.world_fixtures import affiliation_settings


def _player_world(**overrides) -> World:
    data = {
        "name": "BridgeGameTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"red_ant": 20, "red_ant_queen": 3},
        "affiliation": affiliation_settings(),
    }
    data.update(overrides)
    return World.from_json(data)


class TestGameControllerBridge(unittest.TestCase):
    def test_spawn_creature_via_controller(self):
        world = _player_world()
        bridge = SimBridge(world)
        ctrl = GameController({"player_affiliation_id": "red_ant"}, bridge=bridge)

        creature = ctrl.spawn_creature("Spider", x=100, y=100, source="game")
        self.assertIsNotNone(creature)
        self.assertEqual(len(world.creatures), 1)

    def test_apply_mind_profile_via_controller(self):
        world = _player_world()
        bridge = SimBridge(world)
        ctrl = GameController({"player_affiliation_id": "red_ant"}, bridge=bridge)
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        world.events.drain()

        self.assertTrue(ctrl.apply_mind_profile(queen, "workers_and_soldiers"))
        species = {e["species"] for e in queen.mind.action_defs[0]["params"]["offspring"]}
        self.assertIn("red_ant_soldier", species)


if __name__ == "__main__":
    unittest.main()
