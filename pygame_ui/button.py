"""ボタン。"""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from pygame_ui.base import Rect
from pygame_ui.draw import draw_widget_frame
from pygame_ui.fonts import truncate_text
from pygame_ui.theme import UITheme


class Button:
    def __init__(
        self,
        rect: Rect | tuple[int, int, int, int],
        label: str,
        *,
        on_click: Optional[Callable[[], None]] = None,
        enabled: bool = True,
        visible: bool = True,
    ) -> None:
        if isinstance(rect, tuple):
            rect = Rect(*rect)
        self._rect = rect
        self.label = str(label)
        self.on_click = on_click
        self.enabled = enabled
        self.visible = visible
        self._hover = False
        self._pressed = False

    @property
    def rect(self) -> Rect:
        return self._rect

    def set_rect(self, rect: Rect | tuple[int, int, int, int]) -> None:
        self._rect = Rect(*rect) if isinstance(rect, tuple) else rect

    def draw(self, surface, theme: UITheme) -> None:
        if not self.visible:
            return
        r = self._rect
        if not self.enabled:
            bg = theme.button_bg
            border = theme.text_disabled
            text_color = theme.text_disabled
        elif self._pressed:
            bg = theme.button_bg_pressed
            border = theme.button_border
            text_color = theme.text_color
        elif self._hover:
            bg = theme.button_bg_hover
            border = theme.button_border
            text_color = theme.text_color
        else:
            bg = theme.button_bg
            border = theme.button_border
            text_color = theme.text_color

        draw_widget_frame(
            surface,
            (r.x, r.y, r.w, r.h),
            theme,
            fill=bg,
            border=border,
            pressed=self._pressed,
            skin_role="button",
            skin_hover=self._hover,
            skin_enabled=self.enabled,
        )
        font = theme.font()
        inner = max(4, r.w - theme.padding * 2)
        text = truncate_text(self.label, font, inner)
        surf = font.render(text, True, text_color)
        tx = r.x + (r.w - surf.get_width()) // 2
        ty = r.y + (r.h - surf.get_height()) // 2
        surface.blit(surf, (tx, ty))

    def handle_event(self, event, theme: UITheme) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._rect.contains(*event.pos)
            return self._hover
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._pressed and self._rect.contains(*event.pos):
                self._pressed = False
                if self.on_click:
                    self.on_click()
                return True
            self._pressed = False
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._rect.contains(*event.pos):
                self._pressed = True
                return True
        return False
