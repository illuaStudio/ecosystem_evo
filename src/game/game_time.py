"""ゲーム開始からの経過時間（Client 表示用の換算）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World


def sim_ticks_per_real_second() -> float:
    from src.config import config

    fps = float(config.client.get("fps", 60))
    speed = float(config.sim.get("simulation_speed", 1.0))
    # World._sim_time is advanced by dt passed to World.update().
    # The main loop runs World.update(dt=sim_ticks_per_step*speed) only once per
    # sim tick, which itself occurs every sim_ticks_per_step render frames.
    # Therefore sim_ticks_per_step cancels out and _sim_time grows at ~fps*speed.
    return max(1.0, fps * speed)


def elapsed_seconds(world: "World | None") -> float:
    """ワールドの _sim_time を実秒に換算（メインループと同じ前提）。"""
    if world is None:
        return 0.0
    sim_time = float(getattr(world, "_sim_time", 0.0))
    return sim_time / sim_ticks_per_real_second()
