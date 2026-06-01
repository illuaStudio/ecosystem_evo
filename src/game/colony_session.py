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

DEFAULT_SHELTER_ALLOWED_ACTION_NAMES = frozenset({
    "SeekShelterAction",
    "FeedAtNestAction",
    "FeedAtAffiliationSiteAction",
    "AffiliationReproduceAction",
})


def attach_colony_config(world: "World") -> None:
    """コロニー用の避難所許可行動などを World に載せる（レイアウトは sim が既に解析済み）。"""
    world.shelter_allowed_action_names = DEFAULT_SHELTER_ALLOWED_ACTION_NAMES


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
