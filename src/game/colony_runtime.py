"""World ごとのコロニー進行ランタイム状態（敗北・ゲームイベント）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class ColonyRuntimeState:
    defeated: set[str] = field(default_factory=set)
    last_defeat_message: str = ""
    pending_events: List[object] = field(default_factory=list)

    def is_defeated(self, affiliation_id: str) -> bool:
        return str(affiliation_id) in self.defeated

    def mark_defeated(self, affiliation_id: str, message: str = "") -> None:
        self.defeated.add(str(affiliation_id))
        if message:
            self.last_defeat_message = message
