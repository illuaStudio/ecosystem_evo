"""balance_run ヘッドレスランナーのフェーズ記録。"""
from __future__ import annotations

import unittest

from tools.balance_run import run_balance


class TestBalanceRunPhases(unittest.TestCase):
    def test_logs_defense_phase_with_fast_dev_ticks(self):
        report = run_balance(max_steps=120, dev_ticks=10)
        labels = [m.label for m in report.milestones]
        self.assertTrue(
            any("防衛" in label or label.startswith("フェーズ: 防衛") for label in labels),
            f"expected defense milestone, got: {labels}",
        )
        self.assertIn(report.phase_end, ("defense", "story", "development"))


if __name__ == "__main__":
    unittest.main()
