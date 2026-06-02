"""シミュレーション tick のスケジューリング（Client から利用）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World


class SimRunner:
    """レンダー tick とシミュ tick の比率を管理し、World を進める。

    加速は「等倍の1ステップ」を整数回だけ繰り返す。dt を巨大化したり端数 dt
    で update したりしないので、早送りしてもシミュ結果は等倍と同型になる。
  （描画・入力はフレームごとに1回のまま。）
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

    def tick(self, world: "World") -> int:
        """速度倍率ぶんの等倍ステップを実行。戻り値は実行したステップ数。"""
        speed = float(self.simulation_speed)
        if speed <= 0:
            return 0

        self._step_credit += speed
        steps = int(self._step_credit)
        if steps <= 0:
            return 0
        self._step_credit -= float(steps)

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
