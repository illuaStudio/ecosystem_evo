"""簡易レイアウト（縦積み）。"""
from __future__ import annotations

from typing import List

from pygame_ui.base import Rect, Widget
from pygame_ui.theme import UITheme


class VBox:
    """子ウィジェットを縦に並べる（各 child は set_rect / _rect を持つ想定）。"""

    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        *,
        spacing: int = 6,
    ) -> None:
        self.x = x
        self.y = y
        self.width = width
        self.spacing = spacing
        self.children: List[Widget] = []

    def add(self, widget: Widget, height: int) -> Widget:
        if self.children:
            last = self.children[-1]
            y = last.rect.y + last.rect.h + self.spacing
        else:
            y = self.y
        if hasattr(widget, "set_rect"):
            widget.set_rect(Rect(self.x, y, self.width, height))
        elif hasattr(widget, "_rect"):
            widget._rect = Rect(self.x, y, self.width, height)
        self.children.append(widget)
        return widget

    def total_height(self) -> int:
        if not self.children:
            return 0
        last = self.children[-1]
        return last.rect.y + last.rect.h - self.y

    def place_in_panel(self, panel, theme: UITheme, *, start_y: int | None = None) -> None:
        """Panel の content 領域に子を配置。"""
        y = start_y if start_y is not None else panel.content_top(theme)
        self.y = y
        for i, child in enumerate(self.children):
            if i > 0:
                y = self.children[i - 1].rect.y + self.children[i - 1].rect.h + self.spacing
            if hasattr(child, "set_rect"):
                child.set_rect(Rect(self.x, y, self.width, child.rect.h))
            elif hasattr(child, "_rect"):
                child._rect = Rect(self.x, y, self.width, child.rect.h)
            panel.add_child(child)
