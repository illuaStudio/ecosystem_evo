"""progression.json の読み込みと解禁評価。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.game.game_message import GameMessage
from src.game.game_state import GameState

if False:  # TYPE_CHECKING without import cycle
    from src.sim.bridge import SimBridge
    from src.sim.systems.world import World

_PROGRESSION_PATH = (
    Path(__file__).resolve().parent.parent.parent / "config" / "game" / "progression.json"
)


@dataclass(frozen=True)
class ProgressionCommandDef:
    type: str
    target: dict[str, Any] = field(default_factory=dict)
    profile: str = ""
    mode: str = "replace"
    species: str = ""
    x: float | None = None
    y: float | None = None
    source: str = "game"


@dataclass(frozen=True)
class UnlockDef:
    id: str
    requires_flags: tuple[str, ...] = ()
    requires_unlocks: tuple[str, ...] = ()
    commands: tuple[ProgressionCommandDef, ...] = ()
    message: str = ""
    set_flags: tuple[str, ...] = ()


def load_progression(path: Path | None = None) -> list[UnlockDef]:
    file_path = path or _PROGRESSION_PATH
    if not file_path.exists():
        return []
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    unlocks: list[UnlockDef] = []
    for raw in data.get("unlocks", []):
        commands = tuple(
            ProgressionCommandDef(
                type=str(cmd.get("type", "")),
                target=dict(cmd.get("target") or {}),
                profile=str(cmd.get("profile", "")),
                mode=str(cmd.get("mode", "replace")),
                species=str(cmd.get("species", "")),
                x=cmd.get("x"),
                y=cmd.get("y"),
                source=str(cmd.get("source", "game")),
            )
            for cmd in raw.get("commands") or []
        )
        unlocks.append(
            UnlockDef(
                id=str(raw["id"]),
                requires_flags=tuple(raw.get("requires_flags") or ()),
                requires_unlocks=tuple(raw.get("requires_unlocks") or ()),
                commands=commands,
                message=str(raw.get("message", "")),
                set_flags=tuple(raw.get("set_flags") or ()),
            )
        )
    return unlocks


def _unlock_ready(unlock: UnlockDef, state: GameState) -> bool:
    if unlock.id in state.applied_unlocks:
        return False
    for flag in unlock.requires_flags:
        if not state.has_flag(flag):
            return False
    for req in unlock.requires_unlocks:
        if req not in state.applied_unlocks:
            return False
    return True


def _resolve_colony_id(target: dict[str, Any], state: GameState) -> str | None:
    colony = target.get("colony")
    if colony == "player":
        return state.player_colony_id
    if colony:
        return str(colony)
    return None


def execute_progression_command(
    bridge: "SimBridge",
    cmd: ProgressionCommandDef,
    state: GameState,
    world: "World",
) -> bool:
    from src.game.command_builder import (
        apply_mind_profile,
        apply_mind_profile_to_colony_caste,
        apply_mind_profile_to_species,
        spawn_creature,
    )

    if cmd.type == "ApplyMindProfile":
        if not cmd.profile:
            return False
        target = cmd.target
        caste = target.get("caste")
        species = target.get("species") or cmd.species
        colony_id = _resolve_colony_id(target, state)

        if caste and colony_id:
            count = apply_mind_profile_to_colony_caste(
                bridge, colony_id, str(caste), cmd.profile, mode=cmd.mode
            )
            return count > 0
        if species:
            return (
                apply_mind_profile_to_species(
                    bridge,
                    species,
                    cmd.profile,
                    colony_id=colony_id,
                    mode=cmd.mode,
                )
                > 0
            )
        if colony_id:
            for creature in world.creatures:
                from src.sim.utils.colony_helpers import get_creature_colony_id

                if get_creature_colony_id(creature) == colony_id:
                    if apply_mind_profile(bridge, creature, cmd.profile, mode=cmd.mode):
                        return True
            return False
        return False

    if cmd.type == "SpawnCreature":
        species = cmd.species or str(cmd.target.get("species", ""))
        if not species:
            return False
        return spawn_creature(
            bridge, species, x=cmd.x, y=cmd.y, source=cmd.source
        ) is not None

    return False


def apply_unlock(
    bridge: "SimBridge",
    unlock: UnlockDef,
    state: GameState,
    world: "World",
) -> tuple[bool, GameMessage | None]:
    if unlock.id in state.applied_unlocks:
        return False, None

    all_ok = True
    for cmd in unlock.commands:
        if not execute_progression_command(bridge, cmd, state, world):
            all_ok = False
            break

    if not all_ok:
        return False, None

    state.applied_unlocks.add(unlock.id)
    for flag in unlock.set_flags:
        state.set_flag(flag)

    message = None
    if unlock.message:
        message = GameMessage(text=unlock.message, source="progression", priority=3)
    return True, message


class ProgressionEvaluator:
    def __init__(self, unlocks: list[UnlockDef] | None = None) -> None:
        self._unlocks = unlocks if unlocks is not None else load_progression()

    def evaluate(
        self,
        bridge: "SimBridge",
        state: GameState,
        world: "World",
    ) -> list[GameMessage]:
        messages: list[GameMessage] = []
        for unlock in self._unlocks:
            if not _unlock_ready(unlock, state):
                continue
            ok, msg = apply_unlock(bridge, unlock, state, world)
            if ok and msg is not None:
                messages.append(msg)
        return messages
