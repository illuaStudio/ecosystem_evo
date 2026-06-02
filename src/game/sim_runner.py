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

    def set_simulation_speed(self, speed: float) -> None:
        """Adjust sim time acceleration (dt multiplier)."""
        try:
            s = float(speed)
        except Exception:
            return
        # Keep within a sane range to avoid numerical instability.
        self.simulation_speed = max(0.1, min(32.0, s))

    def get_simulation_speed(self) -> float:
        return float(self.simulation_speed)

    def sim_dt(self) -> float:
        return self.sim_ticks_per_step * self.simulation_speed

    def should_run_sim_tick(self) -> bool:
        if self._render_ticks_until_sim > 0:
            self._render_ticks_until_sim -= 1
            return False
        self._render_ticks_until_sim = self.sim_ticks_per_step - 1
        return True

    def tick(self, world: "World") -> None:
        """Advance simulation time.

        Important: simulation_speed accelerates time *without* coarsening the dt.
        If we simply multiply dt, per-tick effects (e.g. FeedAtNestAction's
        feed_per_tick) become weaker relative to per-dt effects (metabolism),
        causing behavior changes at high speeds. We therefore step multiple
        sub-updates for speed>=1.0.
        """
        base_dt = float(self.sim_ticks_per_step)
        speed = float(self.simulation_speed)
        if speed <= 0:
            return

        if speed < 1.0:
            dt = base_dt * speed
            self._run_game_maintenance(world, dt)
            world.update(dt)
            return

        whole = int(speed)
        frac = speed - float(whole)

        for _ in range(max(1, whole)):
            self._run_game_maintenance(world, base_dt)
            world.update(base_dt)
        if frac > 1e-6:
            dt = base_dt * frac
            self._run_game_maintenance(world, dt)
            world.update(dt)

    @staticmethod
    def _run_game_maintenance(world: "World", dt: float) -> None:
        try:
            from src.game.colony_session import get_colony_orchestrator

            orch = get_colony_orchestrator(world)
            orch.update(dt)
        except RuntimeError:
            # no orchestrator (e.g. test world without colony)
            pass
        except Exception:
            pass
