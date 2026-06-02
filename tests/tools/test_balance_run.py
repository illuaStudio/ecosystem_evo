"""balance_run ヘッドレスランナーのフェーズ記録。"""
from __future__ import annotations

import unittest

from tools.balance_run import _population_detail, _soldier_count, _worker_count, run_balance
from src.sim.systems.world import World


class TestBalanceRunPhases(unittest.TestCase):
    def test_logs_defense_phase_with_fast_dev_ticks(self):
        report = run_balance(max_steps=120, dev_ticks=10, min_soldiers=0)
        labels = [m.label for m in report.milestones]
        self.assertTrue(
            any("防衛" in label or label.startswith("フェーズ: 防衛") for label in labels),
            f"expected defense milestone, got: {labels}",
        )
        self.assertIn(report.phase_end, ("defense", "story", "development"))

    def test_worker_count_excludes_soldiers(self):
        world = World("Grassland")
        soldier_species = ("red_ant_soldier",)
        detail = _population_detail(world, "red_ant", soldier_species)
        self.assertIn("workers=", detail)
        self.assertIn("soldiers=", detail)
        # 初期状態: 働きアリのみ（兵隊は 0）
        self.assertGreaterEqual(_worker_count(world, "red_ant", soldier_species), 0)
        self.assertEqual(_soldier_count(world, "red_ant", soldier_species), 0)


if __name__ == "__main__":
    unittest.main()
