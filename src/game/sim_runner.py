"""シミュレーション tick のスケジューリング（Client から利用）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World


class SimRunner:
    """レンダー tick とシミュ tick の比率を管理し、World を進める。

    加速は「等倍の1ステップ」を整数回だけ繰り返す。dt を巨大化しない。
    Game の on_tick は各 step_once の直後に1回（sim_tick_pipeline.advance_sim_gate）。
    同じ回数だけ進めれば加速倍率に関係なく結果は一致する（試験は test_sim_determinism）。
    """

    def __init__(self, sim_config: dict | None = None) -> None:
        if sim_config is None:
            from src.config import config

            sim_config = config.sim
        self._config = dict(sim_config)
        self.sim_ticks_per_step = max(1, int(self._config.get("sim_ticks_per_step", 10)))
        self.simulation_speed = float(self._config.get("simulation_speed", 1.0))
        self._render_ticks_until_sim = 0
        self._step_credit = 0.0

    def reload(self, sim_config: dict | None = None) -> None:
        if sim_config is None:
            from src.config import config

            sim_config = config.sim
        self._config = dict(sim_config)
        self.sim_ticks_per_step = max(1, int(self._config.get("sim_ticks_per_step", 10)))
        self.simulation_speed = float(self._config.get("simulation_speed", 1.0))
        self._render_ticks_until_sim = 0
        self._step_credit = 0.0

    def set_simulation_speed(self, speed: float) -> None:
        """等倍ステップの繰り返し回数（平均）。1.0 = 通常、2.0 = 2倍早送り。"""
        try:
            s = float(speed)
        except Exception:
            return
        self.simulation_speed = max(0.1, min(32.0, s))

    def get_simulation_speed(self) -> float:
        return float(self.simulation_speed)

    def sim_dt(self) -> float:
        """1 等倍ステップあたりの dt（表示・換算用）。"""
        return float(self.sim_ticks_per_step)

    def should_run_sim_tick(self) -> bool:
        if self._render_ticks_until_sim > 0:
            self._render_ticks_until_sim -= 1
            return False
        self._render_ticks_until_sim = self.sim_ticks_per_step - 1
        return True

    def step_once(self, world: "World") -> None:
        """等倍 1 回分: maintenance + world.update(base_dt)。"""
        base_dt = float(self.sim_ticks_per_step)
        self._run_game_maintenance(world, base_dt)
        world.update(base_dt)

    def consume_steps(self, limit: int | None = None) -> int:
        """速度倍率に応じて今ゲートで進める等倍ステップ数（step_once は呼ばない）。

        limit を指定した場合、その回は最大 limit まで（クレジットは実行分だけ減る）。
        """
        speed = float(self.simulation_speed)
        if speed <= 0:
            return 0

        self._step_credit += speed
        steps = int(self._step_credit)
        if steps <= 0:
            return 0
        if limit is not None:
            steps = min(steps, max(0, int(limit)))
        self._step_credit -= float(steps)
        return steps

    def tick(self, world: "World") -> int:
        """速度倍率ぶんの等倍ステップを実行（Sim のみ、Game on_tick なし）。

        Client / 試験では sim_tick_pipeline.advance_sim_gate を使うこと。
        """
        steps = self.consume_steps()
        for _ in range(steps):
            self.step_once(world)
        return steps

    @staticmethod
    def _run_game_maintenance(world: "World", dt: float) -> None:
        try:
            from src.game.colony_session import get_colony_orchestrator

            orch = get_colony_orchestrator(world)
            orch.update(dt)
        except RuntimeError:
            pass
        except Exception:
            pass
