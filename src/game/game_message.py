"""ゲーム層が UI / Client に返すメッセージ。"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class GameMessage:
    text: str
    source: str = "game"
    priority: int = 0
