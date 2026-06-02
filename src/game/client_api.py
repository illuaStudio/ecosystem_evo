"""Client 層が Game 状態を読むときの窓口（Sim 内部・Orchestrator 詳細を隠す）。"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.game.colony_orchestrator import ColonyOrchestrator
    from src.sim.systems.world import World


def get_defeated_affiliation_ids(world: "World") -> set[str]:
    """描画用: 敗北した affiliation_id の集合。"""
    from src.game.colony_session import get_defeated_affiliations

    return get_defeated_affiliations(world)


def try_get_colony_orchestrator(world: "World") -> Optional["ColonyOrchestrator"]:
    from src.game.colony_session import try_get_colony_orchestrator

    return try_get_colony_orchestrator(world)


def try_get_affiliation_fill_ratio(world: "World", affiliation_id: str) -> Optional[float]:
    """拠点備蓄率 0..1。Orchestrator 未登録時は None。"""
    orch = try_get_colony_orchestrator(world)
    if orch is None or not affiliation_id:
        return None
    try:
        return float(orch.affiliation_fill_ratio(str(affiliation_id)))
    except Exception:
        return None


def try_spawn_position(
    world: "World",
    species: str,
    affiliation_cfg: dict,
) -> tuple[float, float] | None:
    """デバッグスポーン用座標。Orchestrator 未登録時は None。"""
    orch = try_get_colony_orchestrator(world)
    if orch is None:
        return None
    try:
        x, y = orch.spawn_position(species, affiliation_cfg)
        return float(x), float(y)
    except Exception:
        return None
