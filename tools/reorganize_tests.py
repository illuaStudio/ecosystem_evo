"""tests/ を sim / game / client サブディレクトリへ整理する。"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

SIM_TESTS = [
    "test_smoke.py",
    "test_sim_dt.py",
    "test_sim_events.py",
    "test_ant_nest.py",
    "test_chunk_carry.py",
    "test_combat_action.py",
    "test_combat_targets.py",
    "test_corpse_decompose.py",
    "test_feed_at_nest_stuck.py",
    "test_field_effects.py",
    "test_hole_combat.py",
    "test_hunger_behavior.py",
    "test_hunt_carcass_stuck.py",
    "test_hunt_helpers.py",
    "test_inventory.py",
    "test_mana_steering.py",
    "test_mana_wander.py",
    "test_movement_standoff.py",
    "test_nest_holes.py",
    "test_population_cap.py",
    "test_seek_shelter.py",
    "test_spider.py",
    "test_territory_soldier.py",
    "test_three_factions.py",
    "test_trait_variance.py",
    "test_wander_bounds.py",
]

GAME_TESTS = [
    "test_game_controller.py",
    "test_queen_mind_policy.py",
]

CLIENT_TESTS = [
    "test_camera_pan.py",
    "test_species_visibility.py",
]

LAYOUT = {
    "sim": SIM_TESTS,
    "game": GAME_TESTS,
    "client": CLIENT_TESTS,
}


def main() -> None:
    for subdir in LAYOUT:
        (TESTS / subdir).mkdir(exist_ok=True)
        init = TESTS / subdir / "__init__.py"
        if not init.exists():
            init.write_text("", encoding="utf-8")

    moved = 0
    for subdir, names in LAYOUT.items():
        for name in names:
            src = TESTS / name
            dst = TESTS / subdir / name
            if not src.exists():
                if dst.exists():
                    continue
                print(f"missing: {name}")
                continue
            if dst.exists():
                src.unlink()
                print(f"already in {subdir}/: {name}")
                continue
            shutil.move(str(src), str(dst))
            print(f"{name} -> {subdir}/")
            moved += 1

    print(f"moved {moved} files")


if __name__ == "__main__":
    main()
