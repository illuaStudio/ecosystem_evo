#!/usr/bin/env python3
"""Noto Sans JP を pygame_ui にダウンロード（任意）。"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FONT_DIR = ROOT / "pygame_ui" / "assets" / "fonts"

URLS = {
    "NotoSansCJKjp-Regular.otf": (
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf"
    ),
    "NotoSansCJKjp-Bold.otf": (
        "https://raw.githubusercontent.com/notofonts/noto-cjk/main/Sans/OTF/Japanese/NotoSansCJKjp-Bold.otf"
    ),
}


def main() -> int:
    FONT_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in URLS.items():
        dest = FONT_DIR / name
        if dest.is_file() and dest.stat().st_size > 100_000:
            print(f"skip (exists): {dest}")
            continue
        print(f"download: {url}")
        try:
            urllib.request.urlretrieve(url, dest)
            print(f"  -> {dest} ({dest.stat().st_size} bytes)")
        except Exception as exc:
            print(f"  failed: {exc}", file=sys.stderr)
            return 1
    print("done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
