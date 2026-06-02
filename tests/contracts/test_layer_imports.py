"""Client / Game / Sim の import 方向契約（2-AI 並行開発用）。"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"


def _py_files_under(package: str) -> list[Path]:
    base = SRC / package
    return sorted(base.rglob("*.py"))


def _imports_in_file(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                out.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.append((node.lineno, node.module))
    return out


def _layer_of_module(module: str) -> str | None:
    if module.startswith("src.sim"):
        return "sim"
    if module.startswith("src.game"):
        return "game"
    if module.startswith("src.client"):
        return "client"
    return None


def _collect_cross_imports(source_layer: str, forbidden: set[str]) -> list[str]:
    violations: list[str] = []
    for path in _py_files_under(source_layer):
        rel = path.relative_to(REPO_ROOT).as_posix()
        for lineno, module in _imports_in_file(path):
            target = _layer_of_module(module)
            if target in forbidden:
                violations.append(f"{rel}:{lineno} imports {module} ({target})")
    return violations


class TestLayerImportBoundaries:
    def test_sim_does_not_import_game_or_client(self):
        bad = _collect_cross_imports("sim", {"game", "client"})
        assert bad == [], "Sim must not import Game/Client:\n" + "\n".join(bad)

    def test_game_does_not_import_client(self):
        bad = _collect_cross_imports("game", {"client"})
        assert bad == [], "Game must not import Client:\n" + "\n".join(bad)
