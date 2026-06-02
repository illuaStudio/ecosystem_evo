#!/usr/bin/env python3
"""サンプル UI スキン PNG と skin.json を生成（pygame 必須）。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "pygame_ui" / "assets" / "skins" / "pixel"


def _rect(surf, color, rect, *, width=0):
    import pygame

    pygame.draw.rect(surf, color, rect, width)


def _bevel_box(w, h, fill, light, shadow):
    import pygame

    s = pygame.Surface((w, h), pygame.SRCALPHA)
    _rect(s, fill, (0, 0, w, h))
    _rect(s, light, (0, 0, w, h), width=2)
    pygame.draw.line(s, light, (2, 2), (w - 3, 2))
    pygame.draw.line(s, light, (2, 2), (2, h - 3))
    pygame.draw.line(s, shadow, (2, h - 3), (w - 3, h - 3))
    pygame.draw.line(s, shadow, (w - 3, 2), (w - 3, h - 3))
    return s


def main() -> int:
    import pygame

    pygame.init()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    palette = {
        "fill": (72, 72, 108),
        "hover": (96, 96, 140),
        "pressed": (52, 52, 80),
        "panel": (48, 48, 72, 255),
        "light": (180, 180, 210),
        "shadow": (28, 28, 44),
        "check_on": (160, 200, 100),
        "check_off": (56, 56, 80),
        "track": (56, 56, 80),
        "fill_bar": (120, 160, 90),
        "thumb": (220, 220, 180),
        "menu_hi": (80, 80, 120, 200),
    }

    assets = {
        "button_idle": _bevel_box(64, 24, palette["fill"], palette["light"], palette["shadow"]),
        "button_hover": _bevel_box(64, 24, palette["hover"], palette["light"], palette["shadow"]),
        "button_pressed": _bevel_box(
            64, 24, palette["pressed"], palette["shadow"], palette["light"]
        ),
        "checkbox_off": _bevel_box(18, 18, palette["check_off"], palette["shadow"], palette["light"]),
        "checkbox_on": _bevel_box(18, 18, palette["check_on"], palette["light"], palette["shadow"]),
        "slider_track": _bevel_box(48, 10, palette["track"], palette["shadow"], palette["light"]),
        "slider_fill": _bevel_box(48, 10, palette["fill_bar"], palette["light"], palette["shadow"]),
        "slider_thumb": _bevel_box(14, 22, palette["thumb"], palette["light"], palette["shadow"]),
        "menu_row_hover": _bevel_box(120, 24, palette["menu_hi"][:3], palette["light"], palette["shadow"]),
    }

    panel = pygame.Surface((48, 48), pygame.SRCALPHA)
    _rect(panel, palette["panel"], (0, 0, 48, 48))
    _rect(panel, palette["light"], (0, 0, 48, 48), width=2)

    for name, surf in assets.items():
        path = OUT_DIR / f"{name}.png"
        pygame.image.save(surf, str(path))
        print(f"wrote {path}")

    panel_path = OUT_DIR / "panel.png"
    pygame.image.save(panel, str(panel_path))
    print(f"wrote {panel_path}")

    manifest = {
        "name": "pixel",
        "images": {k: f"{k}.png" for k in assets},
        "nine_slice": {
            "panel": {"image": "panel.png", "left": 8, "top": 8, "right": 8, "bottom": 8},
            "menu": {"image": "panel.png", "left": 8, "top": 8, "right": 8, "bottom": 8},
            "slider_track": {
                "image": "slider_track.png",
                "left": 4,
                "top": 2,
                "right": 4,
                "bottom": 2,
            },
        },
    }
    manifest_path = OUT_DIR / "skin.json"
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"wrote {manifest_path}")
    pygame.quit()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
