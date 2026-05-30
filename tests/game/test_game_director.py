"""GameDirector 進行ロジックのテスト。"""
import unittest

from src.game.game_director import GameDirector
from src.game.game_monitor import GameMonitor
from src.game.game_state import GameState
from src.sim.bridge import SimBridge
from src.sim.emitters import emit_colony_defeated, emit_combat_started_creature
from src.sim.systems.world import World
from src.sim.entities.creature_factory import CreatureFactory


def _player_world(**overrides) -> World:
    data = {
        "name": "DirectorTest",
        "world_width": 800,
        "world_height": 800,
        "initial_entities": {},
        "population_limits": {"red_ant": 20, "red_ant_queen": 3, "blue_ant": 10},
        "colony": {
            "factions": {
                "red_ant": {"label": "R"},
                "blue_ant": {"label": "B"},
            },
            "faction_species": {
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_queen"],
                "blue_ant": ["blue_ant"],
            },
        },
    }
    data.update(overrides)
    return World.from_json(data)


class TestGameDirector(unittest.TestCase):
    def _director(self, world: World) -> GameDirector:
        state = GameState(player_colony_id="red_ant")
        return GameDirector(state, SimBridge(world))

    def test_first_enemy_contact(self):
        world = _player_world()
        factory = CreatureFactory()
        worker = factory.create("red_ant", world=world, x=120, y=120)
        soldier = factory.create("blue_ant_soldier", world=world, x=125, y=120)
        world.add_creature(worker, spawn_source="initial")
        world.add_creature(soldier, spawn_source="initial")
        emit_combat_started_creature(world, soldier, worker)
        events = world.events.drain()

        director = self._director(world)
        msgs = director.on_sim_events(events, world)
        combat_msgs = [m for m in msgs if "外敵" in m.text]
        self.assertEqual(len(combat_msgs), 1)
        self.assertTrue(director.state.has_flag("first_enemy_contact"))

    def test_colony_defeated_user_message(self):
        world = _player_world()
        emit_colony_defeated(world, "red_ant", "勢力 red_ant が敗北しました")
        events = world.events.drain()

        director = self._director(world)
        msgs = director.on_sim_events(events, world)
        self.assertEqual(director.user_message, "勢力 red_ant が敗北しました")
        self.assertEqual(len(msgs), 1)
        self.assertEqual(director.state.stability_level, 0.0)

    def test_monitor_alert_to_message(self):
        world = _player_world()
        factory = CreatureFactory()
        queen = factory.create("red_ant_queen", world=world, x=120, y=120)
        world.add_creature(queen, spawn_source="initial")
        nest = world.nest_system.get_colony_nest("red_ant")
        world.events.drain()

        director = self._director(world)
        nest.stored_food = nest.max_food * 0.05
        alerts = GameMonitor({"low_food_ratio": 0.10}).check(world, director.state)
        msgs = director.on_monitor_alerts(alerts, world)
        self.assertEqual(len(msgs), 1)
        self.assertIn("低下", msgs[0].text)

        director.update_derived_levels(world)
        self.assertGreater(director.state.danger_level, 0.0)


if __name__ == "__main__":
    unittest.main()
