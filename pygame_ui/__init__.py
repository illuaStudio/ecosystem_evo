"""ゲーム非依存の Pygame UI ウィジェット（日本語表示対応）。"""
from pygame_ui.base import Rect, UIRoot, Widget
from pygame_ui.dock import DockEdge, ScreenOverlay, layout_dock_rects
from pygame_ui.button import Button
from pygame_ui.checkbox import Checkbox
from pygame_ui.context_menu import ContextMenu, ContextMenuItem
from pygame_ui.fonts import FontCache, resolve_font, truncate_text, wrap_text_jp
from pygame_ui.image_fit import ImageScaleMode
from pygame_ui.image_view import ImageView
from pygame_ui.layout import VBox
from pygame_ui.panel import Panel
from pygame_ui.slider import Slider
from pygame_ui.skin import NineSliceSpec, UISkin
from pygame_ui.theme import UITheme

__all__ = [
    "Button",
    "Checkbox",
    "ContextMenu",
    "ContextMenuItem",
    "DockEdge",
    "FontCache",
    "ImageScaleMode",
    "ImageView",
    "NineSliceSpec",
    "Panel",
    "UISkin",
    "Rect",
    "ScreenOverlay",
    "Slider",
    "layout_dock_rects",
    "UITheme",
    "UIRoot",
    "VBox",
    "Widget",
    "resolve_font",
    "truncate_text",
    "wrap_text_jp",
]

__version__ = "0.1.0"
