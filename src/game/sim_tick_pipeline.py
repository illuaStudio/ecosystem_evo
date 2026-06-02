"""Sim + Game の1ゲート進行（Client / balance_run / 試験で共通）。

加速は SimRunner.consume_steps() で「何回回すか」だけ決め、
各回は必ず step_once → on_tick の順（速度に依存しない）。
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.game import client_api
from src.game.game_message import GameMessage

if TYPE_CHECKING:
    from src.game.game_controller import GameController
    from src.game.sim_runner import SimRunner
    from src.sim.systems.world import World


def advance_sim_gate(
    runner: "SimRunner",
    world: "World",
    controller: "GameController",
    *,
    max_steps: int | None = None,
) -> tuple[int, list[GameMessage]]:
    """1 sim gate: sim 停止時は on_tick のみ、否则は consume_steps 回の (step_once + on_tick)。"""
    messages: list[GameMessage] = []
    if not client_api.should_advance_sim(controller):
        messages.extend(controller.on_tick(world))
        return 0, messages

    steps = runner.consume_steps(max_steps)
    for _ in range(steps):
        runner.step_once(world)
        messages.extend(controller.on_tick(world))
    return steps, messages


def advance_paired_sim_steps(
    runner: "SimRunner",
    world: "World",
    controller: "GameController",
    *,
    count: int = 1,
) -> list[GameMessage]:
    """正確に count 回: 毎回 step_once（sim 可）→ on_tick。加速倍率は使わない。"""
    messages: list[GameMessage] = []
    n = max(0, int(count))
    for _ in range(n):
        if client_api.should_advance_sim(controller):
            runner.step_once(world)
        messages.extend(controller.on_tick(world))
    return messages


def advance_render_frame(
    runner: "SimRunner",
    world: "World",
    controller: "GameController",
) -> tuple[int, list[GameMessage]]:
    """Client 1 描画フレーム分。sim_ticks_per_step 未満のフレームは (-1, [])。"""
    if not runner.should_run_sim_tick():
        return -1, []
    return advance_sim_gate(runner, world, controller)
