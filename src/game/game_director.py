"""ゲーム進行: イベント解釈・監視反応・進行状態の更新。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.game.command_builder import apply_spawn_profile
from src.game.game_message import GameMessage
from src.game.game_monitor import MonitorAlert
from src.game.game_state import GameState
from src.sim.events import (
    ColonyDefeatedEvent,
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SimEvent,
    SpawnEvent,
)
from src.sim.utils.colony_helpers import is_rival_colony

if TYPE_CHECKING:
    from src.sim.bridge import SimBridge
    from src.sim.systems.world import World


class GameDirector:
    """World の事実をゲーム進行として解釈し、SimBridge 指示・メッセージを生成する。"""

    def __init__(
        self,
        state: GameState,
        bridge: "SimBridge | None" = None,
    ) -> None:
        self.state = state
        self.bridge = bridge
        self.user_message: str = ""

    def set_bridge(self, bridge: "SimBridge | None") -> None:
        self.bridge = bridge

    def reset(self) -> None:
        self.user_message = ""

    def on_world_start(self, world: "World") -> None:
        """ワールド開始時: スポーンプロファイル等の初期適用。"""
        if self.bridge is None:
            return
        for creature in world.creatures:
            apply_spawn_profile(self.bridge, creature)

    def on_sim_events(
        self, events: list[SimEvent], world: "World"
    ) -> list[GameMessage]:
        messages: list[GameMessage] = []
        for event in events:
            messages.extend(self._handle_sim_event(world, event))
        return messages

    def on_monitor_alerts(
        self, alerts: list[MonitorAlert], world: "World"
    ) -> list[GameMessage]:
        _ = world
        return [self._alert_to_message(alert) for alert in alerts]

    def update_derived_levels(self, world: "World") -> None:
        """危険度・安定度・文明度の更新。"""
        nest = world.nest_system.get_colony_nest(self.state.player_colony_id)
        if nest is None:
            self.state.stability_level = 0.0
            return

        food_factor = min(1.0, nest.food_ratio / 0.5)
        self.state.stability_level = max(0.0, min(1.0, 0.3 + food_factor * 0.7))

        danger = 0.0
        if self.state.has_flag("first_enemy_contact"):
            danger += 0.4
        if self.state.has_flag("low_food_warned"):
            danger += 0.3
        self.state.danger_level = min(1.0, danger)

        if self.state.has_flag("workers_milestone"):
            self.state.civilization_level = max(self.state.civilization_level, 1)

    def _handle_sim_event(self, world: "World", event: SimEvent) -> list[GameMessage]:
        if isinstance(event, SpawnEvent):
            return self._on_spawn(world, event)
        if isinstance(event, DeathEvent):
            return self._on_death(world, event)
        if isinstance(event, ItemFoundEvent):
            return self._on_item_found(world, event)
        if isinstance(event, CombatStartedEvent):
            return self._on_combat_started(world, event)
        if isinstance(event, ColonyDefeatedEvent):
            return self._on_colony_defeated(event)
        return []

    @staticmethod
    def _alert_to_message(alert: MonitorAlert) -> GameMessage:
        return GameMessage(
            text=alert.message,
            source="monitor",
            priority=1 if alert.alert_id == "low_food" else 0,
        )

    def _on_spawn(self, world: "World", event: SpawnEvent) -> list[GameMessage]:
        _ = world
        if event.source != "reproduction":
            return []
        if event.colony_id != self.state.player_colony_id:
            return []
        if not self.state.set_flag("first_reproduction"):
            return []
        return [
            GameMessage(
                text="女王が新しい働きアリを産みました",
                source="event",
            )
        ]

    def _on_death(self, world: "World", event: DeathEvent) -> list[GameMessage]:
        _ = world
        if event.colony_id != self.state.player_colony_id:
            return []
        if event.species_name.endswith("_queen"):
            return [
                GameMessage(
                    text="女王が倒れました",
                    source="event",
                    priority=10,
                )
            ]
        return []

    def _on_item_found(self, world: "World", event: ItemFoundEvent) -> list[GameMessage]:
        _ = world
        if event.colony_id != self.state.player_colony_id:
            return []
        if not self.state.set_flag("first_item_found"):
            return []
        return [
            GameMessage(
                text="働きアリが食料を見つけました",
                source="event",
            )
        ]

    def _on_combat_started(
        self, world: "World", event: CombatStartedEvent
    ) -> list[GameMessage]:
        player_id = self.state.player_colony_id
        attacker_cid = event.attacker_colony_id
        if not attacker_cid or not is_rival_colony(world, player_id, attacker_cid):
            return []

        player_attacked = False
        if event.target_kind == "creature" and event.target_creature is not None:
            from src.sim.utils.colony_helpers import get_creature_colony_id

            target_cid = get_creature_colony_id(event.target_creature)
            player_attacked = target_cid == player_id
        elif event.target_kind == "spawn_node":
            player_attacked = event.target_colony_id == player_id

        if not player_attacked:
            return []
        if not self.state.set_flag("first_enemy_contact"):
            return []
        return [
            GameMessage(
                text="外敵との戦闘が始まりました",
                source="event",
                priority=2,
            )
        ]

    def _on_colony_defeated(self, event: ColonyDefeatedEvent) -> list[GameMessage]:
        if event.colony_id == self.state.player_colony_id:
            self.user_message = event.message
            self.state.stability_level = 0.0
            return [
                GameMessage(
                    text=event.message,
                    source="event",
                    priority=10,
                )
            ]
        if self.state.set_flag(f"rival_defeated_{event.colony_id}"):
            return [
                GameMessage(
                    text=f"敵勢力 {event.colony_id} が滅びました",
                    source="event",
                )
            ]
        return []
