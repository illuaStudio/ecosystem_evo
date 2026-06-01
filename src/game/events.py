"""ゲーム層イベント（Sim 事実の解釈・進行）。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GameEvent:
    sim_time: float = 0.0


@dataclass(frozen=True, kw_only=True)
class AffiliationDefeatedEvent(GameEvent):
    affiliation_id: str = ""
    message: str = ""
