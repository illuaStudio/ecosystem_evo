"""World ごとの ColonyOrchestrator 参照（sim は game を import しない）。"""
from __future__ import annotations

import weakref
from typing import TYPE_CHECKING, List, Optional

from src.game.colony_runtime import ColonyRuntimeState

if TYPE_CHECKING:
    from src.game.colony_orchestrator import ColonyOrchestrator
    from src.game.events import GameEvent
    from src.sim.systems.world import World

_orchestrators: weakref.WeakKeyDictionary["World", "ColonyOrchestrator"] = (
    weakref.WeakKeyDictionary()
)
_runtime_states: weakref.WeakKeyDictionary["World", ColonyRuntimeState] = (
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


def _make_defeated_checker(world: "World"):
    def check(affiliation_id: str) -> bool:
        runtime = _runtime_states.get(world)
        if runtime is None:
            return False
        return runtime.is_defeated(affiliation_id)

    return check


def attach_colony_orchestrator(world: "World", orchestrator: "ColonyOrchestrator") -> None:
    from src.game.ai import register_game_actions

    attach_colony_config(world)
    register_game_actions()
    _orchestrators[world] = orchestrator
    runtime = ColonyRuntimeState()
    _runtime_states[world] = runtime
    world.defeated_affiliation_checker = _make_defeated_checker(world)  # type: ignore[attr-defined]
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


def get_colony_runtime(world: "World") -> Optional[ColonyRuntimeState]:
    return _runtime_states.get(world)


def get_defeated_affiliations(world: "World") -> set[str]:
    runtime = _runtime_states.get(world)
    if runtime is None:
        return set()
    return set(runtime.defeated)


def get_last_defeat_message(world: "World") -> str:
    runtime = _runtime_states.get(world)
    if runtime is None:
        return ""
    return runtime.last_defeat_message


def drain_game_events(world: "World") -> List["GameEvent"]:
    runtime = _runtime_states.get(world)
    if runtime is None or not runtime.pending_events:
        return []
    events = list(runtime.pending_events)
    runtime.pending_events.clear()
    return events
