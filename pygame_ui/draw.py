"""共通描画ヘルパ。"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from pygame_ui.theme import Color, ColorA

if TYPE_CHECKING:
    from pygame_ui.theme import UITheme


def fill_round_rect(
    surface,
    rect: tuple[int, int, int, int],
    color: Color | ColorA,
    *,
    radius: int = 0,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    r = max(0, min(radius, min(w, h) // 2))
    if len(color) == 4:
        patch = pygame.Surface((w, h), pygame.SRCALPHA)
        _blit_round_rect(patch, (0, 0, w, h), color, radius=r)
        surface.blit(patch, (x, y))
    else:
        _blit_round_rect(surface, (x, y, w, h), color, radius=r)


def _blit_round_rect(surface, rect, color, *, radius: int) -> None:
    x, y, w, h = rect
    r = radius
    if r <= 0:
        pygame.draw.rect(surface, color, rect)
        return
    pygame.draw.rect(surface, color, (x + r, y, w - 2 * r, h))
    pygame.draw.rect(surface, color, (x, y + r, w, h - 2 * r))
    pygame.draw.circle(surface, color, (x + r, y + r), r)
    pygame.draw.circle(surface, color, (x + w - r - 1, y + r), r)
    pygame.draw.circle(surface, color, (x + r, y + h - r - 1), r)
    pygame.draw.circle(surface, color, (x + w - r - 1, y + h - r - 1), r)


def stroke_round_rect(
    surface,
    rect: tuple[int, int, int, int],
    color: Color,
    *,
    radius: int = 0,
    width: int = 1,
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    pygame.draw.rect(surface, color, (x, y, w, h), width, border_radius=max(0, radius))


def stroke_bevel_rect(
    surface,
    rect: tuple[int, int, int, int],
    *,
    light: Color,
    shadow: Color,
    inset: bool = False,
) -> None:
    """ドット絵風の 2 色ベベル枠（radius=0 向け）。"""
    x, y, w, h = rect
    if w < 4 or h < 4:
        return
    hi, lo = (shadow, light) if inset else (light, shadow)
    pygame.draw.rect(surface, lo, (x, y, w, h), 2)
    pygame.draw.line(surface, hi, (x + 2, y + 2), (x + w - 3, y + 2))
    pygame.draw.line(surface, hi, (x + 2, y + 2), (x + 2, y + h - 3))
    pygame.draw.line(surface, lo, (x + 2, y + h - 3), (x + w - 3, y + h - 3))
    pygame.draw.line(surface, lo, (x + w - 3, y + 2), (x + w - 3, y + h - 3))


def draw_widget_frame(
    surface,
    rect: tuple[int, int, int, int],
    theme: "UITheme",
    *,
    fill: Color | ColorA,
    border: Color | None = None,
    pressed: bool = False,
    skin_role: str | None = None,
    skin_hover: bool = False,
    skin_enabled: bool = True,
) -> None:
    """テーマに応じてスキン画像またはベクター描画。"""
    if skin_role == "button":
        from pygame_ui.skin_draw import draw_button_skin

        if draw_button_skin(
            surface,
            rect,
            theme,
            hover=skin_hover,
            pressed=pressed,
            enabled=skin_enabled,
        ):
            return
    elif skin_role == "panel":
        from pygame_ui.skin_draw import draw_panel_skin

        if draw_panel_skin(surface, rect, theme):
            return

    fill_round_rect(surface, rect, fill, radius=theme.radius)
    if getattr(theme, "pixel_style", False):
        stroke_bevel_rect(
            surface,
            rect,
            light=theme.bevel_light,
            shadow=theme.bevel_shadow,
            inset=pressed,
        )
    elif border is not None:
        stroke_round_rect(
            surface,
            rect,
            border,
            radius=theme.radius,
            width=max(1, int(getattr(theme, "border_width", 1))),
        )
