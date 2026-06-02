"""日本語対応フォント（同梱優先、SysFont はフォールバック）。"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pygame

_PACKAGE_DIR = Path(__file__).resolve().parent
BUNDLED_REGULAR = _PACKAGE_DIR / "assets" / "fonts" / "NotoSansCJKjp-Regular.otf"
BUNDLED_REGULAR_ALT = _PACKAGE_DIR / "assets" / "fonts" / "NotoSansJP-Regular.otf"
BUNDLED_BOLD = _PACKAGE_DIR / "assets" / "fonts" / "NotoSansCJKjp-Bold.otf"
BUNDLED_BOLD_ALT = _PACKAGE_DIR / "assets" / "fonts" / "NotoSansJP-Bold.otf"

# 同梱が無い環境向け（日本語グリフを含むことが多い順）
_SYSFONT_FALLBACKS = (
    "noto sans jp",
    "notosansjp",
    "meiryo",
    "yu gothic ui",
    "msgothic",
    "ms gothic",
    "hiragino sans",
    "ipaexgothic",
    "sans-serif",
)


class FontCache:
    def __init__(self) -> None:
        self._cache: dict[tuple[str, int, bool], "pygame.font.Font"] = {}

    def get(
        self,
        size: int,
        *,
        path: Path | str | None = None,
        bold: bool = False,
    ) -> "pygame.font.Font":
        import pygame

        key_path = str(path) if path else ""
        key = (key_path, int(size), bool(bold))
        hit = self._cache.get(key)
        if hit is not None:
            return hit
        font = resolve_font(size, path=path, bold=bold, cache=None)
        self._cache[key] = font
        return font


def resolve_font(
    size: int,
    *,
    path: Path | str | None = None,
    bold: bool = False,
    cache: FontCache | None = None,
) -> "pygame.font.Font":
    import pygame

    if cache is not None:
        return cache.get(size, path=path, bold=bold)

    size = max(8, int(size))
    candidates: list[Path] = []
    if path:
        candidates.append(Path(path))
    elif bold:
        for p in (BUNDLED_BOLD, BUNDLED_BOLD_ALT, BUNDLED_REGULAR, BUNDLED_REGULAR_ALT):
            candidates.append(p)
    else:
        for p in (BUNDLED_REGULAR, BUNDLED_REGULAR_ALT, BUNDLED_BOLD, BUNDLED_BOLD_ALT):
            candidates.append(p)

    for candidate in candidates:
        if candidate.is_file():
            try:
                return pygame.font.Font(str(candidate), size)
            except Exception:
                pass

    for name in _SYSFONT_FALLBACKS:
        try:
            font = pygame.font.SysFont(name, size, bold=bold)
            if font is not None:
                return font
        except Exception:
            continue

    return pygame.font.Font(None, size)


def wrap_text_jp(
    text: str,
    font: "pygame.font.Font",
    max_width: int,
) -> list[str]:
    """日本語向け: 文字単位で折り返し。"""
    if not text or max_width <= 0:
        return [""]
    lines: list[str] = []
    current = ""
    for ch in text.replace("\r\n", "\n").replace("\r", "\n"):
        if ch == "\n":
            lines.append(current)
            current = ""
            continue
        trial = current + ch
        if font.size(trial)[0] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = ch
    if current or not lines:
        lines.append(current)
    return lines


def truncate_text(
    text: str,
    font: "pygame.font.Font",
    max_width: int,
    *,
    ellipsis: str = "…",
) -> str:
    if font.size(text)[0] <= max_width:
        return text
    ell = ellipsis
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid] + ell)[0] <= max_width:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo] + ell if lo > 0 else ell
