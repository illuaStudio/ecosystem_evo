"""画像の矩形へのフィット計算（ボタン以外の単純表示用）。"""
from __future__ import annotations

from enum import Enum
from typing import Literal, Optional, Tuple

AlignX = Literal["left", "center", "right"]
AlignY = Literal["top", "center", "bottom"]

DestRect = Tuple[int, int, int, int]  # x, y, w, h（描画先）


class ImageScaleMode(str, Enum):
    """画像をコントロール矩形にどう載せるか。"""

    NATIVE = "native"
    """原寸のまま。はみ出す分はクリップ（既定）。"""

    STRETCH = "stretch"
    """矩形いっぱいに伸縮（アスペクト比は無視）。"""

    FIT = "fit"
    """アスペクト比を維持して矩形内に収める（拡大・縮小とも可）。"""

    FIT_SHRINK_ONLY = "fit_shrink_only"
    """アスペクト比を維持。画像が大きいときだけ縮小（拡大しない）。"""

    FIT_GROW_ONLY = "fit_grow_only"
    """アスペクト比を維持。画像が小さいときだけ拡大（縮小しない）。"""

    COVER = "cover"
    """アスペクト比を維持して矩形を覆う（はみ出しはクリップ）。"""


def mode_allows_upscale(mode: ImageScaleMode) -> bool:
    return mode in (ImageScaleMode.STRETCH, ImageScaleMode.FIT, ImageScaleMode.FIT_GROW_ONLY, ImageScaleMode.COVER)


def mode_allows_downscale(mode: ImageScaleMode) -> bool:
    return mode in (
        ImageScaleMode.STRETCH,
        ImageScaleMode.FIT,
        ImageScaleMode.FIT_SHRINK_ONLY,
        ImageScaleMode.COVER,
    )


def mode_keeps_aspect(mode: ImageScaleMode) -> bool:
    return mode != ImageScaleMode.STRETCH


def mode_uses_cover_scale(mode: ImageScaleMode) -> bool:
    return mode == ImageScaleMode.COVER


def compute_dest_rect(
    bounds: tuple[int, int, int, int],
    image_size: tuple[int, int],
    mode: ImageScaleMode,
    *,
    align_x: AlignX = "center",
    align_y: AlignY = "center",
    allow_upscale: Optional[bool] = None,
    allow_downscale: Optional[bool] = None,
) -> Optional[DestRect]:
    """
    画像を bounds (x,y,w,h) に載せるときの描画先矩形を返す。
    画像サイズ 0 または bounds が 0 なら None。
    """
    bx, by, bw, bh = bounds
    iw, ih = image_size
    if bw <= 0 or bh <= 0 or iw <= 0 or ih <= 0:
        return None

    upscale = mode_allows_upscale(mode) if allow_upscale is None else allow_upscale
    downscale = mode_allows_downscale(mode) if allow_downscale is None else allow_downscale

    if mode == ImageScaleMode.NATIVE:
        dw, dh = iw, ih
    elif mode == ImageScaleMode.STRETCH:
        dw, dh = bw, bh
    elif mode_keeps_aspect(mode):
        sx = bw / iw
        sy = bh / ih
        scale = max(sx, sy) if mode_uses_cover_scale(mode) else min(sx, sy)
        if not upscale:
            scale = min(scale, 1.0)
        if not downscale:
            scale = max(scale, 1.0)
        dw = max(1, int(round(iw * scale)))
        dh = max(1, int(round(ih * scale)))
    else:
        dw, dh = bw, bh

    dx = _align_pos(bx, bw, dw, align_x)
    dy = _align_pos(by, bh, dh, align_y)
    return (dx, dy, dw, dh)


def _align_pos(origin: int, bound: int, size: int, align: str) -> int:
    if align in ("center", "centre"):
        return origin + (bound - size) // 2
    if align == "right" or align == "bottom":
        return origin + bound - size
    return origin


def blit_fitted(
    surface,
    image,
    bounds: tuple[int, int, int, int],
    mode: ImageScaleMode,
    *,
    align_x: AlignX = "center",
    align_y: AlignY = "center",
    allow_upscale: Optional[bool] = None,
    allow_downscale: Optional[bool] = None,
    clip: bool = True,
    background: Optional[tuple[int, int, int] | tuple[int, int, int, int]] = None,
) -> bool:
    """bounds 内に image を描画。成功したら True。"""
    import pygame

    if image is None:
        return False
    x, y, w, h = bounds
    if w <= 0 or h <= 0:
        return False

    if background is not None:
        if len(background) == 4:
            fill = pygame.Surface((w, h), pygame.SRCALPHA)
            fill.fill(background)
            surface.blit(fill, (x, y))
        else:
            pygame.draw.rect(surface, background[:3], (x, y, w, h))

    dest = compute_dest_rect(
        bounds,
        (image.get_width(), image.get_height()),
        mode,
        align_x=align_x,
        align_y=align_y,
        allow_upscale=allow_upscale,
        allow_downscale=allow_downscale,
    )
    if dest is None:
        return False

    dx, dy, dw, dh = dest
    iw, ih = image.get_width(), image.get_height()
    if dw == iw and dh == ih:
        scaled = image
    else:
        scaled = pygame.transform.scale(image, (dw, dh))

    old_clip = surface.get_clip()
    try:
        if clip:
            surface.set_clip(pygame.Rect(x, y, w, h))
        surface.blit(scaled, (dx, dy))
    finally:
        surface.set_clip(old_clip)
    return True
