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


def get_sim_time_seconds(world: "World") -> float:
    """シミュレーション内時間（world._sim_time, dt累積）を秒として返す。"""
    return float(getattr(world, "_sim_time", 0.0))


def get_simulation_speed(sim_runner) -> float:
    """SimRunner の現在の加速倍率を返す（Client は SimRunner を保持している想定）。"""
    try:
        return float(sim_runner.get_simulation_speed())
    except Exception:
        return float(getattr(sim_runner, "simulation_speed", 1.0))


def set_simulation_speed(sim_runner, speed: float) -> float:
    """SimRunner の加速倍率を設定し、設定後の倍率を返す。"""
    try:
        sim_runner.set_simulation_speed(float(speed))
    except Exception:
        try:
            sim_runner.simulation_speed = float(speed)
        except Exception:
            pass
    return get_simulation_speed(sim_runner)


def acknowledge_story(controller: "GameController") -> None:
    """ストーリー画面の続行（Client 入力用）。"""
    controller.phase_controller.acknowledge_story()


def request_start_defense(controller: "GameController", world: "World | None" = None) -> bool:
    """開発フェーズから手動で防衛開始。成功時 True。"""
    pc = controller.phase_controller
    wd = controller.wave_director
    if world is None and controller.bridge is not None:
        world = controller.bridge.world
    if not pc.request_start_defense(wd, world):
        return False
    msgs = pc.start_defense_wave(wd)
    from src.game.game_message import stamp_messages

    w = world if world is not None else (controller.bridge.world if controller.bridge else None)
    controller.pending_messages.extend(stamp_messages(msgs, w))
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


@dataclass(frozen=True)
class TargetView:
    """HuntAction / CombatAction のターゲットを Client 描画・HUD 用に正規化したビュー。

    Client は creature / WorldObject / PickupTarget の区別を知らなくてよい。
    """

    kind: str  # "creature" | "carcass" | "field_biomass" | "other"
    name: str
    x: float
    y: float
    size: float
    is_creature: bool
    species_name: Optional[str] = None
    is_alive: bool = True


def _unwrap_action_target(target) -> object | None:
    """HuntAction._target 等（creature / WorldObject / PickupTarget）を描画用エンティティに正規化。"""
    if target is None:
        return None
    from src.sim.combat.pickup_target import PickupTarget

    if isinstance(target, PickupTarget):
        return target.world_object if target.world_object is not None else target
    return target


def _target_xy(raw_target, entity) -> tuple[float, float]:
    from src.sim.combat.pickup_target import PickupTarget
    from src.sim.utils.position_helpers import entity_xy

    if isinstance(raw_target, PickupTarget):
        return raw_target.position()
    return entity_xy(entity)


def _classify_target_kind(entity) -> str:
    from src.sim.entities.world_object import WorldObject
    from src.sim.utils.field_pickup_helpers import is_field_pickup

    if entity is None:
        return "other"
    species = getattr(entity, "species", None)
    if species is not None and hasattr(species, "name"):
        return "creature" if getattr(entity, "alive", True) else "carcass"
    if isinstance(entity, WorldObject):
        if is_field_pickup(entity):
            return "field_biomass"
        return "carcass"
    return "other"


def _target_display_name(entity, kind: str) -> str:
    from src.sim.utils.hunt_helpers import describe_creature_short

    if kind in ("creature", "carcass"):
        species = getattr(entity, "species", None)
        if species is not None and hasattr(species, "name"):
            try:
                return describe_creature_short(entity)
            except Exception:
                pass
    if kind == "field_biomass":
        label = getattr(entity, "label", None) or getattr(entity, "type_ref", None) or "biomass"
        try:
            ratio = float(entity.fill_ratio)
            return f"{label} (field {ratio * 100:.0f}%)"
        except Exception:
            return f"{label} (field)"
    name = getattr(entity, "label", None) or getattr(entity, "type_ref", None) or type(entity).__name__
    is_dead = not getattr(entity, "alive", True)
    status = "死骸" if is_dead else "対象"
    return f"{name} ({status})"


def _target_draw_size(entity, kind: str) -> float:
    traits = getattr(entity, "traits", None)
    if traits:
        return float(traits.get("base_size", 9))
    from src.sim.entities.world_object import WorldObject
    from src.sim.utils.field_pickup_helpers import is_field_pickup, pickup_radius

    if isinstance(entity, WorldObject) and is_field_pickup(entity):
        return pickup_radius(entity)
    radius = getattr(entity, "radius", None) or getattr(entity, "pickup_radius", None)
    if radius is not None:
        return float(radius)
    return 9.0


def _build_target_view(raw_target) -> TargetView | None:
    if raw_target is None:
        return None
    entity = _unwrap_action_target(raw_target)
    if entity is None:
        return None
    kind = _classify_target_kind(entity)
    is_creature = kind == "creature"
    species_name: str | None = None
    species = getattr(entity, "species", None)
    if species is not None and hasattr(species, "name"):
        species_name = str(species.name)
    try:
        x, y = _target_xy(raw_target, entity)
    except AttributeError:
        return None
    size = _target_draw_size(entity, kind)
    name = _target_display_name(entity, kind)
    is_alive = bool(getattr(entity, "alive", True))
    return TargetView(
        kind=kind,
        name=name,
        x=float(x),
        y=float(y),
        size=size,
        is_creature=is_creature,
        species_name=species_name,
        is_alive=is_alive,
    )


def get_hunt_target_view(creature) -> TargetView | None:
    """creature の HuntAction ターゲットを Client 向けビューで返す。対象なしなら None。"""
    from src.sim.utils.hunt_helpers import get_hunt_target

    return _build_target_view(get_hunt_target(creature))


def get_combat_target_view(creature) -> TargetView | None:
    """creature の CombatAction ターゲットを Client 向けビューで返す。対象なしなら None。"""
    from src.sim.utils.hunt_helpers import get_combat_target

    return _build_target_view(get_combat_target(creature))


def get_aggression_target_view(creature) -> TargetView | None:
    """戦闘または狩りで追っている対象のビュー（戦闘を優先）。"""
    from src.sim.utils.hunt_helpers import get_aggression_target

    return _build_target_view(get_aggression_target(creature))
