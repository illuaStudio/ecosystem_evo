"""右クリック用コンテキストメニュー。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

import pygame

from pygame_ui.base import Rect
from pygame_ui.draw import draw_widget_frame, fill_round_rect
from pygame_ui.fonts import truncate_text
from pygame_ui.theme import UITheme

ROW_H = 28


@dataclass(frozen=True)
class ContextMenuItem:
    action_id: str
    label: str
    enabled: bool = True


class ContextMenu:
    def __init__(
        self,
        *,
        items: Optional[List[ContextMenuItem]] = None,
        on_select: Optional[Callable[[str], None]] = None,
        min_width: int = 160,
    ) -> None:
        self.items: List[ContextMenuItem] = list(items or [])
        self.on_select = on_select
        self.min_width = min_width
        self.visible = False
        self.enabled = True
        self._rect = Rect(0, 0, 0, 0)
        self._hover_index: int = -1

    @property
    def rect(self) -> Rect:
        return self._rect

    def set_items(self, items: List[ContextMenuItem]) -> None:
        self.items = list(items)

    def show(self, x: int, y: int, theme: UITheme) -> None:
        if not self.items:
            self.visible = False
            return
        font = theme.font()
        w = self.min_width
        for item in self.items:
            w = max(w, font.size(item.label)[0] + theme.padding * 2)
        h = ROW_H * len(self.items) + theme.padding
        self._rect = Rect(int(x), int(y), int(w), int(h))
        self.visible = True
        self._hover_index = -1

    def hide(self) -> None:
        self.visible = False
        self._hover_index = -1

    def draw(self, surface, theme: UITheme) -> None:
        if not self.visible or not self.items:
            return
        r = self._rect
        from pygame_ui.skin_draw import draw_menu_skin, draw_menu_row_skin

        if not draw_menu_skin(surface, (r.x, r.y, r.w, r.h), theme):
            draw_widget_frame(
                surface,
                (r.x, r.y, r.w, r.h),
                theme,
                fill=theme.menu_bg,
                border=theme.menu_border,
                skin_role="panel",
            )
        font = theme.font()
        pad = theme.padding // 2
        for i, item in enumerate(self.items):
            row_y = r.y + pad + i * ROW_H
            row_rect = (r.x + 2, row_y, r.w - 4, ROW_H - 2)
            if i == self._hover_index and item.enabled:
                if not draw_menu_row_skin(surface, row_rect, theme):
                    fill_round_rect(
                        surface,
                        row_rect,
                        theme.menu_hover,
                        radius=0 if theme.pixel_style else 3,
                    )
            color = theme.text_color if item.enabled else theme.text_disabled
            text = truncate_text(item.label, font, r.w - theme.padding * 2)
            surf = font.render(text, True, color)
            surface.blit(surf, (r.x + theme.padding, row_y + (ROW_H - surf.get_height()) // 2))

    def handle_event(self, event, theme: UITheme) -> bool:
        if not self.visible:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover_index = self._index_at(event.pos[0], event.pos[1])
            return self._rect.contains(*event.pos)
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if not self._rect.contains(*event.pos):
                self.hide()
                return False
            idx = self._index_at(*event.pos)
            if 0 <= idx < len(self.items):
                item = self.items[idx]
                if item.enabled and self.on_select:
                    self.on_select(item.action_id)
                self.hide()
                return True
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.hide()
            return True
        return self._rect.contains(
            getattr(event, "pos", (-1, -1))[0],
            getattr(event, "pos", (-1, -1))[1],
        )

    def _index_at(self, px: int, py: int) -> int:
        if not self._rect.contains(px, py):
            return -1
        pad = 4
        rel = py - self._rect.y - pad
        if rel < 0:
            return -1
        return rel // ROW_H
