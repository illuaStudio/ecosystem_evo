"""SimBridge 生成（ゲーム層フック付き）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.game.bridge_handlers import GAME_BRIDGE_HOOKS
from src.sim.bridge import SimBridge

if TYPE_CHECKING:
    from src.sim.systems.world import World


def make_sim_bridge(world: "World") -> SimBridge:
    return SimBridge(world, game_hooks=GAME_BRIDGE_HOOKS)
