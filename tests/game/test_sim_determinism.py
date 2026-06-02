"""加速倍率に依存しない Sim+Game 進行（試験用）。"""
from __future__ import annotations

import unittest

from src.config import config
from src.game.game_controller import GameController
from src.game.sim_bridge_factory import make_sim_bridge
from src.game.sim_runner import SimRunner
from src.game.sim_seed import apply_simulation_seed
from src.game.sim_tick_pipeline import advance_paired_sim_steps, advance_sim_gate
from src.sim.systems.world import World


def _game_config_fast_defense() -> dict:
    return {
        "player_affiliation_id": "red_ant",
        "phases": {
            "development_ticks_before_defense": 400,
            "auto_start_defense": True,
            "min_soldiers_before_defense": 3,
            "cycle_waves": False,
        },
    }


def _creature_fingerprint(world: World) -> tuple:
    rows = []
    for creature in world.creatures:
        rows.append(
            (
                creature.species.name,
                round(float(creature.position.x), 3),
                round(float(creature.position.y), 3),
                round(float(creature.hp), 3),
                round(float(creature.max_hp), 3),
                bool(creature.alive),
            )
        )
    rows.sort()
    return (
        round(float(world._sim_time), 6),
        len(world.creatures),
        tuple(rows),
    )


def _run_until_sim_steps(
    *,
    seed: int,
    total_sim_steps: int,
    simulation_speed: float,
) -> tuple:
    """total_sim_steps 回の step_once（sim 停止時は on_tick のみ）まで進める。"""
    apply_simulation_seed(seed)
    config.reload_all()
    world = World("Grassland")
    bridge = make_sim_bridge(world)
    controller = GameController(_game_config_fast_defense(), bridge=bridge)
    controller.reset_for_world(world, bridge=bridge)
    world.events.drain()

    runner = SimRunner(
        {
            "sim_ticks_per_step": int(config.sim.get("sim_ticks_per_step", 10)),
            "simulation_speed": float(simulation_speed),
        }
    )
    done = 0
    game_ticks = 0
    while done < total_sim_steps:
        remaining = total_sim_steps - done
        steps, _ = advance_sim_gate(
            runner, world, controller, max_steps=remaining
        )
        game_ticks += 1
        if steps <= 0:
            done += 1
            continue
        done += steps

    return (
        done,
        game_ticks,
        controller.phase.value,
        controller.phase_controller.phase_ticks,
        bool(controller.state.has_flag("player_affiliation_defeated")),
        _creature_fingerprint(world),
    )


class TestSimDeterminism(unittest.TestCase):
    def test_speed_1x_and_32x_same_state_after_equal_sim_steps(self):
        """同じ sim ステップ数なら加速倍率に関係なく世界状態が一致する。"""
        total_steps = 256

        fp_1x = _run_until_sim_steps(
            seed=42, total_sim_steps=total_steps, simulation_speed=1.0
        )
        fp_32x = _run_until_sim_steps(
            seed=42, total_sim_steps=total_steps, simulation_speed=32.0
        )

        self.assertEqual(fp_1x[0], total_steps)
        self.assertEqual(fp_32x[0], total_steps)
        self.assertEqual(fp_1x[2:], fp_32x[2:])
        self.assertLess(fp_32x[1], fp_1x[1])

if __name__ == "__main__":
    unittest.main()
