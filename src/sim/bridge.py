"""シミュレーション層: ゲーム層からの命令実行窓口。"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING, Any

from src.sim.commands import (
    ClearCreatureDirective,
    EnterCreatureShelter,
    IssueCreatureDirective,
    SetColonyCasteMind,
    SetCreatureMind,
    SetSpeciesMind,
    SimCommand,
    SimCommandResult,
    SpawnCreature,
)
from src.sim.utils.caste_helpers import creature_matches_colony_caste, normalize_caste
from src.sim.entities.creature_factory import CreatureFactory

if TYPE_CHECKING:
    from src.sim.systems.world import World


def _creature_by_id(world: "World", creature_id: int) -> Any | None:
    for creature in world.creatures:
        if id(creature) == creature_id:
            return creature
    return None


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


def _matches_species(creature, species_name: str, colony_id: str | None) -> bool:
    if creature.species.name != species_name:
        return False
    if colony_id is None:
        return True
    from src.sim.utils.colony_helpers import get_creature_colony_id

    return get_creature_colony_id(creature) == colony_id


class SimBridge:
    """Game → Sim の唯一の命令実行窓口。"""

    def __init__(self, world: "World") -> None:
        self.world = world
        self._factory = CreatureFactory()

    def execute(self, command: SimCommand) -> SimCommandResult:
        if isinstance(command, SpawnCreature):
            return self._spawn_creature(command)
        if isinstance(command, SetCreatureMind):
            return self._set_creature_mind(command)
        if isinstance(command, SetSpeciesMind):
            return self._set_species_mind(command)
        if isinstance(command, SetColonyCasteMind):
            return self._set_colony_caste_mind(command)
        if isinstance(command, EnterCreatureShelter):
            return self._enter_creature_shelter(command)
        if isinstance(command, IssueCreatureDirective):
            return self._issue_creature_directive(command)
        if isinstance(command, ClearCreatureDirective):
            return self._clear_creature_directive(command)
        return SimCommandResult(False, type(command).__name__, "未知の命令")

    def execute_all(self, commands: list[SimCommand]) -> list[SimCommandResult]:
        return [self.execute(cmd) for cmd in commands]

    def _spawn_creature(self, cmd: SpawnCreature) -> SimCommandResult:
        world = self.world
        parent = None
        if cmd.parent_creature_id is not None:
            parent = _creature_by_id(world, cmd.parent_creature_id)

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
        creature = _creature_by_id(self.world, cmd.creature_id)
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
            if not _matches_species(creature, cmd.species_name, cmd.colony_id):
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

    def _set_colony_caste_mind(self, cmd: SetColonyCasteMind) -> SimCommandResult:
        caste = normalize_caste(cmd.caste) if isinstance(cmd.caste, str) else cmd.caste
        if caste is None:
            return SimCommandResult(
                False,
                "SetColonyCasteMind",
                f"unknown caste={cmd.caste!r}",
            )

        matched: list[Any] = []
        for creature in self.world.creatures:
            if not creature_matches_colony_caste(creature, cmd.colony_id, caste):
                continue
            if _apply_mind(creature, cmd.actions, cmd.mode):
                matched.append(creature)
        if not matched:
            return SimCommandResult(
                False,
                "SetColonyCasteMind",
                f"no creatures for colony={cmd.colony_id} caste={caste}",
            )
        return SimCommandResult(
            True,
            "SetColonyCasteMind",
            creatures=matched,
            count=len(matched),
        )

    def _enter_creature_shelter(self, cmd: EnterCreatureShelter) -> SimCommandResult:
        creature = _creature_by_id(self.world, cmd.creature_id)
        if creature is None:
            return SimCommandResult(
                False,
                "EnterCreatureShelter",
                f"creature id={cmd.creature_id} not found",
            )
        from src.sim.shelter.helpers import enter_creature_shelter, resolve_nest_shelter

        ref = resolve_nest_shelter(creature)
        if ref is None:
            return SimCommandResult(False, "EnterCreatureShelter", "no nest shelter")
        creature.position.x = ref.x
        creature.position.y = ref.y
        creature.pos[0] = ref.x
        creature.pos[1] = ref.y
        enter_creature_shelter(creature, ref)
        return SimCommandResult(
            True,
            "EnterCreatureShelter",
            creature=creature,
            creatures=[creature],
            count=1,
        )

    def _issue_creature_directive(self, cmd: IssueCreatureDirective) -> SimCommandResult:
        creature = _creature_by_id(self.world, cmd.creature_id)
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
        creature = _creature_by_id(self.world, cmd.creature_id)
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

    @staticmethod
    def random_position(world: "World", *, margin: float = 80.0) -> tuple[float, float]:
        m = float(margin)
        x = random.uniform(m, max(m, world.width - m))
        y = random.uniform(m, max(m, world.height - m))
        return x, y
