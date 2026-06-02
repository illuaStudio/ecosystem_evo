"""チェックボックス（トグル）。"""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from pygame_ui.base import Rect
from pygame_ui.draw import draw_widget_frame, fill_round_rect
from pygame_ui.fonts import truncate_text
from pygame_ui.theme import UITheme

BOX_SIZE = 18


class Checkbox:
    def __init__(
        self,
        rect: Rect | tuple[int, int, int, int],
        label: str,
        *,
        checked: bool = False,
        on_change: Optional[Callable[[bool], None]] = None,
        enabled: bool = True,
        visible: bool = True,
    ) -> None:
        if isinstance(rect, tuple):
            rect = Rect(*rect)
        self._rect = rect
        self.label = str(label)
        self.checked = bool(checked)
        self.on_change = on_change
        self.enabled = enabled
        self.visible = visible
        self._hover = False

    @property
    def rect(self) -> Rect:
        return self._rect

    def _box_rect(self) -> Rect:
        return Rect(self._rect.x, self._rect.y + (self._rect.h - BOX_SIZE) // 2, BOX_SIZE, BOX_SIZE)

    def draw(self, surface, theme: UITheme) -> None:
        if not self.visible:
            return
        box = self._box_rect()
        text_color = theme.text_color if self.enabled else theme.text_disabled
        from pygame_ui.skin_draw import draw_checkbox_skin

        if not draw_checkbox_skin(
            surface,
            (box.x, box.y, box.w, box.h),
            theme,
            checked=self.checked,
            enabled=self.enabled,
        ):
            border = theme.checkbox_on if self.checked else theme.checkbox_border
            draw_widget_frame(
                surface,
                (box.x, box.y, box.w, box.h),
                theme,
                fill=theme.checkbox_fill if self.checked and self.enabled else theme.checkbox_bg,
                border=border,
            )
        if self.checked and self.enabled and not getattr(theme, "skin", None):
            if theme.pixel_style and not getattr(theme, "skin", None):
                inner = 4
                cx = box.x + (box.w - inner) // 2
                cy = box.y + (box.h - inner) // 2
                fill_round_rect(
                    surface,
                    (cx, cy, inner, inner),
                    theme.checkbox_fill,
                    radius=0,
                )
            else:
                font = theme.font(theme.font_size_small)
                mark = font.render("✓", True, theme.checkbox_on)
                surface.blit(
                    mark,
                    (
                        box.x + (box.w - mark.get_width()) // 2,
                        box.y + (box.h - mark.get_height()) // 2 - 1,
                    ),
                )
        font = theme.font()
        label_x = box.x + box.w + theme.padding
        max_w = max(0, self._rect.w - (label_x - self._rect.x))
        text = truncate_text(self.label, font, max_w)
        surf = font.render(text, True, text_color)
        surface.blit(surf, (label_x, self._rect.y + (self._rect.h - surf.get_height()) // 2))

    def handle_event(self, event, theme: UITheme) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEMOTION:
            self._hover = self._rect.contains(*event.pos)
            return self._hover
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._rect.contains(*event.pos):
                self.checked = not self.checked
                if self.on_change:
                    self.on_change(self.checked)
                return True
        return False
