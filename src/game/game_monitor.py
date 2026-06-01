"""数値推移・閾値の監視（離散イベントとは別）。"""
from __future__ import annotations

from src.game.colony_session import get_colony_orchestrator


def colony(world):
    return get_colony_orchestrator(world)

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game.game_state import GameState
    from src.sim.systems.world import World


@dataclass(frozen=True)
class MonitorAlert:
    alert_id: str
    message: str


class GameMonitor:
    """プレイヤーコロニーの巣・個体数などを定期的に監視する。"""

    def __init__(self, settings: dict | None = None) -> None:
        self.settings = dict(settings or {})

    def check(self, world: "World", state: "GameState") -> list[MonitorAlert]:
        alerts: list[MonitorAlert] = []
        affiliation_id = state.player_affiliation_id
        if colony(world).get_affiliation_root(affiliation_id) is None:
            return alerts

        low_ratio = float(self.settings.get("low_fill_ratio", 0.10))
        fill_ratio = colony(world).affiliation_fill_ratio(affiliation_id)
        if fill_ratio < low_ratio:
            if state.set_flag("low_food_warned"):
                alerts.append(
                    MonitorAlert(
                        "low_food",
                        f"備蓄が {fill_ratio * 100:.0f}% まで低下しました",
                    )
                )
        elif fill_ratio >= low_ratio * 1.5:
            state.flags["low_food_warned"] = False

        high_ratio = float(self.settings.get("high_fill_ratio", 0.50))
        if fill_ratio >= high_ratio:
            if state.set_flag("high_food_reached"):
                alerts.append(
                    MonitorAlert(
                        "high_food",
                        f"備蓄が {fill_ratio * 100:.0f}% に達しました",
                    )
                )

        worker_species = self._affiliation_member_species(world, affiliation_id)
        if worker_species:
            count = colony(world).count_affiliation_members(affiliation_id, worker_species)
            milestone = int(self.settings.get("milestone_workers", 5))
            if count >= milestone and state.set_flag("workers_milestone"):
                alerts.append(
                    MonitorAlert(
                        "workers_milestone",
                        f"コロニー個体数が {count} 匹に達しました",
                    )
                )

        return alerts

    @staticmethod
    def _affiliation_member_species(world: "World", affiliation_id: str) -> list[str]:
        groups = getattr(world, "affiliation_species", {}) or getattr(world, "affiliation_species", {}) or {}
        names = list(groups.get(affiliation_id, []))
        if names:
            return [s for s in names if not s.endswith("_queen")]
        return []
