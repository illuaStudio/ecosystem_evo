"""プレイヤー女王の HUD 表示用ヘルパー（Client 層）。"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.game_state import GameState
    from src.sim.systems.world import World

Color = tuple[int, int, int]
Line = tuple[str, Color]

ACTION_LABELS = {
    "FeedAtNestAction": "巣で食事",
    "AffiliationReproduceAction": "産卵",
    "SeekShelterAction": "巣穴待機",
}


def find_colony_queen(world: "World", affiliation_id: str):
    alive = None
    for creature in world.creatures:
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        if get_creature_affiliation_id(creature) != affiliation_id:
            continue
        if not creature.species.name.endswith("_queen"):
            continue
        if creature.alive:
            return creature
        if alive is None:
            alive = creature
    return alive


def _find_colony_reproduce_action(queen):
    from src.sim.ai.mind import ACTION_BY_NAME
    from src.sim.ai.actions.reproduction import AffiliationReproduceAction

    mind = getattr(queen, "mind", None)
    if mind is None:
        return None
    for action_def in mind.action_defs:
        if action_def.get("name") == "AffiliationReproduceAction":
            cls = ACTION_BY_NAME.get("AffiliationReproduceAction", AffiliationReproduceAction)
            return cls.from_config(
                action_def.get("params", {}),
                source=f"queen/{action_def.get('name')}",
            )
    return None


def _progression_label(state: "GameState") -> str:
    if state.has_flag("queen_can_spawn_soldiers"):
        return "進行: 働きアリ + 兵隊アリを産卵"
    if state.has_flag("queen_can_reproduce"):
        return "進行: 働きアリを産卵"
    if state.has_flag("high_food_reached"):
        return "進行: 繁殖解禁処理中"
    return "進行: 備蓄50%で繁殖解禁"


def _next_goal(state: "GameState", world: "World", affiliation_id: str) -> str | None:
    from src.config import config

    monitor = (config.game_player or {}).get("monitor") or {}
    if not state.has_flag("high_food_reached"):
        pct = int(float(monitor.get("high_food_ratio", 0.50)) * 100)
        return f"目標: 備蓄 {pct}% 以上"
    if not state.has_flag("queen_can_reproduce"):
        return "目標: 繁殖解禁"
    if not state.has_flag("workers_milestone"):
        milestone = int(monitor.get("milestone_workers", 5))
        return f"目標: 働きアリ {milestone} 匹"
    if not state.has_flag("queen_can_spawn_soldiers"):
        return "目標: 兵隊アリ解禁"
    return None


def _worker_count(world: "World", affiliation_id: str) -> int | None:
    nest = world.nest_system.get_affiliation_root(affiliation_id)
    if nest is None:
        return None
    groups = getattr(world, "affiliation_species", {}) or {}
    names = [s for s in groups.get(affiliation_id, []) if not str(s).endswith("_queen")]
    if not names:
        return None
    return world.nest_system.count_affiliation_members(nest.id, names)


def build_queen_panel_lines(
    world: "World",
    affiliation_id: str,
    game_state: "GameState | None" = None,
) -> list[Line]:
    queen = find_colony_queen(world, affiliation_id)
    if queen is None:
        return [("女王: 見つかりません", (255, 140, 140))]

    title_color = (255, 200, 160)
    if not queen.alive:
        return [("【女王】", title_color), ("状態: 死亡", (255, 100, 100))]

    from src.sim.shelter.state import is_creature_sheltered
    from src.sim.utils.creature_helpers import format_nutrition_status, needs_self_feed

    lines: list[Line] = [
        ("【女王】", title_color),
        (f"HP: {queen.hp:.0f}/{queen.max_hp:.0f}", (220, 230, 220)),
        (format_nutrition_status(queen), (220, 230, 220)),
    ]

    if is_creature_sheltered(queen):
        lines.append(("所在: 巣穴内（非表示）", (180, 200, 255)))
    else:
        lines.append(("所在: 巣外", (255, 200, 120)))

    action = queen.current_action
    if action is not None:
        name = type(action).__name__
        label = ACTION_LABELS.get(name, name)
        lines.append((f"行動: {label}", (200, 255, 200)))

    if game_state is not None:
        lines.append((_progression_label(game_state), (255, 220, 140)))
        goal = _next_goal(game_state, world, affiliation_id)
        if goal is not None:
            lines.append((goal, (180, 210, 255)))

    nest = world.nest_system.get_creature_nest(queen)
    if nest is not None:
        lines.append(
            (
                f"巣 食料: {nest.stored_food:.0f}/{nest.max_food:.0f} "
                f"({nest.food_ratio * 100:.0f}%)",
                (200, 230, 200),
            )
        )

    workers = _worker_count(world, affiliation_id)
    if workers is not None:
        lines.append((f"コロニー: {workers} 匹（女王除く）", (200, 230, 200)))

    repro = _find_colony_reproduce_action(queen)
    if repro is not None:
        if queen.repro_cooldown > 0:
            lines.append(
                (f"産卵CD: 残り {queen.repro_cooldown} tick", (180, 180, 255))
            )
        ok, reason = repro.reproduction_readiness(queen)
        color: Color = (160, 255, 160) if ok else (255, 200, 160)
        lines.append((f"産卵: {reason}", color))
    elif game_state is not None and not game_state.has_flag("queen_can_reproduce"):
        lines.append(("産卵: ゲーム進行待ち", (200, 200, 200)))

    if needs_self_feed(queen):
        lines.append(("⚠ 自身の栄養補給が必要", (255, 180, 120)))

    return lines
