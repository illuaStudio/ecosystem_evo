"""シミュレーション層: ゲーム層からの命令実行窓口。"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from src.sim.commands import (
    ClearCreatureDirective,
    EnterCreatureShelter,
    IssueCreatureDirective,
    PlaceSpawnEmitter,
    SetAffiliationCasteMind,
    SetCreatureMind,
    SetSpawnEmitterEnabled,
    SetSpeciesMind,
    SimCommand,
    SimCommandResult,
    SpawnCreature,
)
from src.sim.entities.creature_factory import CreatureFactory

if TYPE_CHECKING:
    from src.sim.systems.world import World


def _creature_by_id(world: "World", creature_id: int) -> Any | None:
    for creature in world.creatures:
        if id(creature) == creature_id:
            return creature
    return None


# Note: _creature_by_id remains internal for module use.
# Public access is via SimBridge.creature_by_id (see class below).


def _apply_mind(creature, actions: tuple[dict, ...], mode: str) -> bool:
    mind = getattr(creature, "mind", None)
    if mind is None or not hasattr(mind, "action_defs"):
        return False
    if mode == "reset":
        mind.reset_to_base()
    elif mode == "merge":
        mind.merge_action_defs(list(actions))
    else:
        mind.set_action_defs(list(actions))
    creature.current_action = None
    return True


def _matches_species(creature, species_name: str, affiliation_id: str | None) -> bool:
    if creature.species.name != species_name:
        return False
    if affiliation_id is None:
        return True
    from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

    return get_creature_affiliation_id(creature) == affiliation_id


class SimBridge:
    """Game → Sim の唯一の命令実行窓口。"""

    def __init__(self, world: "World", *, game_hooks: dict | None = None) -> None:
        self.world = world
        self._factory = CreatureFactory()
        self._game_hooks = dict(game_hooks or {})

    def creature_by_id(self, creature_id: int) -> Any | None:
        """公開ヘルパー: creature_id で Creature を検索（Game hook から利用）。
        内部実装は _creature_by_id を使用。
        """
        return _creature_by_id(self.world, creature_id)

    def execute(self, command: SimCommand) -> SimCommandResult:
        if isinstance(command, SpawnCreature):
            return self._spawn_creature(command)
        if isinstance(command, SetCreatureMind):
            return self._set_creature_mind(command)
        if isinstance(command, SetSpeciesMind):
            return self._set_species_mind(command)
        if isinstance(command, SetAffiliationCasteMind):
            return self._dispatch_game_hook(command, "SetAffiliationCasteMind")
        if isinstance(command, EnterCreatureShelter):
            return self._dispatch_game_hook(command, "EnterCreatureShelter")
        if isinstance(command, IssueCreatureDirective):
            return self._issue_creature_directive(command)
        if isinstance(command, ClearCreatureDirective):
            return self._clear_creature_directive(command)
        if isinstance(command, PlaceSpawnEmitter):
            return self._place_spawn_emitter(command)
        if isinstance(command, SetSpawnEmitterEnabled):
            return self._set_spawn_emitter_enabled(command)
        return SimCommandResult(False, type(command).__name__, "未知の命令")

    def execute_all(self, commands: list[SimCommand]) -> list[SimCommandResult]:
        return [self.execute(cmd) for cmd in commands]

    def _spawn_creature(self, cmd: SpawnCreature) -> SimCommandResult:
        world = self.world
        parent = None
        if cmd.parent_creature_id is not None:
            parent = self.creature_by_id(cmd.parent_creature_id)

        try:
            creature = self._factory.create(
                cmd.species,
                world=world,
                x=cmd.x,
                y=cmd.y,
            )
        except Exception as exc:
            return SimCommandResult(False, "SpawnCreature", str(exc))

        cap = world.get_population_cap(cmd.species)
        if cap is not None:
            alive = sum(
                1
                for c in world.creatures
                if c.alive and c.species.name == cmd.species
            )
            if alive >= cap:
                return SimCommandResult(
                    False,
                    "SpawnCreature",
                    f"population cap reached for {cmd.species}",
                )

        world.add_creature(creature, spawn_source=cmd.source, parent=parent)
        return SimCommandResult(
            True,
            "SpawnCreature",
            creature=creature,
            creatures=[creature],
            count=1,
        )

    def _set_creature_mind(self, cmd: SetCreatureMind) -> SimCommandResult:
        creature = self.creature_by_id(cmd.creature_id)
        if creature is None:
            return SimCommandResult(
                False,
                "SetCreatureMind",
                f"creature id={cmd.creature_id} not found",
            )
        if not _apply_mind(creature, cmd.actions, cmd.mode):
            return SimCommandResult(False, "SetCreatureMind", "mind not applicable")
        return SimCommandResult(
            True,
            "SetCreatureMind",
            creature=creature,
            creatures=[creature],
            count=1,
        )

    def _set_species_mind(self, cmd: SetSpeciesMind) -> SimCommandResult:
        matched: list[Any] = []
        for creature in self.world.creatures:
            if not _matches_species(creature, cmd.species_name, cmd.affiliation_id):
                continue
            if _apply_mind(creature, cmd.actions, cmd.mode):
                matched.append(creature)
        if not matched:
            return SimCommandResult(
                False,
                "SetSpeciesMind",
                f"no creatures for species={cmd.species_name}",
            )
        return SimCommandResult(
            True,
            "SetSpeciesMind",
            creatures=matched,
            count=len(matched),
        )

    def _dispatch_game_hook(self, command: SimCommand, key: str) -> SimCommandResult:
        handler = self._game_hooks.get(key)
        if handler is None:
            return SimCommandResult(
                False,
                key,
                "game hook not registered (use game.make_sim_bridge)",
            )
        return handler(self, command)

    def _issue_creature_directive(self, cmd: IssueCreatureDirective) -> SimCommandResult:
        creature = self.creature_by_id(cmd.creature_id)
        if creature is None:
            return SimCommandResult(
                False,
                "IssueCreatureDirective",
                f"creature id={cmd.creature_id} not found",
            )
        if not getattr(creature, "alive", True):
            return SimCommandResult(
                False,
                "IssueCreatureDirective",
                "creature is not alive",
            )
        from src.sim.behavior.directive import create_directive

        try:
            directive = create_directive(
                cmd.kind,
                x=cmd.x,
                y=cmd.y,
                speed_multiplier=cmd.speed_multiplier,
                arrival_radius=cmd.arrival_radius,
            )
        except (KeyError, TypeError) as exc:
            return SimCommandResult(False, "IssueCreatureDirective", str(exc))

        creature.set_directive(directive)
        creature.current_action = None
        return SimCommandResult(
            True,
            "IssueCreatureDirective",
            creature=creature,
            creatures=[creature],
            count=1,
        )

    def _clear_creature_directive(self, cmd: ClearCreatureDirective) -> SimCommandResult:
        creature = self.creature_by_id(cmd.creature_id)
        if creature is None:
            return SimCommandResult(
                False,
                "ClearCreatureDirective",
                f"creature id={cmd.creature_id} not found",
            )
        creature.clear_directive()
        return SimCommandResult(
            True,
            "ClearCreatureDirective",
            creature=creature,
            creatures=[creature],
            count=1,
        )

    def _place_spawn_emitter(self, cmd: PlaceSpawnEmitter) -> SimCommandResult:
        from src.sim.components.spawn_capability import SpawnCapability
        from src.sim.entities.world_object import WorldObject

        ws = self.world.world_object_system
        eid = str(cmd.emitter_id)
        if ws.get(eid) is not None:
            return SimCommandResult(
                False,
                "PlaceSpawnEmitter",
                f"emitter id {eid!r} already exists",
            )
        cap = SpawnCapability.from_mapping(dict(cmd.spawn_config or {}))
        obj = WorldObject(
            id=eid,
            type_ref="spawn",
            x=float(cmd.x),
            y=float(cmd.y),
            label=str(cmd.label or cap.label or "spawn"),
            layer="spawn",
            origin="game",
            spawn=cap,
        )
        ws.objects[eid] = obj
        self.world.spawn_system.rebuild_from_world_objects()
        return SimCommandResult(True, "PlaceSpawnEmitter", count=1)

    def _set_spawn_emitter_enabled(self, cmd: SetSpawnEmitterEnabled) -> SimCommandResult:
        spawned = self.world.spawn_system.set_emitter_enabled(
            str(cmd.emitter_id), bool(cmd.enabled)
        )
        return SimCommandResult(
            True,
            "SetSpawnEmitterEnabled",
            count=int(spawned),
        )

    @staticmethod
    def random_position(world: "World", *, margin: float = 80.0) -> tuple[float, float]:
        m = float(margin)
        x = random.uniform(m, max(m, world.width - m))
        y = random.uniform(m, max(m, world.height - m))
        return x, y
