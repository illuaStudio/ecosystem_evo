"""画面上のゲームメッセージ履歴（Client 層）。"""
from __future__ import annotations

from dataclasses import dataclass

from src.game.game_message import GameMessage

SOURCE_COLORS: dict[str, tuple[int, int, int]] = {
    "progression": (255, 220, 120),
    "event": (180, 240, 200),
    "monitor": (160, 200, 255),
    "game": (230, 230, 230),
}


@dataclass(frozen=True)
class FeedEntry:
    text: str
    source: str = "game"
    priority: int = 0

    @property
    def color(self) -> tuple[int, int, int]:
        return SOURCE_COLORS.get(self.source, SOURCE_COLORS["game"])


class GameMessageFeed:
    """直近のゲームメッセージを保持（新しい順）。"""

    MAX_ENTRIES = 8

    def __init__(self) -> None:
        self._entries: list[FeedEntry] = []

    def clear(self) -> None:
        self._entries.clear()

    def push(self, messages: list[GameMessage]) -> None:
        if not messages:
            return
        ordered = sorted(messages, key=lambda m: m.priority, reverse=True)
        for msg in reversed(ordered):
            if not msg.text:
                continue
            self._add(FeedEntry(text=msg.text, source=msg.source, priority=msg.priority))

    def push_text(self, text: str, *, source: str = "game", priority: int = 0) -> None:
        if not text:
            return
        self._add(FeedEntry(text=text, source=source, priority=priority))

    def _add(self, entry: FeedEntry) -> None:
        self._entries = [e for e in self._entries if e.text != entry.text]
        self._entries.insert(0, entry)
        self._entries = self._entries[: self.MAX_ENTRIES]

    def entries(self) -> list[FeedEntry]:
        return list(self._entries)
