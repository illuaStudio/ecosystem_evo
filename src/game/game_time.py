"""ゲーム開始からの経過時間（Client 表示用の換算）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World


def sim_ticks_per_real_second() -> float:
    from src.config import config as cfg

    fps = float(cfg.client.get("fps", 60))
    ticks_per_step = max(1, int(cfg.sim.get("sim_ticks_per_step", 10)))
    speed = float(cfg.sim.get("simulation_speed", 1.0))
    # One sim gate per (ticks_per_step) render frames; each gate runs ~speed
    # step_once calls (each with dt=ticks_per_step). sim_ticks_per_step cancels:
    # _sim_time grows at ~fps*speed per real second.
    gates_per_sec = fps / float(ticks_per_step)
    return max(1.0, gates_per_sec * ticks_per_step * speed)


def elapsed_seconds(world: "World | None") -> float:
    """ワールドの _sim_time を実秒に換算（メインループと同じ前提）。"""
    if world is None:
        return 0.0
    sim_time = float(getattr(world, "_sim_time", 0.0))
    return sim_time / sim_ticks_per_real_second()
