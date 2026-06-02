"""ゲーム進行: イベント解釈・監視反応・進行状態の更新。"""
from __future__ import annotations

from src.game.colony_session import get_colony_orchestrator


def colony(world):
    return get_colony_orchestrator(world)

from typing import TYPE_CHECKING

from src.game.command_builder import apply_spawn_profile
from src.game.game_message import GameMessage
from src.game.game_monitor import MonitorAlert
from src.game.game_state import GameState
from src.game.progression import ProgressionEvaluator
from src.game.events import AffiliationDefeatedEvent, GameEvent
from src.sim.events import (
    AffiliationAllAccessRemovedEvent,
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SimEvent,
    SpawnEvent,
)
from src.sim.utils.affiliation_group_helpers import is_rival_affiliation as is_rival_affiliation

if TYPE_CHECKING:
    from src.sim.bridge import SimBridge
    from src.sim.events import AffiliationAllAccessRemovedEvent
    from src.sim.systems.world import World


class GameDirector:
    """World の事実をゲーム進行として解釈し、SimBridge 指示・メッセージを生成する。"""

    def __init__(
        self,
        state: GameState,
        bridge: "SimBridge | None" = None,
        progression: ProgressionEvaluator | None = None,
    ) -> None:
        self.state = state
        self.bridge = bridge
        self.user_message: str = ""
        self.progression = progression or ProgressionEvaluator()

    def set_bridge(self, bridge: "SimBridge | None") -> None:
        self.bridge = bridge

    def reset(self) -> None:
        self.user_message = ""

    def on_world_start(self, world: "World") -> None:
        """ワールド開始時: スポーンプロファイル等の初期適用。"""
        if self.bridge is None:
            return
        from src.sim.utils.world_object_helpers import set_creature_nest_parent_ids

        parent_ids = self.state.nest_parent_object_ids
        if not parent_ids:
            parent_ids = (self.state.player_affiliation_id,)

        for creature in world.creatures:
            affiliation_data = getattr(creature.species, "affiliation_data", None) or {}
            inv = getattr(creature, "inventory", None)
            if affiliation_data.get("enabled") or (inv is not None and inv.slot_count > 0):
                set_creature_nest_parent_ids(creature, parent_ids)
            apply_spawn_profile(self.bridge, creature)

    def on_sim_events(
        self, events: list[SimEvent], world: "World"
    ) -> list[GameMessage]:
        messages: list[GameMessage] = []
        for event in events:
            messages.extend(self._handle_sim_event(world, event))
        return messages

    def on_game_events(
        self, events: list[GameEvent], world: "World"
    ) -> list[GameMessage]:
        _ = world
        messages: list[GameMessage] = []
        for event in events:
            if isinstance(event, AffiliationDefeatedEvent):
                messages.extend(self._on_affiliation_defeated(event))
        return messages

    def on_monitor_alerts(
        self, alerts: list[MonitorAlert], world: "World"
    ) -> list[GameMessage]:
        _ = world
        return [self._alert_to_message(alert) for alert in alerts]

    def update_derived_levels(self, world: "World") -> None:
        """危険度・安定度・文明度の更新。"""
        if self.state.has_flag("player_affiliation_defeated"):
            self.state.stability_level = 0.0
        else:
            root = colony(world).get_affiliation_root(self.state.player_affiliation_id)
            if root is None:
                self.state.stability_level = 0.0
            else:
                food_factor = min(
                    1.0,
                    colony(world).affiliation_fill_ratio(self.state.player_affiliation_id) / 0.5,
                )
                self.state.stability_level = max(0.0, min(1.0, 0.3 + food_factor * 0.7))

        danger = 0.0
        if self.state.has_flag("first_enemy_contact"):
            danger += 0.4
        if self.state.has_flag("low_food_warned"):
            danger += 0.3
        self.state.danger_level = min(1.0, danger)

        if self.state.has_flag("workers_milestone"):
            self.state.civilization_level = max(self.state.civilization_level, 1)

    def evaluate_unlocks(self, world: "World") -> list[GameMessage]:
        if self.bridge is None:
            return []
        return self.progression.evaluate(self.bridge, self.state, world)

    def _handle_sim_event(self, world: "World", event: SimEvent) -> list[GameMessage]:
        if isinstance(event, SpawnEvent):
            # Event-driven game reaction: assign affiliation if this spawn needs it.
            # This replaces direct hooks and the previous scan.
            from src.game.colony_session import ensure_creature_affiliations
            ensure_creature_affiliations(world)
            return self._on_spawn(world, event)
        if isinstance(event, DeathEvent):
            return self._on_death(world, event)
        if isinstance(event, ItemFoundEvent):
            return self._on_item_found(world, event)
        if isinstance(event, CombatStartedEvent):
            return self._on_combat_started(world, event)
        if isinstance(event, AffiliationAllAccessRemovedEvent):
            return self._on_affiliation_all_access_removed(world, event)
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
        if event.affiliation_id != self.state.player_affiliation_id:
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
        if event.affiliation_id != self.state.player_affiliation_id:
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
        if event.affiliation_id != self.state.player_affiliation_id:
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
        player_id = self.state.player_affiliation_id
        attacker_cid = event.attacker_affiliation_id
        if not attacker_cid or not is_rival_affiliation(world, player_id, attacker_cid):
            return []

        player_attacked = False
        if event.target_kind == "creature" and event.target_creature is not None:
            from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

            target_cid = get_creature_affiliation_id(event.target_creature)
            player_attacked = target_cid == player_id
        elif event.target_kind == "world_object":
            player_attacked = event.target_affiliation_id == player_id

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

    def _on_affiliation_defeated(self, event: AffiliationDefeatedEvent) -> list[GameMessage]:
        if event.affiliation_id == self.state.player_affiliation_id:
            self.user_message = event.message
            self.state.stability_level = 0.0
            self.state.set_flag("player_affiliation_defeated")
            return [
                GameMessage(
                    text=event.message,
                    source="event",
                    priority=10,
                )
            ]
        if self.state.set_flag(f"rival_defeated_{event.affiliation_id}"):
            return [
                GameMessage(
                    text=f"敵勢力 {event.affiliation_id} が滅びました",
                    source="event",
                )
            ]
        return []

    def _on_affiliation_all_access_removed(
        self, world: "World", event: "AffiliationAllAccessRemovedEvent"
    ) -> list[GameMessage]:
        """When sim reports all accesses for an affiliation are gone, trigger defeat logic."""
        _ = world
        try:
            from src.game.colony_session import get_colony_orchestrator

            orch = get_colony_orchestrator(world)
            orch.defeat_affiliation(event.affiliation_id)
        except Exception:
            pass
        return []
