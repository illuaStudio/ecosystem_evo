"""pygame_ui が ecosystem_evo の game/sim/client を import しないこと。"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PYGAME_UI = REPO_ROOT / "pygame_ui"

FORBIDDEN_PREFIXES = ("src.game", "src.sim", "src.client")


def _violations() -> list[str]:
    out: list[str] = []
    for path in sorted(PYGAME_UI.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            mod = None
            if isinstance(node, ast.Import):
                for alias in node.names:
                    mod = alias.name
            elif isinstance(node, ast.ImportFrom) and node.module:
                mod = node.module
            if mod and any(mod.startswith(p) for p in FORBIDDEN_PREFIXES):
                out.append(f"{rel} imports {mod}")
    return out


def test_pygame_ui_is_game_agnostic():
    bad = _violations()
    assert bad == [], "pygame_ui must not import game/sim/client:\n" + "\n".join(bad)
