"""半透明パネル。

子ウィジェットの rect は画面座標（絶対）で指定する。
パネル内の相対位置には ``local_rect`` を使う。
"""
from __future__ import annotations

from typing import List, Optional

from pygame_ui.base import Rect, Widget
from pygame_ui.draw import draw_widget_frame
from pygame_ui.fonts import truncate_text
from pygame_ui.theme import UITheme


class Panel:
    def __init__(
        self,
        rect: Rect | tuple[int, int, int, int],
        *,
        title: str = "",
        children: Optional[List[Widget]] = None,
        visible: bool = True,
    ) -> None:
        if isinstance(rect, tuple):
            rect = Rect(*rect)
        self._rect = rect
        self.title = str(title)
        self.children: List[Widget] = list(children or [])
        self.visible = visible
        self.enabled = True

    @property
    def rect(self) -> Rect:
        return self._rect

    def set_rect(self, rect: Rect | tuple[int, int, int, int]) -> None:
        self._rect = Rect(*rect) if isinstance(rect, tuple) else rect

    def add_child(self, widget: Widget) -> Widget:
        self.children.append(widget)
        return widget

    def content_top(self, theme: UITheme) -> int:
        if self.title:
            return self._rect.y + theme.padding + theme.font_size_title + theme.padding // 2
        return self._rect.y + theme.padding

    def local_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        *,
        theme: UITheme | None = None,
        below_title: bool = False,
    ) -> Rect:
        """
        パネル左上を (0,0) とした相対座標を画面座標の Rect に変換。

        below_title=True のとき y はタイトル下（content_top）からのオフセット。
        """
        if below_title:
            if theme is None:
                raise ValueError("below_title=True requires theme")
            y = (self.content_top(theme) - self._rect.y) + y
        return Rect(self._rect.x + x, self._rect.y + y, w, h)

    def draw(self, surface, theme: UITheme) -> None:
        if not self.visible:
            return
        r = self._rect
        draw_widget_frame(
            surface,
            (r.x, r.y, r.w, r.h),
            theme,
            fill=theme.panel_bg,
            border=theme.panel_border,
            skin_role="panel",
        )
        if self.title:
            font = theme.font(theme.font_size_title)
            text = truncate_text(self.title, font, max(0, r.w - theme.padding * 2))
            surf = font.render(text, True, theme.text_color)
            surface.blit(surf, (r.x + theme.padding, r.y + theme.padding))
        for child in self.children:
            if getattr(child, "visible", True):
                child.draw(surface, theme)

    def handle_event(self, event, theme: UITheme) -> bool:
        if not self.visible:
            return False
        for child in reversed(self.children):
            if not getattr(child, "visible", True):
                continue
            if not getattr(child, "enabled", True):
                continue
            if child.handle_event(event, theme):
                return True
        pos = getattr(event, "pos", None)
        if pos is not None:
            return self._rect.contains(pos[0], pos[1])
        return False
