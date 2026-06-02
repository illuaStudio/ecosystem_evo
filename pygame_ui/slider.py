"""水平スライダー（0.0 .. 1.0）。"""
from __future__ import annotations

from typing import Callable, Optional

import pygame

from pygame_ui.base import Rect
from pygame_ui.draw import fill_round_rect
from pygame_ui.theme import UITheme

THUMB_W = 14


class Slider:
    def __init__(
        self,
        rect: Rect | tuple[int, int, int, int],
        *,
        value: float = 0.5,
        on_change: Optional[Callable[[float], None]] = None,
        enabled: bool = True,
        visible: bool = True,
    ) -> None:
        if isinstance(rect, tuple):
            rect = Rect(*rect)
        self._rect = rect
        self.value = max(0.0, min(1.0, float(value)))
        self.on_change = on_change
        self.enabled = enabled
        self.visible = visible
        self._dragging = False

    @property
    def rect(self) -> Rect:
        return self._rect

    def _track_rect(self) -> tuple[int, int, int, int]:
        r = self._rect
        h = min(8, max(4, r.h // 3))
        ty = r.y + (r.h - h) // 2
        return (r.x, ty, r.w, h)

    def _thumb_x(self) -> int:
        x, _y, w, _h = self._track_rect()
        inner = max(1, w - THUMB_W)
        return x + int(self.value * inner)

    def _set_from_pos(self, px: int) -> None:
        x, _y, w, _h = self._track_rect()
        inner = max(1, w - THUMB_W)
        self.value = max(0.0, min(1.0, (px - x - THUMB_W // 2) / inner))
        if self.on_change:
            self.on_change(self.value)

    def draw(self, surface, theme: UITheme) -> None:
        if not self.visible:
            return
        from pygame_ui.skin_draw import draw_slider_thumb_skin, draw_slider_track_skin

        track = self._track_rect()
        fill_w = int(track[2] * self.value)
        fill_rect = (
            (track[0], track[1], fill_w, track[3]) if fill_w > 0 else None
        )
        if not draw_slider_track_skin(surface, track, fill_rect, theme):
            fill_round_rect(surface, track, theme.slider_track, radius=4)
            if fill_rect:
                fill_round_rect(
                    surface,
                    fill_rect,
                    theme.slider_fill if self.enabled else theme.text_disabled,
                    radius=4,
                )
        tx = self._thumb_x()
        thumb_rect = (tx, self._rect.y + 2, THUMB_W, self._rect.h - 4)
        if not draw_slider_thumb_skin(surface, thumb_rect, theme):
            fill_round_rect(
                surface,
                thumb_rect,
                theme.slider_thumb if self.enabled else theme.text_disabled,
                radius=6,
            )

    def handle_event(self, event, theme: UITheme) -> bool:
        if not self.visible or not self.enabled:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._rect.contains(*event.pos):
                self._dragging = True
                self._set_from_pos(event.pos[0])
                return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self._dragging:
                self._dragging = False
                return True
        if event.type == pygame.MOUSEMOTION and self._dragging:
            self._set_from_pos(event.pos[0])
            return True
        return False
