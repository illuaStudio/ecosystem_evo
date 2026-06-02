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
        dt = self.sim_dt()
        # Run game maintenance (e.g. affiliation storage leaks) that used to be
        # performed via direct hook injection (World.on_sim_tick). This keeps
        # the sim layer (World) free of game-specific callbacks.
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
