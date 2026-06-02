"""フェーズ条件・女王 AI 差し替えの Game 層テスト。"""
from __future__ import annotations

import unittest

from src.game.game_controller import GameController
from src.game.phase_ai import count_alive_soldiers
from src.game.phases import GamePhase
from src.sim.bridge import SimBridge
from src.sim.systems.world import World
from tests.sim.world_fixtures import (
    RIVAL_ANT_PROFILE,
    RED_ANT_PROFILE,
    affiliation_settings,
    load_test_world,
)


def _cfg(**phase) -> dict:
    phases = {
        "development_ticks_before_defense": 5,
        "story_ticks_before_resume": 2,
        "auto_start_defense": True,
        "auto_resume_after_story": True,
        "cycle_waves": False,
        "min_soldiers_before_defense": 3,
    }
    phases.update(phase)
    return {"player_affiliation_id": "red_ant", "phases": phases}


def _world(**overrides) -> World:
    return load_test_world(
        name="PhaseAITest",
        world_width=800,
        world_height=800,
        population_limits={
            "red_ant": 20,
            "red_ant_queen": 3,
            "red_ant_soldier": 10,
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
                "rival_ant": ["rival_ant_soldier"],
            },
        ),
        **overrides,
    )


class TestPhaseAI(unittest.TestCase):
    def _ensure_queen(self, ctrl: GameController, world: World) -> None:
        from src.game.phase_ai import find_colony_queen

        if find_colony_queen(world, "red_ant") is not None:
            return
        ctrl.spawn_creature("red_ant_queen", source="test")
        ctrl.on_tick(world)

    def _spawn_soldiers(self, ctrl: GameController, world: World, count: int = 3) -> None:
        for _ in range(count):
            ctrl.spawn_creature("red_ant_soldier", source="test")

    def test_defense_waits_for_three_soldiers(self):
        world = _world()
        bridge = SimBridge(world)
        ctrl = GameController(_cfg(), bridge=bridge)
        ctrl.reset_for_world(world, bridge=bridge)
        world.events.drain()
        self._ensure_queen(ctrl, world)

        for _ in range(20):
            world.update(1.0)
            ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.DEVELOPMENT)

        self._spawn_soldiers(ctrl, world, 3)
        for _ in range(10):
            if ctrl.phase is GamePhase.DEFENSE:
                break
            world.update(1.0)
            ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.DEFENSE)
        self.assertGreaterEqual(
            count_alive_soldiers(world, "red_ant", ("red_ant_soldier",)), 3
        )

    def test_queen_combat_when_soldiers_wiped(self):
        world = _world()
        bridge = SimBridge(world)
        ctrl = GameController(_cfg(), bridge=bridge)
        ctrl.reset_for_world(world, bridge=bridge)
        world.events.drain()
        ctrl.state.set_flag("queen_can_spawn_soldiers")
        self._ensure_queen(ctrl, world)

        self._spawn_soldiers(ctrl, world, 3)

        for _ in range(30):
            if ctrl.phase is GamePhase.DEFENSE:
                break
            world.update(1.0)
            ctrl.on_tick(world)

        self.assertEqual(ctrl.phase, GamePhase.DEFENSE)

        for creature in list(world.creatures):
            if creature.species.name == "red_ant_soldier" and creature.alive:
                creature.hp = 0.0
                creature.become_corpse(cause="hp")

        msgs = []
        for _ in range(5):
            world.update(1.0)
            msgs.extend(ctrl.on_tick(world))

        self.assertTrue(ctrl.phase_ai._queen_combat_active)
        self.assertTrue(any("女王が自ら" in m.text for m in msgs))

        queen = None
        for creature in world.creatures:
            if creature.species.name == "red_ant_queen" and creature.alive:
                queen = creature
                break
        self.assertIsNotNone(queen)
        self.assertGreaterEqual(queen.max_hp, 2000.0)
        action_names = [a.get("name") for a in queen.mind.action_defs]
        self.assertIn("CombatAction", action_names)

        # End defense: should return queen to shelter and restore reproduction profile.
        # Force wave to be clearable quickly: mark all spawns done and kill any spawned enemies.
        ctrl.wave_director.debug_exhaust_budgets()
        ctrl.wave_director.debug_destroy_all_holes(world)
        for creature in list(world.creatures):
            if creature.species.name == "invader_ant" and creature.alive:
                creature.hp = 0.0
                creature.become_corpse(cause="hp")
        for _ in range(80):
            world.update(1.0)
            ctrl.on_tick(world)
            if ctrl.phase is GamePhase.DEVELOPMENT:
                break
        self.assertEqual(ctrl.phase, GamePhase.DEVELOPMENT)
        names = [a.get("name") for a in queen.mind.action_defs]
        self.assertNotIn("CombatAction", names)
        self.assertIn("FeedAtNestAction", names)


if __name__ == "__main__":
    unittest.main()
