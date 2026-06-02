"""生態系シミュレーション層のドメインイベント型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional

DeathCause = Literal["hp", "lifespan", "metabolism", "defeat", "unknown"]
SpawnSource = Literal["initial", "reproduction", "spawn", "game", "debug"]
CombatTargetKind = Literal["creature", "world_object"]
ItemKind = Literal["biomass"]


@dataclass(frozen=True, kw_only=True)
class SimEvent:
    """全シミュイベント共通の基底。"""

    sim_time: float = 0.0


@dataclass(frozen=True, kw_only=True)
class DeathEvent(SimEvent):
    creature: Any = field(repr=False)
    species_name: str = ""
    cause: DeathCause = "unknown"


@dataclass(frozen=True, kw_only=True)
class SpawnEvent(SimEvent):
    creature: Any = field(repr=False)
    species_name: str = ""
    source: SpawnSource = "spawn"
    parent: Any = field(default=None, repr=False)


@dataclass(frozen=True, kw_only=True)
class ItemFoundEvent(SimEvent):
    carrier: Any = field(repr=False)
    species_name: str = ""
    item_kind: ItemKind = "biomass"
    amount: float = 0.0


@dataclass(frozen=True, kw_only=True)
class CombatStartedEvent(SimEvent):
    attacker: Any = field(repr=False)
    attacker_species: str = ""
    target_kind: CombatTargetKind = "creature"
    target_creature: Any = field(default=None, repr=False)
    target_object_id: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class AffiliationAllAccessRemovedEvent(SimEvent):
    """Sim層で中立に発火するイベント: ある勢力のアクセスポイント（接続点）が全て破壊された。"""

    affiliation_id: str = ""
