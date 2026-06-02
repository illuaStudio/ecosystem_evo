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


def _fast_game_config(**phase_overrides) -> dict:
    phases = {
        "development_ticks_before_defense": 5,
        "story_ticks_before_resume": 3,
        "auto_start_defense": True,
        "auto_resume_after_story": True,
        "cycle_waves": True,
    }
    phases.update(phase_overrides)
    return {
        "player_affiliation_id": "red_ant",
        "phases": phases,
    }


def _player_world(**overrides) -> World:
    return load_test_world(
        name="PhaseWaveTest",
        world_width=800,
        world_height=800,
        population_limits={
            "red_ant": 20,
            "red_ant_queen": 3,
            "red_ant_soldier": 10,
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


def _sim_tick(world: World) -> None:
    from src.game.sim_runner import SimRunner

    SimRunner({"sim_ticks_per_step": 1, "simulation_speed": 1.0}).tick(world)


def _advance_until(ctrl: GameController, world: World, *, phase: GamePhase, max_ticks: int = 500) -> None:
    for _ in range(max_ticks):
        if ctrl.phase is phase:
            return
        if client_api.should_advance_sim(ctrl):
            _sim_tick(world)
        ctrl.on_tick(world)
    raise AssertionError(f"phase {phase} not reached within {max_ticks} ticks")


def _kill_wave_enemies(ctrl: GameController, world: World) -> None:
    for creature in list(world.creatures):
        if (
            creature.species.name == "rival_ant_soldier"
            and id(creature) in ctrl.wave_director._spawned_ids
        ):
            creature.hp = 0.0
            creature.become_corpse(cause="hp")


def _clear_active_wave(ctrl: GameController, world: World, *, max_ticks: int = 400) -> None:
    """防衛中のウェーブ敵を倒し、ストーリーフェーズへ遷移させる。"""
    for _ in range(max_ticks):
        if ctrl.phase is GamePhase.STORY:
            return
        if ctrl.phase is GamePhase.DEFENSE:
            _kill_wave_enemies(ctrl, world)
        if client_api.should_advance_sim(ctrl):
            _sim_tick(world)
        ctrl.on_tick(world)
    raise AssertionError("story phase not reached after clearing wave")


class TestPhaseWave(unittest.TestCase):
    def _controller(self, world: World | None = None, **phase_overrides) -> GameController:
        world = world or _player_world()
        bridge = SimBridge(world)
        ctrl = GameController(_fast_game_config(**phase_overrides), bridge=bridge)
        ctrl.reset_for_world(world, bridge=bridge)
        world.events.drain()
        return ctrl

    def test_should_advance_sim_false_during_story(self):
        pc = PhaseController.from_config(_fast_game_config())
        pc.phase = GamePhase.STORY
        self.assertFalse(pc.should_run_sim())

    def test_manual_start_defense(self):
        cfg = _fast_game_config(auto_start_defense=False)
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

        _advance_until(ctrl, world, phase=GamePhase.DEFENSE, max_ticks=20)
        self.assertEqual(ctrl.wave_director.wave_index, 0)

        for _ in range(200):
            if ctrl.wave_director.wave_active and ctrl.wave_director.enemies_spawned_total >= 3:
                break
            if client_api.should_advance_sim(ctrl):
                _sim_tick(world)
            ctrl.on_tick(world)

        self.assertGreaterEqual(ctrl.wave_director.enemies_spawned_total, 1)
        _clear_active_wave(ctrl, world)

        _advance_until(ctrl, world, phase=GamePhase.STORY, max_ticks=10)
        view = client_api.get_phase_view(ctrl, world)
        self.assertTrue(view.story_pending)
        self.assertIn("先遣隊", view.story_text)

        _advance_until(ctrl, world, phase=GamePhase.DEVELOPMENT, max_ticks=20)
        self.assertEqual(ctrl.phase_controller.next_wave_index, 1)

    def test_full_cycle_restarts_after_all_waves(self):
        ctrl = self._controller()
        world = ctrl.bridge.world
        waves_total = len(ctrl.wave_director.waves)
        self.assertGreaterEqual(waves_total, 2)

        for wave_num in range(waves_total):
            _advance_until(ctrl, world, phase=GamePhase.DEFENSE, max_ticks=30)
            self.assertEqual(ctrl.wave_director.wave_index, wave_num)

            for _ in range(200):
                if ctrl.wave_director.enemies_spawned_total > 0:
                    break
                if client_api.should_advance_sim(ctrl):
                    _sim_tick(world)
                ctrl.on_tick(world)

            _clear_active_wave(ctrl, world)
            self.assertEqual(ctrl.phase, GamePhase.STORY)
            _advance_until(ctrl, world, phase=GamePhase.DEVELOPMENT, max_ticks=20)

        view = client_api.get_phase_view(ctrl, world)
        self.assertTrue(view.waves_cycled)
        self.assertEqual(ctrl.phase_controller.next_wave_index, 0)

        _advance_until(ctrl, world, phase=GamePhase.DEFENSE, max_ticks=30)
        self.assertEqual(ctrl.wave_director.wave_index, 0)

    def test_player_defeat_during_defense_enters_story(self):
        cfg = _fast_game_config(auto_start_defense=False)
        world = _player_world()
        bridge = SimBridge(world)
        ctrl = GameController(cfg, bridge=bridge)
        ctrl.reset_for_world(world, bridge=bridge)
        self.assertTrue(client_api.request_start_defense(ctrl))

        orch = client_api.try_get_colony_orchestrator(world)
        self.assertIsNotNone(orch)
        orch.defeat_affiliation("red_ant")
        ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.STORY)
        view = client_api.get_phase_view(ctrl, world)
        self.assertTrue(view.story_pending)
        self.assertFalse(ctrl.wave_director.wave_active)

    def test_wave_director_loads_config(self):
        wd = WaveDirector.from_json(player_affiliation_id="red_ant")
        self.assertGreaterEqual(len(wd.waves), 2)
        self.assertEqual(wd.waves[0].id, "wave_1")
        self.assertEqual(wd.waves[1].id, "wave_2")

    def test_client_api_phase_view(self):
        ctrl = self._controller()
        view = client_api.get_phase_view(ctrl, ctrl.bridge.world)
        self.assertEqual(view.phase, "development")
        self.assertGreaterEqual(view.waves_total, 2)


if __name__ == "__main__":
    unittest.main()
