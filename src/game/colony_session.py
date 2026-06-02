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

def attach_colony_config(world: "World") -> None:
    """コロニー用の避難所許可行動などを World に載せる（レイアウトは sim が既に解析済み）。

    Note: shelter action whitelist is now managed in game layer (shelter_helpers,
    bridge_handlers) via mind restriction on enter/exit, not by injecting on World.
    """
    # No longer inject shelter_allowed_action_names on world for independence.
    # The sim mind no longer filters using it.
    pass


def attach_colony_orchestrator(world: "World", orchestrator: "ColonyOrchestrator") -> None:
    from src.game.ai import register_game_actions

    attach_colony_config(world)
    register_game_actions()
    _orchestrators[world] = orchestrator
    runtime = ColonyRuntimeState()
    _runtime_states[world] = runtime
    # No direct attribute injection on World (on_sim_tick / on_creature_added /
    # access_damage_handler / defeated_affiliation_checker) for clean separation.
    # See GameController for explicit maintenance and assignment, and neutral
    # methods on World (mark/is_affiliation_defeated) + events.
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


def ensure_creature_affiliations(world: "World") -> None:
    """Game reaction to creature spawns: assign affiliations for any creatures
    whose species declares affiliation_data but are not yet assigned.

    This is called from SpawnEvent handling in the game director (event-driven path)
    and from test helpers. Replaces the old synchronous on_creature_added hook.
    """
    try:
        orch = get_colony_orchestrator(world)
    except Exception:
        return

    for creature in list(world.creatures):
        aff = getattr(creature, "affiliation", None)
        if aff is None or getattr(aff, "affiliation_id", None):
            continue
        data = getattr(creature.species, "affiliation_data", None) or {}
        if data:
            try:
                orch.assign_creature(creature, data)
            except Exception:
                pass
