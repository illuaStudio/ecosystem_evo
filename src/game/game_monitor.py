"""数値推移・閾値の監視（離散イベントとは別）。"""
from __future__ import annotations

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
        colony_id = state.player_colony_id
        nest = world.nest_system.get_colony_nest(colony_id)
        if nest is None:
            return alerts

        low_ratio = float(self.settings.get("low_food_ratio", 0.10))
        if nest.food_ratio < low_ratio:
            if state.set_flag("low_food_warned"):
                alerts.append(
                    MonitorAlert(
                        "low_food",
                        f"備蓄が {nest.food_ratio * 100:.0f}% まで低下しました",
                    )
                )
        elif nest.food_ratio >= low_ratio * 1.5:
            state.flags["low_food_warned"] = False

        high_ratio = float(self.settings.get("high_food_ratio", 0.50))
        if nest.food_ratio >= high_ratio:
            if state.set_flag("high_food_reached"):
                alerts.append(
                    MonitorAlert(
                        "high_food",
                        f"備蓄が {nest.food_ratio * 100:.0f}% に達しました",
                    )
                )

        worker_species = self._colony_member_species(world, colony_id)
        if worker_species:
            count = world.nest_system.count_colony_members(nest.id, worker_species)
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
    def _colony_member_species(world: "World", colony_id: str) -> list[str]:
        factions = getattr(world, "faction_species", {}) or {}
        names = list(factions.get(colony_id, []))
        if names:
            return [s for s in names if not s.endswith("_queen")]
        return []
