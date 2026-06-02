"""ボタンではない単純な画像表示コントロール。"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from pygame_ui.base import Rect
from pygame_ui.image_fit import AlignX, AlignY, ImageScaleMode, blit_fitted
from pygame_ui.theme import UITheme

Color = Tuple[int, int, int]
ColorA = Tuple[int, int, int, int]


class ImageView:
    """
    矩形内に画像を表示する（クリック等なし）。

    scale_mode で伸縮・原寸・アスペクト維持を切り替え。
    allow_upscale / allow_downscale を指定するとモード既定より優先される。
    """

    def __init__(
        self,
        rect: Rect | tuple[int, int, int, int],
        image=None,
        *,
        image_path: str | Path | None = None,
        scale_mode: ImageScaleMode | str = ImageScaleMode.FIT_SHRINK_ONLY,
        allow_upscale: Optional[bool] = None,
        allow_downscale: Optional[bool] = None,
        align_x: AlignX = "center",
        align_y: AlignY = "center",
        background: Color | ColorA | None = None,
        clip: bool = True,
        visible: bool = True,
    ) -> None:
        if isinstance(rect, tuple):
            rect = Rect(*rect)
        self._rect = rect
        self.image = image
        if image_path is not None:
            self.load_path(image_path)
        if isinstance(scale_mode, str):
            scale_mode = ImageScaleMode(scale_mode)
        self.scale_mode = scale_mode
        self.allow_upscale = allow_upscale
        self.allow_downscale = allow_downscale
        self.align_x = align_x
        self.align_y = align_y
        self.background = background
        self.clip = clip
        self.visible = visible
        self.enabled = True

    @property
    def rect(self) -> Rect:
        return self._rect

    def set_rect(self, rect: Rect | tuple[int, int, int, int]) -> None:
        self._rect = Rect(*rect) if isinstance(rect, tuple) else rect

    def set_image(self, image) -> None:
        self.image = image

    def load_path(self, path: str | Path) -> None:
        from pygame_ui.skin import _load_image_alpha

        self.image = _load_image_alpha(Path(path))

    def draw(self, surface, theme: UITheme) -> None:
        if not self.visible or self.image is None:
            return
        r = self._rect
        blit_fitted(
            surface,
            self.image,
            (r.x, r.y, r.w, r.h),
            self.scale_mode,
            align_x=self.align_x,
            align_y=self.align_y,
            allow_upscale=self.allow_upscale,
            allow_downscale=self.allow_downscale,
            clip=self.clip,
            background=self.background,
        )

    def handle_event(self, event, theme: UITheme) -> bool:
        return False
