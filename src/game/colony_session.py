"""World ごとの ColonyOrchestrator 参照（sim は game を import しない）。"""
from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from src.game.colony_orchestrator import ColonyOrchestrator
    from src.sim.systems.world import World

_orchestrators: weakref.WeakKeyDictionary["World", "ColonyOrchestrator"] = (
    weakref.WeakKeyDictionary()
)


def attach_colony_config(world: "World") -> None:
    """World の affiliation レイアウトを ColonyConfig に解釈して載せる。"""
    from src.game.colony_config import ColonyConfig

    if getattr(world, "_colony_config", None) is None:
        world._colony_config = ColonyConfig.from_affiliation_block(
            getattr(world, "_affiliation_layout_raw", None) or {}
        )


def attach_colony_orchestrator(world: "World", orchestrator: "ColonyOrchestrator") -> None:
    from src.game.ai import register_game_actions

    attach_colony_config(world)
    register_game_actions()
    _orchestrators[world] = orchestrator
    world.access_damage_handler = orchestrator.damage_access  # type: ignore[attr-defined]
    world.on_creature_added = orchestrator.assign_creature_on_spawn  # type: ignore[attr-defined]
    orchestrator.bootstrap_existing_creatures()


def get_colony_orchestrator(world: "World") -> "ColonyOrchestrator":
    orch = _orchestrators.get(world)
    if orch is None:
        raise RuntimeError(
            "ColonyOrchestrator が未登録です。GameController.reset_for_world または "
            "tests.sim.colony_binding.bind_colony を呼んでください。"
        )
    return orch


def try_get_colony_orchestrator(world: "World") -> Optional["ColonyOrchestrator"]:
    return _orchestrators.get(world)
