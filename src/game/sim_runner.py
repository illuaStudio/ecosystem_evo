"""シミュレーション tick のスケジューリング（Client から利用）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World


class SimRunner:
    """レンダー tick とシミュ tick の比率を管理し、World を進める。"""

    def __init__(self, sim_config: dict | None = None) -> None:
        if sim_config is None:
            from src.config import config

            sim_config = config.sim
        self._config = dict(sim_config)
        self.sim_ticks_per_step = max(1, int(self._config.get("sim_ticks_per_step", 10)))
        self.simulation_speed = float(self._config.get("simulation_speed", 1.0))
        self._render_ticks_until_sim = 0

    def reload(self, sim_config: dict | None = None) -> None:
        if sim_config is None:
            from src.config import config

            sim_config = config.sim
        self._config = dict(sim_config)
        self.sim_ticks_per_step = max(1, int(self._config.get("sim_ticks_per_step", 10)))
        self.simulation_speed = float(self._config.get("simulation_speed", 1.0))
        self._render_ticks_until_sim = 0

    def sim_dt(self) -> float:
        return self.sim_ticks_per_step * self.simulation_speed

    def should_run_sim_tick(self) -> bool:
        if self._render_ticks_until_sim > 0:
            self._render_ticks_until_sim -= 1
            return False
        self._render_ticks_until_sim = self.sim_ticks_per_step - 1
        return True

    def tick(self, world: "World") -> None:
        world.update(self.sim_dt())
