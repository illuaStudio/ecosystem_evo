"""Client 層が Game 状態を読むときの窓口（Sim 内部・Orchestrator 詳細を隠す）。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from src.game.colony_orchestrator import ColonyOrchestrator
    from src.game.game_controller import GameController
    from src.sim.systems.world import World


@dataclass(frozen=True)
class GamePhaseView:
    """HUD / フェーズ UI 用スナップショット（Client はこの型だけ参照）。"""

    phase: str
    phase_ticks: int
    wave_index: int
    wave_label: str
    wave_active: bool
    wave_enemies_alive: int
    wave_enemies_spawned: int
    story_text: str
    story_pending: bool
    waves_total: int
    next_wave_index: int


def get_phase_view(controller: "GameController", world: "World") -> GamePhaseView:
    pc = controller.phase_controller
    wd = controller.wave_director
    return GamePhaseView(
        phase=pc.phase.value,
        phase_ticks=pc.phase_ticks,
        wave_index=wd.wave_index,
        wave_label=wd.wave_label,
        wave_active=wd.wave_active,
        wave_enemies_alive=wd.enemies_alive(world) if wd.wave_active or wd.enemies_spawned_total else 0,
        wave_enemies_spawned=wd.enemies_spawned_total,
        story_text=pc.story_text,
        story_pending=pc.story_pending,
        waves_total=len(wd.waves),
        next_wave_index=pc.next_wave_index,
    )


def should_advance_sim(controller: "GameController") -> bool:
    """ストーリーフェーズなど、シミュを止めるとき False。"""
    return controller.phase_controller.should_run_sim()


def acknowledge_story(controller: "GameController") -> None:
    """ストーリー画面の続行（Client 入力用）。"""
    controller.phase_controller.acknowledge_story()


def request_start_defense(controller: "GameController") -> bool:
    """開発フェーズから手動で防衛開始。成功時 True。"""
    pc = controller.phase_controller
    wd = controller.wave_director
    if not pc.request_start_defense(wd):
        return False
    msgs = pc.start_defense_wave(wd)
    controller.pending_messages.extend(msgs)
    return True


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
