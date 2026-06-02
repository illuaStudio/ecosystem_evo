"""ゲーム層が UI / Client に返すメッセージ。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.sim.systems.world import World


@dataclass
class GameMessage:
    text: str
    source: str = "game"
    priority: int = 0
    elapsed_seconds: float | None = None


def with_elapsed(
    text: str,
    world: "World | None",
    *,
    source: str = "game",
    priority: int = 0,
) -> GameMessage:
    """経過秒を付与したメッセージ（既に付いている場合は二重付与しない）。"""
    from src.game.game_time import elapsed_seconds

    sec = elapsed_seconds(world)
    body = text.strip()
    if body.startswith("[") and "s]" in body[:12]:
        return GameMessage(text=body, source=source, priority=priority, elapsed_seconds=sec)
    return GameMessage(
        text=f"[{sec:5.1f}s] {body}",
        source=source,
        priority=priority,
        elapsed_seconds=sec,
    )


def stamp_messages(messages: list[GameMessage], world: "World | None") -> list[GameMessage]:
    """既存メッセージ列に経過秒プレフィックスを付ける。"""
    if world is None:
        return messages
    out: list[GameMessage] = []
    for msg in messages:
        if msg.elapsed_seconds is not None:
            out.append(msg)
            continue
        out.append(
            with_elapsed(msg.text, world, source=msg.source, priority=msg.priority)
        )
    return out
