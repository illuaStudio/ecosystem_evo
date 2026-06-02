"""描画なしでシミュを高速回し、進行マイルストーンとイベントを記録する。

Client と同じ tick 配線（SimRunner + GameController.on_tick、ストーリー中は sim 停止）を使う。
防衛フェーズは **両方** を満たしたときに自動開始:
  - development_ticks_before_defense（既定 400 step）以上
  - min_soldiers_before_defense（既定 3 匹）以上の兵隊アリ

Usage:
  python tools/balance_run.py
  python tools/balance_run.py --steps 5000 --verbose
  python tools/balance_run.py --dev-ticks 50 --steps 2000
  python tools/balance_run.py --world Grassland --seed 42
"""
from __future__ import annotations

import argparse
import copy
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import config
from src.game import client_api
from src.game.game_controller import GameController
from src.game.phase_ai import count_alive_soldiers
from src.game.sim_bridge_factory import make_sim_bridge
from src.game.sim_runner import SimRunner
from src.sim.systems.world import World
from tools.dev_launcher_fields import default_sim_rate_context


def colony(world):
    return client_api.try_get_colony_orchestrator(world)


@dataclass
class MilestoneLog:
    sim_time: float
    real_sec_est: float
    step: int
    label: str
    detail: str = ""


@dataclass
class BalanceRunReport:
    steps: int = 0
    sim_time_end: float = 0.0
    real_sec_est_end: float = 0.0
    wall_sec: float = 0.0
    milestones: list[MilestoneLog] = field(default_factory=list)
    worker_count_end: int = 0
    soldier_count_end: int = 0
    nest_food_end: float = 0.0
    nest_fill_ratio_end: float = 0.0
    flags_end: dict[str, bool] = field(default_factory=dict)
    phase_end: str = "development"
    wave_index_end: int = -1
    waves_cleared: int = 0


def _sim_time(world: World) -> float:
    return float(getattr(world, "_sim_time", 0.0))


def _real_sec(sim_time: float, ctx) -> float:
    rate = ctx.dt_per_real_second
    if rate <= 0:
        return 0.0
    return sim_time / rate


def _worker_species(world: World, affiliation_id: str, soldier_species: tuple[str, ...]) -> list[str]:
    """働きアリ種のみ（女王・兵隊・ヴァンガードを除く）。"""
    factions = getattr(world, "affiliation_species", {}) or {}
    exclude = set(soldier_species)
    return [
        s
        for s in factions.get(affiliation_id, ["red_ant"])
        if not s.endswith("_queen")
        and not s.endswith("_vanguard")
        and s not in exclude
    ]


def _worker_count(
    world: World, affiliation_id: str, soldier_species: tuple[str, ...]
) -> int:
    orch = colony(world)
    if orch is None:
        return 0
    nest = orch.get_affiliation_root(affiliation_id)
    if nest is None:
        return 0
    species = _worker_species(world, affiliation_id, soldier_species)
    if not species:
        return 0
    return orch.count_affiliation_members(nest.id, species)


def _soldier_count(world: World, affiliation_id: str, soldier_species: tuple[str, ...]) -> int:
    return count_alive_soldiers(world, affiliation_id, soldier_species)


def _population_detail(
    world: World, affiliation_id: str, soldier_species: tuple[str, ...]
) -> str:
    workers = _worker_count(world, affiliation_id, soldier_species)
    soldiers = _soldier_count(world, affiliation_id, soldier_species)
    return f"workers={workers} soldiers={soldiers}"


def _maybe_log_milestone(
    report: BalanceRunReport,
    *,
    step: int,
    world: World,
    ctx,
    key: str,
    label: str,
    detail: str = "",
    seen: set[str],
) -> None:
    if key in seen:
        return
    seen.add(key)
    st = _sim_time(world)
    report.milestones.append(
        MilestoneLog(
            sim_time=st,
            real_sec_est=_real_sec(st, ctx),
            step=step,
            label=label,
            detail=detail,
        )
    )


def _game_config(*, dev_ticks: int | None, min_soldiers: int | None) -> dict:
    cfg = copy.deepcopy(config.game_player)
    if dev_ticks is not None or min_soldiers is not None:
        phases = dict(cfg.get("phases") or {})
        if dev_ticks is not None:
            phases["development_ticks_before_defense"] = max(1, int(dev_ticks))
        if min_soldiers is not None:
            phases["min_soldiers_before_defense"] = max(0, int(min_soldiers))
        cfg["phases"] = phases
    return cfg


def _log_phase_snapshot(
    report: BalanceRunReport,
    *,
    step: int,
    world: World,
    ctx,
    controller: GameController,
    seen: set[str],
) -> None:
    view = client_api.get_phase_view(controller, world)
    phase = view.phase
    if phase == "defense" and view.wave_active:
        key = f"defense_wave_{view.wave_index}"
        label = f"防衛フェーズ: {view.wave_label or view.wave_index + 1}"
        detail = f"enemies_alive={view.wave_enemies_alive} spawned={view.wave_enemies_spawned}"
        _maybe_log_milestone(
            report,
            step=step,
            world=world,
            ctx=ctx,
            key=key,
            label=label,
            detail=detail,
            seen=seen,
        )
    elif phase == "story" and view.story_pending:
        key = f"story_{view.next_wave_index}"
        snippet = (view.story_text or "")[:48]
        _maybe_log_milestone(
            report,
            step=step,
            world=world,
            ctx=ctx,
            key=key,
            label="ストーリーフェーズ",
            detail=snippet,
            seen=seen,
        )
    elif phase == "development" and view.waves_cycled:
        _maybe_log_milestone(
            report,
            step=step,
            world=world,
            ctx=ctx,
            key="dev_after_cycle",
            label="開発フェーズ（全ウェーブ周回後）",
            detail=f"next_wave={view.next_wave_index}",
            seen=seen,
        )


def run_balance(
    *,
    world_name: str = "Grassland",
    max_steps: int = 8000,
    verbose: bool = False,
    dev_ticks: int | None = None,
    min_soldiers: int | None = None,
) -> BalanceRunReport:
    config.reload_all()
    ctx = default_sim_rate_context()
    runner = SimRunner()

    world = World(world_name)
    bridge = make_sim_bridge(world)
    game_cfg = _game_config(dev_ticks=dev_ticks, min_soldiers=min_soldiers)
    controller = GameController(game_cfg, bridge=bridge)
    controller.reset_for_world(world, bridge=bridge)

    affiliation_id = controller.state.player_affiliation_id
    phases_cfg = dict(game_cfg.get("phases") or {})
    dev_before = int(phases_cfg.get("development_ticks_before_defense", 400))
    min_soldiers = int(phases_cfg.get("min_soldiers_before_defense", 3))
    soldier_species = tuple(phases_cfg.get("soldier_species") or ("red_ant_soldier",))
    milestone_workers = int((game_cfg.get("monitor") or {}).get("milestone_workers", 3))
    report = BalanceRunReport()
    seen_milestones: set[str] = set()
    prev_phase = controller.phase.value

    orch = colony(world)
    nest = orch.get_affiliation_root(affiliation_id) if orch is not None else None
    if nest is not None:
        _maybe_log_milestone(
            report,
            step=0,
            world=world,
            ctx=ctx,
            key="start",
            label="開始",
            detail=(
                f"food={nest.stored_mass:.0f}/{nest.capacity:.0f} "
                f"{_population_detail(world, affiliation_id, soldier_species)} "
                f"defense_when=step>={dev_before} AND soldiers>={min_soldiers}"
            ),
            seen=seen_milestones,
        )

    t0 = time.perf_counter()
    prev_workers = _worker_count(world, affiliation_id, soldier_species)
    prev_soldiers = _soldier_count(world, affiliation_id, soldier_species)

    for step in range(1, max_steps + 1):
        if client_api.should_advance_sim(controller):
            runner.tick(world)
        messages = controller.on_tick(world)

        phase_now = controller.phase.value
        if phase_now != prev_phase:
            labels = {
                "development": "開発フェーズ",
                "defense": "防衛フェーズ",
                "story": "ストーリーフェーズ",
            }
            pop = _population_detail(world, affiliation_id, soldier_species)
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key=f"phase_enter_{phase_now}_{step}",
                label=f"フェーズ: {labels.get(phase_now, phase_now)}",
                detail=f"from={prev_phase} {pop}",
                seen=seen_milestones,
            )
            prev_phase = phase_now

        if (
            controller.phase.value == "development"
            and controller.phase_controller.phase_ticks >= dev_before
        ):
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key="dev_threshold",
                label="開発 tick 閾値到達（兵隊待ち）",
                detail=(
                    f"phase_ticks={controller.phase_controller.phase_ticks} "
                    f"{_population_detail(world, affiliation_id, soldier_species)} "
                    f"(need soldiers>={min_soldiers})"
                ),
                seen=seen_milestones,
            )

        _log_phase_snapshot(
            report,
            step=step,
            world=world,
            ctx=ctx,
            controller=controller,
            seen=seen_milestones,
        )

        nest = orch.get_affiliation_root(affiliation_id) if orch is not None else None
        if nest is not None:
            ratio = nest.fill_ratio
            if controller.state.has_flag("high_food_reached"):
                _maybe_log_milestone(
                    report,
                    step=step,
                    world=world,
                    ctx=ctx,
                    key="high_food",
                    label="繁殖解禁 (high_food_reached)",
                    detail=f"food={nest.stored_mass:.0f} ratio={ratio:.2f}",
                    seen=seen_milestones,
                )
            if controller.state.has_flag("queen_can_reproduce"):
                _maybe_log_milestone(
                    report,
                    step=step,
                    world=world,
                    ctx=ctx,
                    key="queen_reproduce",
                    label="女王: 産卵 AI 適用",
                    seen=seen_milestones,
                )
            if controller.state.has_flag("queen_can_spawn_soldiers"):
                _maybe_log_milestone(
                    report,
                    step=step,
                    world=world,
                    ctx=ctx,
                    key="queen_soldiers",
                    label="女王: 兵隊アリ繁殖解禁",
                    seen=seen_milestones,
                )
            if controller.state.has_flag("first_reproduction"):
                _maybe_log_milestone(
                    report,
                    step=step,
                    world=world,
                    ctx=ctx,
                    key="first_repro",
                    label="最初の繁殖スポーン",
                    detail=_population_detail(world, affiliation_id, soldier_species),
                    seen=seen_milestones,
                )
            if controller.state.has_flag("first_item_found"):
                _maybe_log_milestone(
                    report,
                    step=step,
                    world=world,
                    ctx=ctx,
                    key="first_item",
                    label="初めての食料運搬",
                    seen=seen_milestones,
                )

        for msg in messages:
            if verbose and msg.text:
                st = _sim_time(world)
                print(
                    f"  [{_real_sec(st, ctx):6.1f}s sim={st:7.0f} step={step:5d}] "
                    f"{msg.source}: {msg.text}",
                    flush=True,
                )

        workers = _worker_count(world, affiliation_id, soldier_species)
        if workers > prev_workers:
            soldiers = _soldier_count(world, affiliation_id, soldier_species)
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key=f"worker_plus_{workers}",
                label=f"働きアリ +1 (合計 {workers})",
                detail=f"soldiers={soldiers}",
                seen=seen_milestones,
            )
        prev_workers = workers

        if workers >= 3:
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key="workers_3",
                label="働きアリ 3 匹以上",
                detail=f"workers={workers}",
                seen=seen_milestones,
            )
        if workers >= milestone_workers:
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key="workers_milestone",
                label=f"働きアリ {milestone_workers} 匹 (milestone_workers)",
                detail=f"workers={workers}",
                seen=seen_milestones,
            )

        soldiers = _soldier_count(world, affiliation_id, soldier_species)
        if soldiers > prev_soldiers:
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key=f"soldier_plus_{soldiers}",
                label=f"兵隊アリ +1 (合計 {soldiers})",
                detail=f"workers={workers}",
                seen=seen_milestones,
            )
        if soldiers >= min_soldiers and min_soldiers > 0:
            _maybe_log_milestone(
                report,
                step=step,
                world=world,
                ctx=ctx,
                key="soldiers_ready",
                label=f"兵隊アリ {min_soldiers} 匹以上（防衛開始可能）",
                detail=f"workers={workers} soldiers={soldiers}",
                seen=seen_milestones,
            )
        prev_soldiers = soldiers

    view = client_api.get_phase_view(controller, world)
    report.steps = max_steps
    report.sim_time_end = _sim_time(world)
    report.real_sec_est_end = _real_sec(report.sim_time_end, ctx)
    report.wall_sec = time.perf_counter() - t0
    report.worker_count_end = _worker_count(world, affiliation_id, soldier_species)
    report.soldier_count_end = _soldier_count(world, affiliation_id, soldier_species)
    report.flags_end = dict(controller.state.flags)
    report.phase_end = view.phase
    report.wave_index_end = view.wave_index
    report.waves_cleared = max(0, view.next_wave_index)
    if nest is not None:
        report.nest_food_end = nest.stored_mass
        report.nest_fill_ratio_end = nest.fill_ratio
    return report


def print_report(report: BalanceRunReport) -> None:
    ctx = default_sim_rate_context()
    print()
    print("=== Balance run ===")
    print(
        f"前提: {ctx.fps:g} FPS, 1 step = {ctx.sim_ticks_per_step:g} tick, "
        f"speed x{ctx.simulation_speed:g} "
        f"→ {ctx.dt_per_real_second:g} sim時間/実秒"
    )
    print(
        f"実行: {report.steps} steps, "
        f"wall {report.wall_sec:.2f}s, "
        f"sim時間 {report.sim_time_end:.0f} "
        f"(~ {report.real_sec_est_end:.1f} sec real-time equiv)"
    )
    print(
        f"終了: phase={report.phase_end} wave_index={report.wave_index_end} "
        f"waves_cleared={report.waves_cleared} "
        f"food={report.nest_food_end:.0f} ({report.nest_fill_ratio_end * 100:.1f}%), "
        f"働きアリ={report.worker_count_end}, 兵隊アリ={report.soldier_count_end}"
    )
    print()
    print("--- milestones ---")
    for m in report.milestones:
        extra = f"  {m.detail}" if m.detail else ""
        print(
            f"  {m.real_sec_est:7.1f}s  (sim={m.sim_time:7.0f}, step={m.step:5d})  "
            f"{m.label}{extra}"
        )
    if report.flags_end:
        on_flags = [k for k, v in sorted(report.flags_end.items()) if v]
        if on_flags:
            print()
            print("flags:", ", ".join(on_flags))


def main() -> int:
    parser = argparse.ArgumentParser(description="Headless balance simulation runner")
    parser.add_argument("--world", default="Grassland", help="World name (default: Grassland)")
    parser.add_argument("--steps", type=int, default=8000, help="Sim steps (default: 8000)")
    parser.add_argument(
        "--dev-ticks",
        type=int,
        default=None,
        help="Override development_ticks_before_defense (default: player.json)",
    )
    parser.add_argument(
        "--min-soldiers",
        type=int,
        default=None,
        help="Override min_soldiers_before_defense (default: player.json)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print game messages each step",
    )
    args = parser.parse_args()

    report = run_balance(
        world_name=args.world,
        max_steps=max(1, args.steps),
        verbose=args.verbose,
        dev_ticks=args.dev_ticks,
        min_soldiers=args.min_soldiers,
    )
    print_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
