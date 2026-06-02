"""ドメインイベントの発火ヘルパー（シミュレーション層専用）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from src.sim.events import (
    AffiliationAllAccessRemovedEvent,
    CombatStartedEvent,
    CombatTargetKind,
    DeathCause,
    DeathEvent,
    ItemFoundEvent,
    ItemKind,
    SpawnEvent,
    SpawnSource,
)

if TYPE_CHECKING:
    from src.sim.combat.target_ref import TargetRef
    from src.sim.systems.world import World


def _sim_time(world: "World") -> float:
    return float(getattr(world, "_sim_time", 0.0))


def emit_death(world: "World", creature, *, cause: DeathCause = "unknown") -> None:
    if world is None or creature is None:
        return
    world.events.emit(
        DeathEvent(
            sim_time=_sim_time(world),
            creature=creature,
            species_name=creature.species.name,
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
            item_kind=item_kind,
            amount=float(amount),
        )
    )


def _combat_key(
    attacker,
    *,
    target_creature=None,
    target_object_id: str | None = None,
) -> tuple:
    if target_creature is not None:
        return ("creature", id(attacker), id(target_creature))
    return ("world_object", id(attacker), str(target_object_id or ""))


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
            target_kind="creature",
            target_creature=target_creature,
        )
    )


def emit_combat_started_affiliation_access(
    world: "World",
    attacker,
    *,
    access_id: str,
    target_affiliation_id: Optional[str],
) -> None:
    if world is None or attacker is None or not access_id:
        return
    pairs = world._combat_pairs_this_tick
    key = _combat_key(attacker, target_object_id=str(access_id))
    if key in pairs:
        return
    pairs.add(key)
    world.events.emit(
        CombatStartedEvent(
            sim_time=_sim_time(world),
            attacker=attacker,
            attacker_species=attacker.species.name,
            target_kind="world_object",
            target_object_id=str(access_id),
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

    from src.sim.combat.target_ref import TargetKind

    if ref.kind is TargetKind.CREATURE and ref.creature is not None:
        emit_combat_started_creature(world, attacker, ref.creature)
        return

    if ref.kind is TargetKind.WORLD_OBJECT:
        access = ref.world_object
        if access is None:
            return
        emit_combat_started_affiliation_access(
            world,
            attacker,
            access_id=access.id,
            target_affiliation_id=ref.affiliation_id or access.parent_id,
        )
        return


def emit_affiliation_all_access_removed(world: "World", affiliation_id: str) -> None:
    """勢力の全アクセスポイントが破壊されたことを通知する（中立イベント）。"""
    if world is None or not affiliation_id:
        return
    world.events.emit(
        AffiliationAllAccessRemovedEvent(
            sim_time=_sim_time(world),
            affiliation_id=str(affiliation_id),
        )
    )
