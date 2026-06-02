"""見た目の定数（ゲーム非依存）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

if TYPE_CHECKING:
    from pygame_ui.skin import UISkin

Color = Tuple[int, int, int]
ColorA = Tuple[int, int, int, int]

_PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_FONT_PATH = _PACKAGE_DIR / "assets" / "fonts" / "NotoSansCJKjp-Regular.otf"


@dataclass
class UITheme:
    """UI 配色・フォント。`pixel_art()` / `from_defaults()` でプリセット切替。"""

    name: str = "default"
    font_path: Path | None = None
    font_size: int = 16
    font_size_small: int = 13
    font_size_title: int = 18

    text_color: Color = (235, 240, 230)
    text_muted: Color = (160, 170, 155)
    text_disabled: Color = (110, 115, 105)

    canvas_bg: Color = (18, 28, 20)

    panel_bg: ColorA = (12, 18, 14, 200)
    panel_border: Color = (55, 75, 55)

    button_bg: Color = (42, 58, 42)
    button_bg_hover: Color = (58, 78, 58)
    button_bg_pressed: Color = (32, 44, 32)
    button_border: Color = (90, 120, 90)

    checkbox_bg: Color = (30, 40, 30)
    checkbox_fill: Color = (120, 180, 100)
    checkbox_on: Color = (120, 180, 100)
    checkbox_border: Color = (80, 100, 80)

    slider_track: Color = (40, 50, 40)
    slider_fill: Color = (90, 140, 80)
    slider_thumb: Color = (200, 220, 190)

    menu_bg: ColorA = (16, 22, 18, 230)
    menu_border: Color = (70, 90, 70)
    menu_hover: Color = (50, 68, 50)

    bevel_light: Color = (180, 180, 200)
    bevel_shadow: Color = (40, 40, 56)

    padding: int = 8
    radius: int = 4
    border_width: int = 1
    pixel_style: bool = False

    skin: Optional["UISkin"] = None

    _font_cache: object = field(default=None, repr=False)

    @classmethod
    def from_defaults(cls, **overrides) -> "UITheme":
        """やわらかい角丸（従来のデモ見た目）。"""
        theme = cls(name="default")
        if theme.font_path is None and DEFAULT_FONT_PATH.is_file():
            theme.font_path = DEFAULT_FONT_PATH
        return theme._apply(overrides)

    @classmethod
    def pixel_art(cls, **overrides) -> "UITheme":
        """ドット絵・レトロ UI 向け（角丸なし・ベベル枠・限定パレット）。"""
        theme = cls(
            name="pixel_art",
            font_size=12,
            font_size_small=10,
            font_size_title=14,
            radius=0,
            padding=6,
            border_width=2,
            pixel_style=True,
            canvas_bg=(28, 28, 44),
            text_color=(252, 252, 220),
            text_muted=(168, 168, 140),
            text_disabled=(96, 96, 88),
            panel_bg=(48, 48, 72, 255),
            panel_border=(104, 104, 136),
            button_bg=(88, 88, 128),
            button_bg_hover=(112, 112, 160),
            button_bg_pressed=(64, 64, 96),
            button_border=(152, 152, 184),
            checkbox_bg=(56, 56, 80),
            checkbox_fill=(180, 220, 120),
            checkbox_on=(180, 220, 120),
            checkbox_border=(120, 120, 152),
            slider_track=(56, 56, 80),
            slider_fill=(140, 180, 100),
            slider_thumb=(220, 220, 180),
            menu_bg=(40, 40, 64, 255),
            menu_border=(136, 136, 168),
            menu_hover=(72, 72, 108),
            bevel_light=(200, 200, 224),
            bevel_shadow=(32, 32, 48),
        )
        if theme.font_path is None and DEFAULT_FONT_PATH.is_file():
            theme.font_path = DEFAULT_FONT_PATH
        return theme._apply(overrides)

    @classmethod
    def with_skin(cls, skin_id: str, *, base: str = "pixel_art", **overrides) -> "UITheme":
        """組み込みスキン `assets/skins/<skin_id>/` を載せたテーマ。"""
        from pygame_ui.skin import UISkin

        if base == "pixel_art":
            theme = cls.pixel_art()
        else:
            theme = cls.from_defaults()
        theme.skin = UISkin.load_builtin(skin_id)
        theme.name = f"skin:{theme.skin.name}"
        return theme._apply(overrides)

    @classmethod
    def from_skin_dir(cls, path: str | Path, *, base: str = "pixel_art", **overrides) -> "UITheme":
        """任意ディレクトリの skin.json + PNG。"""
        from pygame_ui.skin import UISkin

        if base == "pixel_art":
            theme = cls.pixel_art()
        else:
            theme = cls.from_defaults()
        theme.skin = UISkin.from_directory(path)
        theme.name = f"skin:{theme.skin.name}"
        return theme._apply(overrides)

    def _apply(self, overrides: dict) -> "UITheme":
        for key, value in overrides.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self

    def font(self, size: int | None = None):
        from pygame_ui.fonts import resolve_font

        return resolve_font(
            size or self.font_size,
            path=self.font_path,
            cache=self._font_cache,
        )

    def ensure_font_cache(self) -> None:
        if self._font_cache is None:
            from pygame_ui.fonts import FontCache

            self._font_cache = FontCache()
