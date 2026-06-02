"""スキン画像の描画（9-slice / 伸縮 blit）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import pygame

if TYPE_CHECKING:
    from pygame_ui.skin import NineSliceSpec, UISkin
    from pygame_ui.theme import UITheme


def blit_nine_slice(
    surface,
    rect: tuple[int, int, int, int],
    spec: "NineSliceSpec",
) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0:
        return
    img = spec.surface
    L, T, R, B = spec.left, spec.top, spec.right, spec.bottom
    iw, ih = img.get_width(), img.get_height()
    if iw < L + R + 1 or ih < T + B + 1:
        scaled = pygame.transform.scale(img, (max(1, w), max(1, h)))
        surface.blit(scaled, (x, y))
        return

    cw, ch = iw - L - R, ih - T - B

    def _blit_part(sx, sy, sw, sh, dx, dy, dw, dh) -> None:
        if sw <= 0 or sh <= 0 or dw <= 0 or dh <= 0:
            return
        part = img.subsurface((sx, sy, sw, sh))
        if sw != dw or sh != dh:
            part = pygame.transform.scale(part, (dw, dh))
        surface.blit(part, (dx, dy))

    # コーナー
    _blit_part(0, 0, L, T, x, y, L, T)
    _blit_part(iw - R, 0, R, T, x + w - R, y, R, T)
    _blit_part(0, ih - B, L, B, x, y + h - B, L, B)
    _blit_part(iw - R, ih - B, R, B, x + w - R, y + h - B, R, B)
    # 辺
    _blit_part(L, 0, cw, T, x + L, y, w - L - R, T)
    _blit_part(L, ih - B, cw, B, x + L, y + h - B, w - L - R, B)
    _blit_part(0, T, L, ch, x, y + T, L, h - T - B)
    _blit_part(iw - R, T, R, ch, x + w - R, y + T, R, h - T - B)
    # 中央
    _blit_part(L, T, cw, ch, x + L, y + T, w - L - R, h - T - B)


def blit_stretched(surface, rect: tuple[int, int, int, int], image) -> None:
    x, y, w, h = rect
    if w <= 0 or h <= 0 or image is None:
        return
    if image.get_width() == w and image.get_height() == h:
        surface.blit(image, (x, y))
    else:
        surface.blit(pygame.transform.scale(image, (w, h)), (x, y))


def _skin(theme: "UITheme") -> Optional["UISkin"]:
    return getattr(theme, "skin", None)


def draw_button_skin(
    surface,
    rect: tuple[int, int, int, int],
    theme: "UITheme",
    *,
    hover: bool,
    pressed: bool,
    enabled: bool,
) -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    if not enabled:
        key = "button_disabled"
        img = skin.image(key) or skin.image("button_idle")
    elif pressed:
        key = "button_pressed"
        img = skin.image(key) or skin.image("button_idle")
    elif hover:
        key = "button_hover"
        img = skin.image(key) or skin.image("button_idle")
    else:
        key = "button_idle"
        img = skin.image(key)
    if img is None:
        return False
    blit_stretched(surface, rect, img)
    return True


def draw_panel_skin(surface, rect: tuple[int, int, int, int], theme: "UITheme") -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    spec = skin.slice_spec("panel")
    if spec is None:
        img = skin.image("panel")
        if img is None:
            return False
        blit_stretched(surface, rect, img)
        return True
    blit_nine_slice(surface, rect, spec)
    return True


def draw_checkbox_skin(
    surface,
    box_rect: tuple[int, int, int, int],
    theme: "UITheme",
    *,
    checked: bool,
    enabled: bool,
) -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    key = "checkbox_on" if checked and enabled else "checkbox_off"
    img = skin.image(key)
    if img is None:
        return False
    blit_stretched(surface, box_rect, img)
    return True


def draw_menu_skin(surface, rect: tuple[int, int, int, int], theme: "UITheme") -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    spec = skin.slice_spec("menu") or skin.slice_spec("panel")
    if spec is not None:
        blit_nine_slice(surface, rect, spec)
        return True
    img = skin.image("menu_bg") or skin.image("panel")
    if img is None:
        return False
    blit_stretched(surface, rect, img)
    return True


def draw_menu_row_skin(
    surface,
    row_rect: tuple[int, int, int, int],
    theme: "UITheme",
) -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    img = skin.image("menu_row_hover")
    if img is None:
        return False
    blit_stretched(surface, row_rect, img)
    return True


def draw_slider_track_skin(
    surface,
    track_rect: tuple[int, int, int, int],
    fill_rect: tuple[int, int, int, int] | None,
    theme: "UITheme",
) -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    spec = skin.slice_spec("slider_track")
    if spec is not None:
        blit_nine_slice(surface, track_rect, spec)
    else:
        img = skin.image("slider_track")
        if img is None:
            return False
        blit_stretched(surface, track_rect, img)
    if fill_rect and fill_rect[2] > 0:
        fill_img = skin.image("slider_fill")
        if fill_img is not None:
            blit_stretched(surface, fill_rect, fill_img)
    return True


def draw_slider_thumb_skin(
    surface,
    thumb_rect: tuple[int, int, int, int],
    theme: "UITheme",
) -> bool:
    skin = _skin(theme)
    if skin is None:
        return False
    img = skin.image("slider_thumb")
    if img is None:
        return False
    blit_stretched(surface, thumb_rect, img)
    return True
