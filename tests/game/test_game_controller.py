"""ゲームレイヤー（GameController / GameMonitor）のテスト。"""
import unittest

from src.sim.ai.actions import ColonyReproduceAction
from src.sim.entities.creature_factory import CreatureFactory
from src.game.game_controller import GameController
from src.game.game_monitor import GameMonitor
from src.game.mind_policy import MindPolicy
from src.sim.bridge import SimBridge
from src.sim.emitters import emit_colony_defeated, emit_combat_started_creature
from src.sim.systems.world import World
from tests.sim.world_fixtures import colony_settings


def _player_world(**overrides) -> World:
    data = {
        "name": "GameLayerTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"red_ant": 20, "red_ant_queen": 3, "blue_ant": 10},
        "colony": colony_settings(
            factions={
                "red_ant": {"label": "R"},
                "blue_ant": {"label": "B"},
            },
            faction_species={
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_queen"],
                "blue_ant": ["blue_ant"],
            },
        ),
    }
    data.update(overrides)
    return World.from_json(data)


class TestGameMonitor(unittest.TestCase):
    def test_low_food_alert_once(self):
        world = _player_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        nest = world.nest_system.get_colony_nest("red_ant")
        world.events.drain()

        monitor = GameMonitor({"low_food_ratio": 0.10})
        from src.game.game_state import GameState

        state = GameState(player_colony_id="red_ant")

        nest.stored_food = nest.max_food * 0.05
        alerts = monitor.check(world, state)
        self.assertEqual(len(alerts), 1)
        self.assertIn("低下", alerts[0].message)

        alerts = monitor.check(world, state)
        self.assertEqual(alerts, [])


class TestGameController(unittest.TestCase):
    def _controller(self, world: World | None = None) -> GameController:
        world = world or _player_world()
        bridge = SimBridge(world)
        ctrl = GameController(
            {
                "player_colony_id": "red_ant",
                "monitor": {
                    "low_food_ratio": 0.10,
                    "high_food_ratio": 0.50,
                    "milestone_workers": 3,
                },
            },
            bridge=bridge,
        )
        return ctrl

    def test_first_reproduction_message(self):
        world = _player_world()
        ctrl = self._controller(world)
        ctrl.reset_for_world(world, bridge=ctrl.bridge)

        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        nest = world.nest_system.get_colony_nest("red_ant")
        world.events.drain()

        profile = MindPolicy().get_profile("workers_only") or {}
        params = next(
            a["params"]
            for a in profile["actions"]
            if a["name"] == "ColonyReproduceAction"
        )
        from src.sim.utils.colony_config_helpers import get_min_food_reserve

        nest.stored_food = get_min_food_reserve(world) + float(params["food_cost"]) + 10
        action = ColonyReproduceAction(**{**params, "spawn_cooldown": 0})
        action.execute(queen)

        msgs = ctrl.on_tick(world)
        repro_msgs = [m for m in msgs if "産み" in m.text]
        self.assertEqual(len(repro_msgs), 1)
        self.assertTrue(ctrl.state.has_flag("first_reproduction"))

        msgs = ctrl.on_tick(world)
        repro_msgs = [m for m in msgs if "産み" in m.text]
        self.assertEqual(repro_msgs, [])

    def test_colony_defeated_sets_user_message(self):
        world = _player_world()
        ctrl = self._controller(world)
        ctrl.reset_for_world(world, bridge=ctrl.bridge)

        emit_colony_defeated(world, "red_ant", "勢力 red_ant が敗北しました")
        msgs = ctrl.on_tick(world)

        self.assertEqual(ctrl.user_message, "勢力 red_ant が敗北しました")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(ctrl.state.stability_level, 0.0)

    def test_first_enemy_contact_on_rival_attack(self):
        world = _player_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=120, y=120)
        soldier = factory.create("blue_ant_soldier", world=world, x=125, y=120)
        world.add_creature(worker, spawn_source="initial")
        world.add_creature(soldier, spawn_source="initial")
        world.events.drain()

        ctrl = self._controller(world)
        ctrl.reset_for_world(world, bridge=ctrl.bridge)
        emit_combat_started_creature(world, soldier, worker)

        msgs = ctrl.on_tick(world)
        combat_msgs = [m for m in msgs if "外敵" in m.text]
        self.assertEqual(len(combat_msgs), 1)
        self.assertTrue(ctrl.state.has_flag("first_enemy_contact"))

    def test_monitor_low_food_via_on_tick(self):
        world = _player_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        nest = world.nest_system.get_colony_nest("red_ant")
        world.events.drain()

        ctrl = self._controller(world)
        ctrl.reset_for_world(world, bridge=ctrl.bridge)
        nest.stored_food = nest.max_food * 0.05

        msgs = ctrl.on_tick(world)
        low_msgs = [m for m in msgs if m.source == "monitor" and "低下" in m.text]
        self.assertEqual(len(low_msgs), 1)
        self.assertGreater(ctrl.state.danger_level, 0.0)


if __name__ == "__main__":
    unittest.main()
