"""ゲーム画面への UI 重ね合わせ（上下左右ペイン・サブ領域）。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable, List, Optional, Tuple, Union

from pygame_ui.base import Rect, UIRoot, Widget
from pygame_ui.panel import Panel
from pygame_ui.theme import UITheme

Anchor = Union[Rect, Callable[[], Rect]]


class DockEdge(str, Enum):
    """ペインを張り付ける辺（画面または anchor 矩形の内側）。"""

    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"


@dataclass
class _DockSlot:
    edge: DockEdge
    size: int
    panel: Panel
    anchor: Optional[Anchor] = None


def _resolve_anchor(anchor: Anchor) -> Rect:
    r = anchor() if callable(anchor) else anchor
    return r if isinstance(r, Rect) else Rect(*r)


def _anchor_key(anchor: Anchor) -> Tuple:
    if callable(anchor):
        return ("fn", id(anchor))
    return ("rect", anchor.x, anchor.y, anchor.w, anchor.h)


def layout_dock_rects(
    bounds: Rect,
    slots: List[_DockSlot],
) -> tuple[Rect, List[tuple[Panel, Rect]]]:
    """
    bounds 内にドックスロットを配置し、残り矩形と各 Panel の rect を返す。
    """
    x, y, w, h = bounds.x, bounds.y, bounds.w, bounds.h
    placed: List[tuple[Panel, Rect]] = []

    for edge in (DockEdge.TOP, DockEdge.BOTTOM, DockEdge.LEFT, DockEdge.RIGHT):
        group = [s for s in slots if s.edge == edge]
        if not group:
            continue
        if edge == DockEdge.TOP:
            for s in group:
                pr = Rect(x, y, w, s.size)
                placed.append((s.panel, pr))
                y += s.size
                h -= s.size
        elif edge == DockEdge.BOTTOM:
            total = sum(s.size for s in group)
            yb = y + h - total
            for s in group:
                pr = Rect(x, yb, w, s.size)
                placed.append((s.panel, pr))
                yb += s.size
            h -= total
        elif edge == DockEdge.LEFT:
            for s in group:
                pr = Rect(x, y, s.size, h)
                placed.append((s.panel, pr))
                x += s.size
                w -= s.size
        elif edge == DockEdge.RIGHT:
            total = sum(s.size for s in group)
            xr = x + w - total
            for s in group:
                pr = Rect(xr, y, s.size, h)
                placed.append((s.panel, pr))
                xr += s.size
            w -= total

    return Rect(x, y, w, h), placed


class ScreenOverlay:
    """
    ゲーム描画の上に UI を重ねるホスト。

    - 上下左右ペイン: 画面サイズに合わせて **帯だけ** 伸縮（厚み ``size`` は固定 px）
    - ペイン内のボタン等は従来どおり固定サイズ（VBox / local_rect で配置）
    - ``dock_on`` でサブウインドウ矩形の上にも同様にドック可能

    典型的なループ::

        overlay.set_viewport(*screen.get_size())
        # ... ゲームを overlay.game_rect に描画 ...
        overlay.draw(screen)
        overlay.handle_event(event)
    """

    def __init__(self, theme: UITheme | None = None) -> None:
        self.theme = theme or UITheme.from_defaults()
        self.root = UIRoot(self.theme)
        self._screen_slots: List[_DockSlot] = []
        self._anchor_slots: List[_DockSlot] = []
        self.game_rect = Rect(0, 0, 0, 0)

    def set_theme(self, theme: UITheme) -> None:
        self.theme = theme
        self.root.set_theme(theme)

    def _register(self, slot: _DockSlot) -> Panel:
        self.root.add(slot.panel)
        return slot.panel

    def dock(
        self,
        edge: DockEdge,
        size: int,
        *,
        title: str = "",
        panel: Panel | None = None,
    ) -> Panel:
        """画面端にペインを追加（厚み ``size`` px は固定）。"""
        p = panel or Panel((0, 0, 1, 1), title=title)
        slot = _DockSlot(edge=edge, size=size, panel=p)
        self._screen_slots.append(slot)
        return self._register(slot)

    def dock_top(self, height: int, **kwargs) -> Panel:
        return self.dock(DockEdge.TOP, height, **kwargs)

    def dock_bottom(self, height: int, **kwargs) -> Panel:
        return self.dock(DockEdge.BOTTOM, height, **kwargs)

    def dock_left(self, width: int, **kwargs) -> Panel:
        return self.dock(DockEdge.LEFT, width, **kwargs)

    def dock_right(self, width: int, **kwargs) -> Panel:
        return self.dock(DockEdge.RIGHT, width, **kwargs)

    def dock_on(
        self,
        anchor: Anchor,
        edge: DockEdge,
        size: int,
        *,
        title: str = "",
        panel: Panel | None = None,
    ) -> Panel:
        """
        任意矩形（ミニマップ枠・サブウインドウなど）の内側にペインを張る。

        ``anchor`` は ``Rect`` または ``lambda: Rect(...)``（毎フレーム更新可）。
        """
        p = panel or Panel((0, 0, 1, 1), title=title)
        slot = _DockSlot(edge=edge, size=size, panel=p, anchor=anchor)
        self._anchor_slots.append(slot)
        return self._register(slot)

    def add_floating(self, widget: Widget) -> Widget:
        """画面座標固定のウィジェット（リサイズ時は自前で rect 更新）。"""
        return self.root.add(widget)

    def add_overlay(self, widget: Widget) -> Widget:
        return self.root.add_overlay(widget)

    def set_viewport(self, width: int, height: int) -> Rect:
        """ウィンドウサイズ変更時に呼ぶ。``game_rect`` を更新しペインを再配置。"""
        vw = max(0, int(width))
        vh = max(0, int(height))

        self.game_rect, placed = layout_dock_rects(Rect(0, 0, vw, vh), self._screen_slots)
        for panel, rect in placed:
            panel.set_rect(rect)

        groups: dict[Tuple, List[_DockSlot]] = {}
        for slot in self._anchor_slots:
            if slot.anchor is None:
                continue
            groups.setdefault(_anchor_key(slot.anchor), []).append(slot)

        for group in groups.values():
            ar = _resolve_anchor(group[0].anchor)
            _, anchor_placed = layout_dock_rects(ar, group)
            for panel, rect in anchor_placed:
                panel.set_rect(rect)

        return self.game_rect

    def relayout_vbox(self, panel: Panel, vbox, theme: UITheme | None = None) -> None:
        """ドック後に VBox をペイン内へ再配置（リサイズ時に呼ぶ）。"""
        theme = theme or self.theme
        pad = theme.padding
        vbox.x = panel.rect.x + pad
        vbox.width = max(1, panel.rect.w - pad * 2)
        vbox.place_in_panel(panel, theme)

    def draw(self, surface) -> None:
        self.root.draw(surface)

    def handle_event(self, event) -> bool:
        return self.root.handle_event(event)

    def consumes_point(self, px: int, py: int) -> bool:
        """ゲーム入力を渡す前に UI がその座標を使うか。"""
        return self.root.hit_test((px, py)) is not None
