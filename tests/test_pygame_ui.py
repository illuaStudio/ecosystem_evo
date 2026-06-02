"""pygame_ui ユニットテスト（ヘッドレス）。"""
from __future__ import annotations

import os
import unittest

# ディスプレイ無し環境向け
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _init_pygame():
    import pygame

    if not pygame.get_init():
        pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))
    return pygame


class TestFonts(unittest.TestCase):
    def test_resolve_font_renders_japanese(self):
        _init_pygame()
        from pygame_ui.fonts import resolve_font, truncate_text, wrap_text_jp

        font = resolve_font(16)
        surf = font.render("日本語テスト", True, (255, 255, 255))
        self.assertGreater(surf.get_width(), 10)
        lines = wrap_text_jp("表示を切り替える", font, 80)
        self.assertGreaterEqual(len(lines), 1)
        short = truncate_text("長いラベル文字列テスト", font, 40)
        self.assertIn("…", short)


class TestWidgets(unittest.TestCase):
    def setUp(self):
        self.pygame = _init_pygame()

    def test_checkbox_toggle(self):
        from pygame_ui import Checkbox, Rect, UITheme

        theme = UITheme.from_defaults()
        changes: list[bool] = []
        box = Checkbox(
            Rect(0, 0, 200, 28),
            "テスト",
            checked=False,
            on_change=changes.append,
        )
        ev = self.pygame.event.Event(
            self.pygame.MOUSEBUTTONDOWN,
            {"pos": (10, 10), "button": 1},
        )
        self.assertTrue(box.handle_event(ev, theme))
        self.assertTrue(box.checked)
        self.assertEqual(changes, [True])

    def test_button_click(self):
        from pygame_ui import Button, Rect, UITheme

        theme = UITheme.from_defaults()
        clicks: list[int] = []
        btn = Button(Rect(0, 0, 100, 32), "OK", on_click=lambda: clicks.append(1))
        down = self.pygame.event.Event(
            self.pygame.MOUSEBUTTONDOWN,
            {"pos": (5, 5), "button": 1},
        )
        up = self.pygame.event.Event(
            self.pygame.MOUSEBUTTONUP,
            {"pos": (5, 5), "button": 1},
        )
        btn.handle_event(down, theme)
        btn.handle_event(up, theme)
        self.assertEqual(clicks, [1])

    def test_slider_value(self):
        from pygame_ui import Rect, Slider, UITheme

        theme = UITheme.from_defaults()
        values: list[float] = []
        slider = Slider(Rect(0, 0, 200, 24), value=0.2, on_change=values.append)
        down = self.pygame.event.Event(
            self.pygame.MOUSEBUTTONDOWN,
            {"pos": (150, 12), "button": 1},
        )
        slider.handle_event(down, theme)
        self.assertGreater(slider.value, 0.5)
        self.assertTrue(values)

    def test_context_menu_select(self):
        from pygame_ui import ContextMenu, ContextMenuItem, UITheme

        theme = UITheme.from_defaults()
        picked: list[str] = []
        menu = ContextMenu(
            items=[
                ContextMenuItem("a", "項目A"),
                ContextMenuItem("b", "項目B"),
            ],
            on_select=picked.append,
        )
        menu.show(10, 10, theme)
        ev = self.pygame.event.Event(
            self.pygame.MOUSEBUTTONDOWN,
            {"pos": (20, 20), "button": 1},
        )
        self.assertTrue(menu.handle_event(ev, theme))
        self.assertEqual(picked, ["a"])
        self.assertFalse(menu.visible)

    def test_screen_overlay_dock(self):
        from pygame_ui import Rect, ScreenOverlay, UITheme

        theme = UITheme.from_defaults()
        overlay = ScreenOverlay(theme)
        overlay.dock_top(50)
        overlay.dock_bottom(80)
        overlay.dock_right(100)
        game = overlay.set_viewport(800, 600)
        self.assertEqual(game, Rect(0, 50, 700, 470))

        overlay2 = ScreenOverlay(theme)
        overlay2.dock_left(60)
        game2 = overlay2.set_viewport(400, 300)
        self.assertEqual(game2.x, 60)
        self.assertEqual(game2.w, 340)

    def test_dock_on_anchor(self):
        from pygame_ui import Rect, ScreenOverlay, UITheme
        from pygame_ui.dock import DockEdge

        theme = UITheme.from_defaults()
        overlay = ScreenOverlay(theme)
        anchor = lambda: Rect(100, 80, 200, 150)
        overlay.dock_on(anchor, DockEdge.TOP, 30, title="bar")
        overlay.set_viewport(640, 480)
        # anchor slot panel should be at y=80
        panel = overlay._anchor_slots[0].panel
        self.assertEqual(panel.rect.y, 80)
        self.assertEqual(panel.rect.h, 30)

    def test_panel_local_rect(self):
        from pygame_ui import Panel, Rect, UITheme

        theme = UITheme.from_defaults()
        panel = Panel(Rect(100, 50, 200, 150), title="T")
        r = panel.local_rect(10, 20, 80, 60)
        self.assertEqual(r, Rect(110, 70, 80, 60))
        top = panel.content_top(theme) - panel.rect.y
        r2 = panel.local_rect(0, 4, 100, 40, theme=theme, below_title=True)
        self.assertEqual(r2.x, 100)
        self.assertEqual(r2.y, panel.rect.y + top + 4)

    def test_ui_root_z_order(self):
        from pygame_ui import Button, Rect, UIRoot, UITheme

        theme = UITheme.from_defaults()
        root = UIRoot(theme)
        bottom = Button(Rect(0, 0, 100, 30), "下")
        top = Button(Rect(0, 0, 100, 30), "上", on_click=lambda: None)
        root.add(bottom)
        root.add(top)
        hit = root.hit_test((50, 15))
        self.assertIs(hit, top)


class TestImageFit(unittest.TestCase):
    def test_native_keeps_size(self):
        from pygame_ui.image_fit import ImageScaleMode, compute_dest_rect

        dest = compute_dest_rect((0, 0, 100, 100), (64, 24), ImageScaleMode.NATIVE)
        self.assertEqual(dest, (18, 38, 64, 24))

    def test_stretch_fills_bounds(self):
        from pygame_ui.image_fit import ImageScaleMode, compute_dest_rect

        dest = compute_dest_rect((10, 20, 80, 60), (64, 24), ImageScaleMode.STRETCH)
        self.assertEqual(dest, (10, 20, 80, 60))

    def test_fit_shrink_only(self):
        from pygame_ui.image_fit import ImageScaleMode, compute_dest_rect

        dest = compute_dest_rect((0, 0, 40, 40), (80, 80), ImageScaleMode.FIT_SHRINK_ONLY)
        self.assertIsNotNone(dest)
        _x, _y, w, h = dest
        self.assertLessEqual(w, 40)
        self.assertLessEqual(h, 40)
        self.assertEqual(w, h)

    def test_fit_grow_only(self):
        from pygame_ui.image_fit import ImageScaleMode, compute_dest_rect

        dest = compute_dest_rect((0, 0, 100, 100), (10, 10), ImageScaleMode.FIT_GROW_ONLY)
        self.assertIsNotNone(dest)
        _x, _y, w, h = dest
        self.assertGreater(w, 10)
        self.assertGreater(h, 10)

    def test_override_allow_upscale(self):
        from pygame_ui.image_fit import ImageScaleMode, compute_dest_rect

        dest = compute_dest_rect(
            (0, 0, 100, 100),
            (10, 10),
            ImageScaleMode.FIT_SHRINK_ONLY,
            allow_upscale=True,
        )
        self.assertIsNotNone(dest)
        _x, _y, w, h = dest
        self.assertGreater(w, 10)

    def test_image_view_load(self):
        _init_pygame()
        from pathlib import Path

        from pygame_ui import ImageScaleMode, ImageView, Rect, UITheme

        icon = Path(__file__).resolve().parents[1] / "pygame_ui" / "assets" / "skins" / "pixel" / "checkbox_on.png"
        if not icon.is_file():
            self.skipTest("sample icon missing")
        view = ImageView(Rect(0, 0, 50, 50), image_path=icon, scale_mode=ImageScaleMode.STRETCH)
        import pygame

        surf = pygame.Surface((50, 50))
        view.draw(surf, UITheme.from_defaults())
        self.assertGreater(surf.get_bounding_rect().width, 0)


class TestSkin(unittest.TestCase):
    def setUp(self):
        _init_pygame()

    def test_load_builtin_pixel_skin(self):
        from pygame_ui import UISkin

        skin = UISkin.load_builtin("pixel")
        self.assertEqual(skin.name, "pixel")
        self.assertIsNotNone(skin.image("button_idle"))
        self.assertIsNotNone(skin.slice_spec("panel"))

    def test_theme_with_skin(self):
        from pygame_ui import UITheme

        theme = UITheme.with_skin("pixel")
        self.assertTrue(theme.name.startswith("skin:"))
        self.assertIsNotNone(theme.skin)

    def test_nine_slice_blit(self):
        from pygame_ui.skin import UISkin
        from pygame_ui.skin_draw import blit_nine_slice

        spec = UISkin.load_builtin("pixel").slice_spec("panel")
        self.assertIsNotNone(spec)
        import pygame

        dst = pygame.Surface((120, 80), pygame.SRCALPHA)
        blit_nine_slice(dst, (0, 0, 120, 80), spec)
        self.assertGreater(dst.get_at((60, 40))[3], 0)


class TestThemes(unittest.TestCase):
    def test_pixel_art_preset(self):
        from pygame_ui import UITheme

        t = UITheme.pixel_art()
        self.assertEqual(t.name, "pixel_art")
        self.assertTrue(t.pixel_style)
        self.assertEqual(t.radius, 0)

    def test_theme_toggle_cache(self):
        _init_pygame()
        from pygame_ui import UITheme, UIRoot

        root = UIRoot(UITheme.from_defaults())
        root.set_theme(UITheme.pixel_art())
        self.assertEqual(root.theme.name, "pixel_art")


class TestImportIsolation(unittest.TestCase):
    def test_pygame_ui_has_no_game_sim_imports(self):
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1] / "pygame_ui"
        bad = []
        for path in root.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                mod = None
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        mod = alias.name
                elif isinstance(node, ast.ImportFrom) and node.module:
                    mod = node.module
                if mod and (
                    mod.startswith("src.game")
                    or mod.startswith("src.sim")
                    or mod.startswith("src.client")
                ):
                    bad.append(f"{path.name}: {mod}")
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
