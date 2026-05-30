"""シミュレーション層のイベントキュー。"""
from __future__ import annotations

from typing import Callable, List

from src.sim.events import SimEvent

EventHandler = Callable[[SimEvent], None]


class EventBus:
    """事実の発生を記録し、購読者へ通知する薄いバス。"""

    def __init__(self) -> None:
        self._queue: List[SimEvent] = []
        self._subscribers: List[EventHandler] = []

    def emit(self, event: SimEvent) -> None:
        self._queue.append(event)
        for handler in self._subscribers:
            handler(event)

    def drain(self) -> List[SimEvent]:
        events = list(self._queue)
        self._queue.clear()
        return events

    def subscribe(self, handler: EventHandler) -> None:
        self._subscribers.append(handler)

    def clear(self) -> None:
        self._queue.clear()
