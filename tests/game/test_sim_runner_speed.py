"""SimRunner: 加速 = 等倍 step_once の繰り返し。"""
from __future__ import annotations

import unittest

from src.game.sim_runner import SimRunner
from tests.sim.world_fixtures import load_test_world


class TestSimRunnerSpeed(unittest.TestCase):
    def test_fast_forward_advances_same_sim_time_as_repeated_1x(self):
        """4x で 10 ゲート = step_once×40 と、1x で step_once×40 は同じ _sim_time。"""
        total_steps = 40
        base_dt = 10.0

        world_a = load_test_world(name="ReplayA", world_width=400, world_height=400)
        runner_1x = SimRunner({"sim_ticks_per_step": int(base_dt), "simulation_speed": 1.0})
        for _ in range(total_steps):
            runner_1x.step_once(world_a)
        time_a = float(world_a._sim_time)

        world_b = load_test_world(name="ReplayB", world_width=400, world_height=400)
        runner_4x = SimRunner({"sim_ticks_per_step": int(base_dt), "simulation_speed": 4.0})
        for _ in range(total_steps // 4):
            steps = runner_4x.tick(world_b)
            self.assertEqual(steps, 4)
        time_b = float(world_b._sim_time)

        self.assertEqual(time_a, time_b)
        self.assertEqual(time_a, total_steps * base_dt)

    def test_tick_returns_zero_when_credit_below_one(self):
        world = load_test_world(name="Slow", world_width=200, world_height=200)
        runner = SimRunner({"sim_ticks_per_step": 10, "simulation_speed": 0.25})
        runner._step_credit = 0.0
        self.assertEqual(runner.tick(world), 0)
        self.assertEqual(runner.tick(world), 0)
        self.assertEqual(runner.tick(world), 0)
        self.assertEqual(runner.tick(world), 1)


if __name__ == "__main__":
    unittest.main()
