"""progression.json 解禁のテスト。"""
import unittest

from src.game.game_controller import GameController
from src.game.game_monitor import GameMonitor
from src.game.game_state import GameState
from src.game.progression import ProgressionEvaluator, apply_unlock, load_progression
from src.sim.bridge import SimBridge
from src.sim.entities.creature_factory import CreatureFactory
from src.sim.systems.world import World
from tests.sim.world_fixtures import affiliation_settings, load_test_world, set_colony_stored_food


def _player_world(**overrides) -> World:
    return load_test_world(
        name="ProgressionTest",
        world_width=800,
        world_height=800,
        population_limits={
            "red_ant": 20,
            "red_ant_queen": 3,
            "red_ant_soldier": 10,
        },
        affiliation=affiliation_settings(
            affiliation_species={
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_vanguard"],
            },
        ),
        **overrides,
    )


class TestProgressionLoader(unittest.TestCase):
    def test_loads_unlocks(self):
        unlocks = load_progression()
        ids = {u.id for u in unlocks}
        self.assertIn("queen_worker_reproduction", ids)
        self.assertIn("queen_soldier_reproduction", ids)


class TestProgressionUnlock(unittest.TestCase):
    def _setup_queen(self, world: World):
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        world.events.drain()
        bridge = SimBridge(world)
        from src.game.command_builder import apply_spawn_profile

        apply_spawn_profile(bridge, queen)
        return queen, bridge

    def test_high_food_unlocks_queen_reproduction(self):
        world = _player_world()
        queen, bridge = self._setup_queen(world)
        state = GameState(player_colony_id="red_ant")
        nest = world.nest_system.get_colony_nest("red_ant")

        self.assertEqual([a["name"] for a in queen.mind.action_defs], ["FeedAtNestAction"])

        state.set_flag("high_food_reached")
        set_colony_stored_food(world, "red_ant", nest.max_food * 0.55)

        evaluator = ProgressionEvaluator()
        msgs = evaluator.evaluate(bridge, state, world)

        self.assertIn("queen_worker_reproduction", state.applied_unlocks)
        self.assertTrue(state.has_flag("queen_can_reproduce"))
        self.assertEqual(len(msgs), 1)
        self.assertIn("産む準備", msgs[0].text)

        names = [a["name"] for a in queen.mind.action_defs]
        self.assertIn("FeedAtNestAction", names)
        self.assertIn("ColonyReproduceAction", names)

    def test_unlock_applied_only_once(self):
        world = _player_world()
        queen, bridge = self._setup_queen(world)
        state = GameState(player_colony_id="red_ant")
        state.set_flag("high_food_reached")

        evaluator = ProgressionEvaluator()
        msgs1 = evaluator.evaluate(bridge, state, world)
        msgs2 = evaluator.evaluate(bridge, state, world)

        self.assertEqual(len(msgs1), 1)
        self.assertEqual(msgs2, [])

    def test_soldier_unlock_requires_milestone_and_prior_unlock(self):
        world = _player_world()
        queen, bridge = self._setup_queen(world)
        nest = world.nest_system.get_colony_nest("red_ant")
        factory = CreatureFactory()

        state = GameState(player_colony_id="red_ant")
        state.applied_unlocks.add("queen_worker_reproduction")
        from src.game.command_builder import apply_mind_profile_to_colony_caste

        apply_mind_profile_to_colony_caste(
            bridge, "red_ant", "queen", "queen_feed_and_workers"
        )

        for i in range(5):
            worker = factory.create("red_ant", world=world, x=130 + i, y=120)
            world.add_creature(worker, spawn_source="initial")
        world.events.drain()

        monitor = GameMonitor({"milestone_workers": 5})
        monitor.check(world, state)

        evaluator = ProgressionEvaluator()
        msgs = evaluator.evaluate(bridge, state, world)

        self.assertIn("queen_soldier_reproduction", state.applied_unlocks)
        self.assertEqual(len(msgs), 1)
        self.assertIn("兵隊", msgs[0].text)

        repro = next(
            a for a in queen.mind.action_defs if a["name"] == "ColonyReproduceAction"
        )
        species = {e["species"] for e in repro["params"]["offspring"]}
        self.assertIn("red_ant_soldier", species)

    def test_via_game_controller_on_tick(self):
        world = _player_world()
        bridge = SimBridge(world)
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        nest = world.nest_system.get_colony_nest("red_ant")
        world.events.drain()

        ctrl = GameController(
            {
                "player_colony_id": "red_ant",
                "monitor": {"high_food_ratio": 0.10, "high_food_ratio": 0.50},
            },
            bridge=bridge,
        )
        ctrl.reset_for_world(world, bridge=bridge)

        set_colony_stored_food(world, "red_ant", nest.max_food * 0.55)
        msgs = ctrl.on_tick(world)

        progression_msgs = [m for m in msgs if m.source == "progression"]
        self.assertEqual(len(progression_msgs), 1)
        self.assertIn("queen_worker_reproduction", ctrl.state.applied_unlocks)


if __name__ == "__main__":
    unittest.main()
