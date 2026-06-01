#!/usr/bin/env python3
"""一時スクリプト: nest_system 参照を colony orchestrator へ置換。"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REPLACEMENTS = [
    ("world.nest_system.get_creature_nest(", "colony(world).get_creature_affiliation_root("),
    ("world.nest_system.get_affiliation_root(", "colony(world).get_affiliation_root("),
    ("world.nest_system.create_nest(", "colony(world).create_affiliation_site("),
    ("world.nest_system.nests", "colony(world).affiliation_roots"),
    ("world.nest_system.", "colony(world)."),
    ("creature.world.nest_system", "colony(creature.world)"),
    ("getattr(world, \"nest_system\", None)", "try_get_colony_orchestrator(world)"),
    ("getattr(self.engine.world, \"nest_system\", None)", "try_get_colony_orchestrator(self.engine.world)"),
    ("nest_system = getattr(world, \"nest_system\", None)", "colony_orchestrator = try_get_colony_orchestrator(world)"),
    ("nest_system = getattr(self.engine.world, \"nest_system\", None)", "colony_orchestrator = try_get_colony_orchestrator(self.engine.world)"),
    ("if nest_system is None:", "if colony_orchestrator is None:"),
    ("if nest_system is not None:", "if colony_orchestrator is not None:"),
    ("nest_system.", "colony_orchestrator."),
    ("float(getattr(world.nest_system, \"_sim_time\", 0.0))", "float(getattr(world, \"_sim_time\", 0.0))"),
]

IMPORT_COLONY = """from src.game.colony_session import get_colony_orchestrator, try_get_colony_orchestrator

def colony(world):
    return get_colony_orchestrator(world)

"""

BIND_IMPORT = "from tests.sim.colony_binding import bind_colony\n"

GLOBS = [
    "tests/**/*.py",
    "src/client/**/*.py",
    "src/game/**/*.py",
    "tools/**/*.py",
    "src/sim/ai/actions/predation.py",
    "src/sim/ai/actions/reproduction.py",
    "src/sim/ai/actions/shelter.py",
]


def should_skip(path: Path) -> bool:
    parts = path.parts
    if "nest_system.py" in parts or "colony_orchestrator.py" in parts:
        return True
    if "colony.py" in path.name and "colony_actions" not in path.name:
        return True
    if "migrate_nest_refs" in path.name:
        return True
    return False


def ensure_imports(text: str, path: Path) -> str:
    if "colony(world)" not in text and "try_get_colony_orchestrator" not in text:
        return text
    if "def colony(world):" in text:
        pass
    elif path.parts[0] == "tests":
        if BIND_IMPORT.strip() not in text:
            text = BIND_IMPORT + text
    else:
        if "get_colony_orchestrator" not in text:
            text = IMPORT_COLONY + text
    return text


def add_bind_after_world(text: str) -> str:
    if "bind_colony" not in text or "World(" not in text:
        return text
    if "bind_colony(world)" in text:
        return text
    return re.sub(
        r"(world\s*=\s*World\([^\)]*\))",
        r"\1\n        bind_colony(world)",
        text,
        count=0,
    )


def main() -> None:
    for pattern in GLOBS:
        for path in ROOT.glob(pattern):
            if not path.is_file() or should_skip(path):
                continue
            original = path.read_text(encoding="utf-8")
            if "nest_system" not in original and "nest_renderer" not in str(path):
                continue
            text = original
            for old, new in REPLACEMENTS:
                text = text.replace(old, new)
            text = ensure_imports(text, path)
            if path.parts[0] == "tests" and path.name.startswith("test_"):
                text = add_bind_after_world(text)
            if text != original:
                path.write_text(text, encoding="utf-8")
                print("updated", path.relative_to(ROOT))


if __name__ == "__main__":
    main()
