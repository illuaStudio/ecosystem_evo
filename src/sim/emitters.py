"""ドメインイベントの発火ヘルパー（シミュレーション層専用）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from src.sim.events import (
    CombatStartedEvent,
    ColonyDefeatedEvent,
    CombatTargetKind,
    DeathCause,
    DeathEvent,
    ItemFoundEvent,
    ItemKind,
    SpawnEvent,
    SpawnSource,
)

if TYPE_CHECKING:
    from src.combat.target_ref import TargetRef
    from src.systems.world import World


def _sim_time(world: "World") -> float:
    ns = getattr(world, "nest_system", None)
    if ns is not None:
        return float(getattr(ns, "_sim_time", 0.0))
    return 0.0


def _colony_id(creature) -> Optional[str]:
    from src.utils.colony_helpers import get_creature_colony_id

    return get_creature_colony_id(creature)


def emit_death(world: "World", creature, *, cause: DeathCause = "unknown") -> None:
    if world is None or creature is None:
        return
    world.events.emit(
        DeathEvent(
            sim_time=_sim_time(world),
            creature=creature,
            species_name=creature.species.name,
            colony_id=_colony_id(creature),
            cause=cause,
        )
    )


def emit_spawn(
    world: "World",
    creature,
    *,
    source: SpawnSource = "spawn",
    parent=None,
) -> None:
    if world is None or creature is None:
        return
    world.events.emit(
        SpawnEvent(
            sim_time=_sim_time(world),
            creature=creature,
            species_name=creature.species.name,
            colony_id=_colony_id(creature),
            source=source,
            parent=parent,
        )
    )


def emit_item_found(
    world: "World",
    carrier,
    *,
    item_kind: ItemKind = "biomass",
    amount: float,
) -> None:
    if world is None or carrier is None or amount <= 0:
        return
    world.events.emit(
        ItemFoundEvent(
            sim_time=_sim_time(world),
            carrier=carrier,
            species_name=carrier.species.name,
            colony_id=_colony_id(carrier),
            item_kind=item_kind,
            amount=float(amount),
        )
    )


def _combat_key(attacker, *, target_creature=None, nest_id=None, hole_index=None) -> tuple:
    if target_creature is not None:
        return ("creature", id(attacker), id(target_creature))
    return ("spawn_node", id(attacker), nest_id, hole_index)


def emit_combat_started_creature(world: "World", attacker, target_creature) -> None:
    if world is None or attacker is None or target_creature is None:
        return
    pairs = world._combat_pairs_this_tick
    key = _combat_key(attacker, target_creature=target_creature)
    if key in pairs:
        return
    pairs.add(key)
    world.events.emit(
        CombatStartedEvent(
            sim_time=_sim_time(world),
            attacker=attacker,
            attacker_species=attacker.species.name,
            attacker_colony_id=_colony_id(attacker),
            target_kind="creature",
            target_creature=target_creature,
            target_colony_id=_colony_id(target_creature),
        )
    )


def emit_combat_started_spawn_node(
    world: "World",
    attacker,
    *,
    nest_id: int,
    hole_index: int,
    target_colony_id: Optional[str],
) -> None:
    if world is None or attacker is None:
        return
    pairs = world._combat_pairs_this_tick
    key = _combat_key(attacker, nest_id=nest_id, hole_index=hole_index)
    if key in pairs:
        return
    pairs.add(key)
    world.events.emit(
        CombatStartedEvent(
            sim_time=_sim_time(world),
            attacker=attacker,
            attacker_species=attacker.species.name,
            attacker_colony_id=_colony_id(attacker),
            target_kind="spawn_node",
            target_colony_id=target_colony_id,
            target_nest_id=nest_id,
            target_hole_index=hole_index,
        )
    )


def emit_colony_defeated(world: "World", colony_id: str, message: str) -> None:
    if world is None or not colony_id:
        return
    world.events.emit(
        ColonyDefeatedEvent(
            sim_time=_sim_time(world),
            colony_id=str(colony_id),
            message=message,
        )
    )


def maybe_emit_combat_from_damage(
    world: "World",
    attacker,
    ref: "TargetRef",
    dealt: float,
) -> None:
    """与ダメージが発生したとき、戦闘開始イベントを1回だけ発火。"""
    if world is None or attacker is None or dealt <= 0 or ref is None:
        return

    from src.combat.target_ref import TargetKind

    if ref.kind is TargetKind.CREATURE and ref.creature is not None:
        emit_combat_started_creature(world, attacker, ref.creature)
        return

    if ref.kind is TargetKind.SPAWN_NODE and ref.nest is not None:
        hole_index = None
        holes = ref.nest.holes or []
        if ref.hole is not None and ref.hole in holes:
            hole_index = holes.index(ref.hole)
        emit_combat_started_spawn_node(
            world,
            attacker,
            nest_id=ref.nest.id,
            hole_index=hole_index if hole_index is not None else -1,
            target_colony_id=ref.nest.colony_id,
        )
