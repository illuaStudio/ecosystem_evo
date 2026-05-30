"""3層アーキテクチャへ src/ のディレクトリ移動と import 一括更新。"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"

DIR_MOVES = [
    ("systems", "sim/systems"),
    ("entities", "sim/entities"),
    ("components", "sim/components"),
    ("ai", "sim/ai"),
    ("combat", "sim/combat"),
    ("shelter", "sim/shelter"),
    ("utils", "sim/utils"),
    ("rendering", "client/rendering"),
]

FILE_MOVES = [
    ("core/engine.py", "client/app.py"),
    ("core/camera.py", "client/camera.py"),
    ("core/input_handler.py", "client/input_handler.py"),
    ("core/species_visibility.py", "client/species_visibility.py"),
]

IMPORT_REPLACEMENTS = [
    ("from src.client.app import GameApp", "from src.client.app import GameApp"),
    ("src.client.app", "src.client.app"),
    ("from src.client.species_visibility", "from src.client.species_visibility"),
    ("from src.client.input_handler", "from src.client.input_handler"),
    ("from src.client.camera", "from src.client.camera"),
    ("src.client.species_visibility", "src.client.species_visibility"),
    ("src.client.input_handler", "src.client.input_handler"),
    ("src.client.camera", "src.client.camera"),
    ("from src.client.rendering.", "from src.client.rendering."),
    ("src.client.rendering.", "src.client.rendering."),
    ("from src.sim.systems.", "from src.sim.systems."),
    ("src.sim.systems.", "src.sim.systems."),
    ("from src.sim.entities.", "from src.sim.entities."),
    ("src.sim.entities.", "src.sim.entities."),
    ("from src.sim.components.", "from src.sim.components."),
    ("src.sim.components.", "src.sim.components."),
    ("from src.sim.combat.", "from src.sim.combat."),
    ("src.sim.combat.", "src.sim.combat."),
    ("from src.sim.shelter.", "from src.sim.shelter."),
    ("src.sim.shelter.", "src.sim.shelter."),
    ("from src.sim.utils.", "from src.sim.utils."),
    ("src.sim.utils.", "src.sim.utils."),
    ("from src.sim.ai.", "from src.sim.ai."),
    ("src.sim.ai.", "src.sim.ai."),
    ("GameApp", "GameApp"),
]

CONFIG_REPLACEMENTS = [
    ('config.client["camera_width"]', 'config.client["camera_width"]'),
    ('config.client["camera_height"]', 'config.client["camera_height"]'),
    ("config.game.get(\"debug_mode\"", "config.client.get(\"debug_hud\""),
    ('config.client.get("debug_hud"', 'config.client.get("debug_hud"'),
    ("config.game.get(\"ui_font_size\"", "config.client.get(\"ui_font_size\""),
    ('config.client.get("ui_font_size"', 'config.client.get("ui_font_size"'),
    ("config.game.get(\"camera_pan_extra\"", "config.client.get(\"camera_pan_extra\""),
    ('config.client.get("camera_pan_extra"', 'config.client.get("camera_pan_extra"'),
    ("config.game.get(\"sim_ticks_per_step\"", "config.sim.get(\"sim_ticks_per_step\""),
    ('config.sim.get("sim_ticks_per_step"', 'config.sim.get("sim_ticks_per_step"'),
    ("config.game.get(\"simulation_speed\"", "config.sim.get(\"simulation_speed\""),
    ('config.sim.get("simulation_speed"', 'config.sim.get("simulation_speed"'),
    ('config.client["fps"]', 'config.client["fps"]'),
    ("config.game_app['game_title']", "config.game_app['game_title']"),
    ("config.game_app['version']", "config.game_app['version']"),
    ("config.game = self._load(\"game.json\")", "# migrated to sim/game/client configs"),
    ("game_config = config.game_player", "game_config = config.game_player_player"),
]


def move_dirs() -> None:
    (SRC / "client").mkdir(exist_ok=True)
    for src_rel, dst_rel in DIR_MOVES:
        src = SRC / src_rel
        dst = SRC / dst_rel
        if not src.exists():
            print(f"skip missing dir: {src_rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            print(f"skip existing: {dst_rel}")
            continue
        shutil.move(str(src), str(dst))
        print(f"moved {src_rel} -> {dst_rel}")


def move_files() -> None:
    (SRC / "client").mkdir(exist_ok=True)
    for src_rel, dst_rel in FILE_MOVES:
        src = SRC / src_rel
        dst = SRC / dst_rel
        if not src.exists():
            print(f"skip missing file: {src_rel}")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        print(f"moved {src_rel} -> {dst_rel}")
    core = SRC / "core"
    if core.exists() and not any(core.iterdir()):
        core.rmdir()
        print("removed empty core/")


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new in IMPORT_REPLACEMENTS:
        text = text.replace(old, new)
    for old, new in CONFIG_REPLACEMENTS:
        text = text.replace(old, new)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def patch_tree(root: Path) -> int:
    count = 0
    for path in root.rglob("*.py"):
        if patch_file(path):
            count += 1
    for path in root.rglob("*.md"):
        if patch_file(path):
            count += 1
    return count


def move_config_data() -> None:
    cfg = ROOT / "config"
    sim = cfg / "sim"
    sim.mkdir(exist_ok=True)
    for folder in ("species", "worlds"):
        src = cfg / folder
        dst = sim / folder
        if src.exists() and not dst.exists():
            shutil.move(str(src), str(dst))
            print(f"moved config/{folder} -> config/sim/{folder}")
    legacy = cfg / "game.json"
    if legacy.exists():
        legacy.unlink()
        print("removed config/game.json")


def main() -> None:
    move_config_data()
    move_dirs()
    move_files()
    n = patch_tree(ROOT / "src")
    n += patch_tree(ROOT / "tests")
    n += patch_tree(ROOT / "tools")
    n += patch_tree(ROOT / "docs")
    print(f"patched {n} files")


if __name__ == "__main__":
    main()
