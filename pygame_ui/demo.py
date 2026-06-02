"""pygame_ui 単体デモ（ecosystem_evo / Sim / Game 不要）。

実行:
  python -m pygame_ui.demo

操作:
  T キー … テーマ切替
  1〜6 … 右ペイン ImageView の scale_mode
  ウィンドウリサイズ … 上下左右ペインが追従（中央が game_rect）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pygame

from pygame_ui import (
    Button,
    Checkbox,
    ContextMenu,
    ContextMenuItem,
    DockEdge,
    ImageScaleMode,
    ImageView,
    ScreenOverlay,
    Slider,
    UITheme,
    VBox,
)

_SAMPLE_ICON = Path(__file__).resolve().parent / "assets" / "skins" / "pixel" / "checkbox_on.png"


def main() -> None:
    pygame.init()
    screen = pygame.display.set_mode((720, 480), pygame.RESIZABLE)
    pygame.display.set_caption("pygame_ui demo — ScreenOverlay")
    clock = pygame.time.Clock()

    themes = [
        UITheme.from_defaults(),
        UITheme.pixel_art(),
        UITheme.with_skin("pixel"),
    ]
    theme_index = 0
    theme = themes[theme_index]
    overlay = ScreenOverlay(theme)

    status = "準備完了（T: テーマ / 端ドラッグでレイアウト確認）"
    speed = 0.5
    flags = {"territory": True, "shelter": False}

    def set_status(msg: str) -> None:
        nonlocal status
        status = msg

    def toggle_theme() -> None:
        nonlocal theme_index, theme
        theme_index = (theme_index + 1) % len(themes)
        theme = themes[theme_index]
        overlay.set_theme(theme)
        set_status(f"テーマ: {theme.name}")

    top_panel = overlay.dock_top(36, title="pygame_ui — ScreenOverlay デモ")
    bottom_panel = overlay.dock_bottom(200, title="コントロール（下ペイン）")
    right_panel = overlay.dock_right(360, title="ImageView")

    def subwindow_anchor():
        g = overlay.game_rect
        return type(g)(
            g.x + 24,
            g.y + 24,
            min(220, max(120, g.w // 3)),
            min(140, max(80, g.h // 3)),
        )

    overlay.dock_on(subwindow_anchor, DockEdge.TOP, 26, title="サブ枠ツールバー")

    vbox = VBox(0, 0, 280, spacing=8)
    btn_pause = Button((0, 0, 280, 36), "一時停止", on_click=lambda: set_status("一時停止"))
    btn_theme = Button((0, 0, 280, 32), "テーマ切替", on_click=toggle_theme)
    chk_territory = Checkbox(
        (0, 0, 280, 28),
        "テリトリー表示",
        checked=flags["territory"],
        on_change=lambda v: (flags.update({"territory": v}), set_status(f"territory={v}")),
    )
    chk_shelter = Checkbox(
        (0, 0, 280, 28),
        "避難所の個体を表示",
        checked=flags["shelter"],
        on_change=lambda v: (flags.update({"shelter": v}), set_status(f"shelter={v}")),
    )
    slider = Slider((0, 0, 280, 32), value=speed, on_change=lambda v: set_status(f"速度 {v:.0%}"))
    vbox.add(btn_pause, 36)
    vbox.add(btn_theme, 32)
    vbox.add(chk_territory, 28)
    vbox.add(chk_shelter, 28)
    vbox.add(slider, 32)
    for w in vbox.children:
        bottom_panel.add_child(w)

    preview_modes = list(ImageScaleMode)
    preview_index = 2
    preview = ImageView(
        (0, 0, 1, 1),
        image_path=_SAMPLE_ICON,
        scale_mode=preview_modes[preview_index],
        background=(20, 28, 22, 180),
    )
    right_panel.add_child(preview)
    thumb_native = ImageView(
        (0, 0, 1, 1),
        image_path=_SAMPLE_ICON,
        scale_mode=ImageScaleMode.NATIVE,
        background=(30, 40, 32),
    )
    thumb_stretch = ImageView(
        (0, 0, 1, 1),
        image_path=_SAMPLE_ICON,
        scale_mode=ImageScaleMode.STRETCH,
        background=(30, 40, 32),
    )
    thumb_fit = ImageView(
        (0, 0, 1, 1),
        image_path=_SAMPLE_ICON,
        scale_mode=ImageScaleMode.FIT_SHRINK_ONLY,
        background=(30, 40, 32),
    )
    for t in (thumb_native, thumb_stretch, thumb_fit):
        right_panel.add_child(t)

    menu = ContextMenu(
        items=[
            ContextMenuItem("spawn", "デバッグスポーン"),
            ContextMenuItem("clear", "選択解除"),
            ContextMenuItem("disabled", "無効項目", enabled=False),
        ],
        on_select=lambda aid: set_status(f"menu: {aid}"),
    )
    overlay.add_overlay(menu)

    def layout_content() -> None:
        overlay.set_viewport(*screen.get_size())
        overlay.relayout_vbox(bottom_panel, vbox)
        pad = theme.padding
        rp = right_panel.rect
        ch = rp.h - (right_panel.content_top(theme) - rp.y) - pad - 56
        preview.set_rect(
            right_panel.local_rect(pad, pad, rp.w - pad * 2, max(40, ch), theme=theme, below_title=True)
        )
        ty = rp.y + rp.h - 52
        tw = max(1, (rp.w - pad * 4) // 3)
        thumb_native.set_rect((rp.x + pad, ty, tw, 44))
        thumb_stretch.set_rect((rp.x + pad * 2 + tw, ty, tw, 44))
        thumb_fit.set_rect((rp.x + pad * 3 + tw * 2, ty, tw, 44))

    layout_content()

    def set_preview_mode(idx: int) -> None:
        nonlocal preview_index
        preview_index = idx % len(preview_modes)
        preview.scale_mode = preview_modes[preview_index]
        set_status(f"ImageView: {preview.scale_mode.value}")

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode(
                    (max(480, event.w), max(360, event.h)),
                    pygame.RESIZABLE,
                )
                layout_content()
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_t:
                toggle_theme()
            elif event.type == pygame.KEYDOWN and pygame.K_1 <= event.key <= pygame.K_6:
                set_preview_mode(event.key - pygame.K_1)
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
                if not overlay.handle_event(event):
                    menu.show(event.pos[0], event.pos[1], theme)
            elif not overlay.handle_event(event):
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    menu.hide()

        screen.fill(theme.canvas_bg)
        g = overlay.game_rect
        if g.w > 0 and g.h > 0:
            pygame.draw.rect(screen, (28, 42, 32), (g.x, g.y, g.w, g.h))
            pygame.draw.rect(screen, theme.panel_border, (g.x, g.y, g.w, g.h), 2)
            label = theme.font(theme.font_size_title).render(
                "game_rect（ワールド描画領域）", True, theme.text_muted
            )
            screen.blit(label, (g.x + 12, g.y + 12))

        overlay.draw(screen)

        small = theme.font(theme.font_size_small)
        tp = top_panel.rect
        screen.blit(
            small.render(
                f"{status} | game {g.w}×{g.h} | 右クリック=メニュー | 1-6=scale",
                True,
                theme.text_muted,
            ),
            (tp.x + 220, tp.y + 10),
        )

        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pygame.quit()
        sys.exit(0)
