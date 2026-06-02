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
    waves_cycled: bool
    all_waves_complete: bool


def get_phase_view(controller: "GameController", world: "World") -> GamePhaseView:
    pc = controller.phase_controller
    wd = controller.wave_director
    waves_total = len(wd.waves)
    all_complete = waves_total > 0 and pc.next_wave_index >= waves_total and not wd.wave_active
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
        waves_total=waves_total,
        next_wave_index=pc.next_wave_index,
        waves_cycled=pc.waves_cycled,
        all_waves_complete=all_complete,
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


# ============================================================
# Client 層向け Game 公開ヘルパー（Client/Game 並行開発のための境界）
# Client担当AIはここからしか Game の colony や特定の game ロジックにアクセスしない。
# Game担当AIは内部実装を変えても、この関数のシグネチャと戻り値を維持すれば Client を壊さない。
# ============================================================

def find_queen_reproduction_action(queen):
    """女王の産卵 Action を解決して返す。Client はこのクラスの詳細を知らない。"""
    if queen is None:
        return None
    mind = getattr(queen, "mind", None)
    if mind is None:
        return None
    for action_def in mind.action_defs:
        if action_def.get("name") == "AffiliationReproduceAction":
            # 内部 import は client_api 内に閉じる
            from src.sim.ai.mind import ACTION_BY_NAME
            from src.game.ai.reproduction_actions import AffiliationReproduceAction

            cls = ACTION_BY_NAME.get("AffiliationReproduceAction", AffiliationReproduceAction)
            return cls.from_config(
                action_def.get("params", {}),
                source=f"queen/{action_def.get('name')}",
            )
    return None


def get_queen_reproduction_readiness(queen) -> tuple[bool, str] | None:
    """女王の産卵可能状態を (ok, reason) で返す。
    queen.world から必要な Game/Sim データを解決。
    Client は reproduction_readiness の内部や AffiliationReproduceAction を直接触らない。
    """
    if queen is None or not getattr(queen, "world", None):
        return None
    repro = find_queen_reproduction_action(queen)
    if repro is None:
        return None
    try:
        return repro.reproduction_readiness(queen)
    except Exception:
        return None
