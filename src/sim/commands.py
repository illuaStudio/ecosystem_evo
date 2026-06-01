"""ゲーム層 → シミュレーション層への命令型。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Union

MindApplyMode = Literal["replace", "merge", "reset"]
CommandSpawnSource = Literal["game", "debug"]
ColonyCaste = Literal["worker", "soldier", "vanguard", "combat", "queen", "member"]
DirectiveKind = Literal["move_to", "warp_to"]


@dataclass(frozen=True)
class SpawnCreature:
    """指定種をスポーン。x/y 省略時はワールド内ランダム。"""

    species: str
    x: Optional[float] = None
    y: Optional[float] = None
    source: CommandSpawnSource = "game"
    parent_creature_id: Optional[int] = None


@dataclass(frozen=True)
class SetCreatureMind:
    """個体の UtilityMind actions を変更。"""

    creature_id: int
    actions: tuple[dict[str, Any], ...] = ()
    mode: MindApplyMode = "replace"


@dataclass(frozen=True)
class SetSpeciesMind:
    """種名一致の全個体（任意で colony_id 絞り）に mind を適用。"""

    species_name: str
    actions: tuple[dict[str, Any], ...] = ()
    mode: MindApplyMode = "replace"
    colony_id: Optional[str] = None


@dataclass(frozen=True)
class SetColonyCasteMind:
    """同一コロニー内の種別（働きアリ・兵隊等）全個体に mind を適用。"""

    colony_id: str
    caste: ColonyCaste
    actions: tuple[dict[str, Any], ...] = ()
    mode: MindApplyMode = "replace"


@dataclass(frozen=True)
class EnterCreatureShelter:
    """個体を巣穴 shelter 状態へ。"""

    creature_id: int


@dataclass(frozen=True)
class IssueCreatureDirective:
    """UtilityMind より優先する強制行動。"""

    creature_id: int
    kind: DirectiveKind
    x: float = 0.0
    y: float = 0.0
    speed_multiplier: float = 1.0
    arrival_radius: float = 8.0


@dataclass(frozen=True)
class ClearCreatureDirective:
    """進行中の強制行動を解除。"""

    creature_id: int


SimCommand = Union[
    SpawnCreature,
    SetCreatureMind,
    SetSpeciesMind,
    SetColonyCasteMind,
    EnterCreatureShelter,
    IssueCreatureDirective,
    ClearCreatureDirective,
]


@dataclass
class SimCommandResult:
    ok: bool
    command: str
    message: str = ""
    creature: Any = None
    creatures: list[Any] = field(default_factory=list)
    count: int = 0
