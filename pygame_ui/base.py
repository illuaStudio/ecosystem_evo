"""ウィジェット基底とルートコンテナ。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Protocol, runtime_checkable

from pygame_ui.theme import UITheme


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    w: int
    h: int

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.x + self.w and self.y <= py < self.y + self.h

    def move(self, dx: int, dy: int) -> "Rect":
        return Rect(self.x + dx, self.y + dy, self.w, self.h)


@runtime_checkable
class Widget(Protocol):
    visible: bool
    enabled: bool

    @property
    def rect(self) -> Rect: ...

    def draw(self, surface, theme: UITheme) -> None: ...

    def handle_event(self, event, theme: UITheme) -> bool: ...


class UIRoot:
    """画面上のウィジェット木のルート（イベントは後から追加したものを優先）。"""

    def __init__(self, theme: UITheme | None = None) -> None:
        self.theme = theme or UITheme.from_defaults()
        self.theme.ensure_font_cache()
        self._widgets: List[Widget] = []
        self._overlay: List[Widget] = []

    def set_theme(self, theme: UITheme) -> None:
        """実行中に見た目プリセットを切り替え（デモ・設定画面向け）。"""
        self.theme = theme
        self.theme.ensure_font_cache()

    def add(self, widget: Widget) -> Widget:
        self._widgets.append(widget)
        return widget

    def add_overlay(self, widget: Widget) -> Widget:
        """コンテキストメニューなど最前面用。"""
        self._overlay.append(widget)
        return widget

    def remove(self, widget: Widget) -> None:
        if widget in self._widgets:
            self._widgets.remove(widget)
        if widget in self._overlay:
            self._overlay.remove(widget)

    def clear(self) -> None:
        self._widgets.clear()
        self._overlay.clear()

    def all_widgets(self) -> List[Widget]:
        return list(self._widgets) + list(self._overlay)

    def handle_event(self, event) -> bool:
        for group in (self._overlay, self._widgets):
            for widget in reversed(group):
                if not getattr(widget, "visible", True):
                    continue
                if widget.handle_event(event, self.theme):
                    return True
        return False

    def draw(self, surface) -> None:
        for widget in self._widgets:
            if getattr(widget, "visible", True):
                widget.draw(surface, self.theme)
        for widget in self._overlay:
            if getattr(widget, "visible", True):
                widget.draw(surface, self.theme)

    def hit_test(self, pos: tuple[int, int]) -> Optional[Widget]:
        px, py = pos
        for group in (self._overlay, self._widgets):
            for widget in reversed(group):
                if not getattr(widget, "visible", True):
                    continue
                if widget.rect.contains(px, py):
                    return widget
        return None
