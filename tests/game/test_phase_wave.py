"""フェーズ制御と最小ウェーブの Game 層テスト。"""
from __future__ import annotations

import unittest

from src.game import client_api
from src.game.game_controller import GameController
from src.game.phases import GamePhase
from src.game.phase_controller import PhaseController
from src.game.wave_director import WaveDirector
from src.sim.bridge import SimBridge
from src.sim.systems.world import World
from tests.sim.world_fixtures import (
    RIVAL_ANT_PROFILE,
    RED_ANT_PROFILE,
    affiliation_settings,
    load_test_world,
)


def _fast_game_config() -> dict:
    return {
        "player_affiliation_id": "red_ant",
        "phases": {
            "development_ticks_before_defense": 5,
            "story_ticks_before_resume": 3,
            "auto_start_defense": True,
            "auto_resume_after_story": True,
        },
    }


def _player_world(**overrides) -> World:
    return load_test_world(
        name="PhaseWaveTest",
        world_width=800,
        world_height=800,
        population_limits={
            "red_ant": 20,
            "red_ant_queen": 3,
            "rival_ant": 10,
            "rival_ant_soldier": 10,
        },
        affiliation=affiliation_settings(
            profiles={
                "red_ant": {**RED_ANT_PROFILE, "initial_mass": 600},
                "rival_ant": dict(RIVAL_ANT_PROFILE),
            },
            factions={"red_ant": {"label": "R"}, "rival_ant": {"label": "B"}},
            affiliation_species={
                "red_ant": ["red_ant", "red_ant_soldier", "red_ant_queen"],
                "rival_ant": ["rival_ant", "rival_ant_soldier"],
            },
        ),
        **overrides,
    )


class TestPhaseWave(unittest.TestCase):
    def _controller(self, world: World | None = None) -> GameController:
        world = world or _player_world()
        bridge = SimBridge(world)
        ctrl = GameController(_fast_game_config(), bridge=bridge)
        ctrl.reset_for_world(world, bridge=bridge)
        world.events.drain()
        return ctrl

    def test_should_advance_sim_false_during_story(self):
        pc = PhaseController.from_config(_fast_game_config())
        pc.phase = GamePhase.STORY
        self.assertFalse(pc.should_run_sim())

    def test_manual_start_defense(self):
        cfg = _fast_game_config()
        cfg["phases"]["auto_start_defense"] = False
        world = _player_world()
        bridge = SimBridge(world)
        ctrl = GameController(cfg, bridge=bridge)
        ctrl.reset_for_world(world, bridge=bridge)
        self.assertTrue(client_api.request_start_defense(ctrl))
        self.assertEqual(ctrl.phase, GamePhase.DEFENSE)
        self.assertTrue(ctrl.wave_director.wave_active)
        self.assertFalse(client_api.request_start_defense(ctrl))

    def test_development_to_defense_to_story_loop(self):
        ctrl = self._controller()
        world = ctrl.bridge.world

        for _ in range(6):
            if client_api.should_advance_sim(ctrl):
                ctrl.bridge.world  # satisfy lint
                from src.game.sim_runner import SimRunner

                SimRunner({"sim_ticks_per_step": 1, "simulation_speed": 1.0}).tick(world)
            ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.DEFENSE)

        for _ in range(200):
            if ctrl.wave_director.wave_active and ctrl.wave_director.enemies_spawned_total >= 3:
                break
            if client_api.should_advance_sim(ctrl):
                from src.game.sim_runner import SimRunner

                SimRunner({"sim_ticks_per_step": 1, "simulation_speed": 1.0}).tick(world)
            ctrl.on_tick(world)

        self.assertGreaterEqual(ctrl.wave_director.enemies_spawned_total, 1)

        for creature in list(world.creatures):
            if (
                creature.species.name == "rival_ant_soldier"
                and id(creature) in ctrl.wave_director._spawned_ids
            ):
                creature.hp = 0.0
                creature.become_corpse(cause="hp")

        for _ in range(30):
            if ctrl.phase is GamePhase.STORY:
                break
            if client_api.should_advance_sim(ctrl):
                from src.game.sim_runner import SimRunner

                SimRunner({"sim_ticks_per_step": 1, "simulation_speed": 1.0}).tick(world)
            ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.STORY)
        self.assertTrue(client_api.get_phase_view(ctrl, world).story_pending)

        for _ in range(5):
            if ctrl.phase is GamePhase.DEVELOPMENT:
                break
            if client_api.should_advance_sim(ctrl):
                from src.game.sim_runner import SimRunner

                SimRunner({"sim_ticks_per_step": 1, "simulation_speed": 1.0}).tick(world)
            ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.DEVELOPMENT)
        self.assertEqual(ctrl.phase_controller.next_wave_index, 1)

    def test_wave_director_loads_config(self):
        wd = WaveDirector.from_json(player_affiliation_id="red_ant")
        self.assertGreaterEqual(len(wd.waves), 1)
        self.assertEqual(wd.waves[0].id, "wave_1")

    def test_client_api_phase_view(self):
        ctrl = self._controller()
        view = client_api.get_phase_view(ctrl, ctrl.bridge.world)
        self.assertEqual(view.phase, "development")
        self.assertGreaterEqual(view.waves_total, 1)


if __name__ == "__main__":
    unittest.main()
