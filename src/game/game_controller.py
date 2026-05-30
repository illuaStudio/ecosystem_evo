"""ゲームレイヤー: シミュイベントの解釈と数値監視の統合。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from src.game.command_builder import apply_spawn_profile
from src.game.game_monitor import GameMonitor, MonitorAlert
from src.game.game_state import GameState
from src.sim.bridge import SimBridge
from src.sim.events import (
    ColonyDefeatedEvent,
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SimEvent,
    SpawnEvent,
)
from src.sim.utils.colony_helpers import get_rival_colony_ids, is_rival_colony

if TYPE_CHECKING:
    from src.sim.systems.world import World


@dataclass
class GameMessage:
    text: str
    source: str = "game"
    priority: int = 0


class GameController:
    """World の事実をゲームとして解釈し、UI 向けメッセージを生成する。"""

    def __init__(
        self,
        game_config: dict | None = None,
        bridge: SimBridge | None = None,
    ) -> None:
        if game_config is None:
            from src.config import config

            game_config = config.game_player
        self._config = dict(game_config)
        colony_id = str(self._config.get("player_colony_id", "red_ant"))
        self.state = GameState(player_colony_id=colony_id)
        self.monitor = GameMonitor(self._config.get("monitor"))
        self.bridge = bridge
        self.pending_messages: list[GameMessage] = []
        self.user_message: str = ""
        self.debug_sim_events: bool = False

    def reset_for_world(
        self, world: "World | None" = None, bridge: SimBridge | None = None
    ) -> None:
        if bridge is not None:
            self.bridge = bridge
        colony_id = str(self._config.get("player_colony_id", "red_ant"))
        self.state = GameState(player_colony_id=colony_id)
        self.pending_messages.clear()
        self.user_message = ""
        if world is None or self.bridge is None:
            return
        for creature in world.creatures:
            apply_spawn_profile(self.bridge, creature)
        world.events.drain()

    def spawn_creature(
        self,
        species: str,
        *,
        x: float | None = None,
        y: float | None = None,
        source: str = "game",
    ):
        """Bridge 経由で生物をスポーン（座標省略時はランダム）。"""
        from src.game.command_builder import spawn_creature as bridge_spawn

        if self.bridge is None:
            return None
        return bridge_spawn(
            self.bridge, species, x=x, y=y, source=source
        )

    def apply_mind_profile(self, creature, profile_id: str, *, mode: str = "replace") -> bool:
        from src.game.command_builder import apply_mind_profile as bridge_apply

        if self.bridge is None:
            return False
        return bridge_apply(self.bridge, creature, profile_id, mode=mode)

    def apply_mind_profile_to_species(
        self,
        species_name: str,
        profile_id: str,
        *,
        colony_id: str | None = None,
        mode: str = "replace",
    ) -> int:
        from src.game.command_builder import apply_mind_profile_to_species

        if self.bridge is None:
            return 0
        return apply_mind_profile_to_species(
            self.bridge,
            species_name,
            profile_id,
            colony_id=colony_id,
            mode=mode,
        )

    def apply_mind_profile_to_colony_caste(
        self,
        colony_id: str,
        caste: str,
        profile_id: str,
        *,
        mode: str = "replace",
    ) -> int:
        from src.game.command_builder import apply_mind_profile_to_colony_caste

        if self.bridge is None:
            return 0
        return apply_mind_profile_to_colony_caste(
            self.bridge,
            colony_id,
            caste,
            profile_id,
            mode=mode,
        )

    def on_tick(self, world: "World") -> list[GameMessage]:
        """1 シミュ tick 分のイベント処理と監視。返値は当 tick の新規メッセージ。"""
        tick_messages: list[GameMessage] = []

        for event in world.events.drain():
            if self.debug_sim_events:
                self._log_sim_event(event)
            tick_messages.extend(self._handle_sim_event(world, event))

        for alert in self.monitor.check(world, self.state):
            tick_messages.extend(self._handle_monitor_alert(alert))

        self._update_derived_levels(world)
        self.pending_messages.extend(tick_messages)
        return tick_messages

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

    def _handle_monitor_alert(self, alert: MonitorAlert) -> list[GameMessage]:
        return [
            GameMessage(
                text=alert.message,
                source="monitor",
                priority=1 if alert.alert_id == "low_food" else 0,
            )
        ]

    def _on_spawn(self, world: "World", event: SpawnEvent) -> list[GameMessage]:
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

    def _update_derived_levels(self, world: "World") -> None:
        """危険度・安定度の簡易更新（プレースホルダ）。"""
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

    @staticmethod
    def _log_sim_event(event: SimEvent) -> None:
        name = type(event).__name__
        if isinstance(event, SpawnEvent):
            print(
                f"[sim] {name} {event.species_name} source={event.source}",
                flush=True,
            )
        elif isinstance(event, DeathEvent):
            print(
                f"[sim] {name} {event.species_name} cause={event.cause}",
                flush=True,
            )
        elif isinstance(event, ItemFoundEvent):
            print(
                f"[sim] {name} {event.species_name} amount={event.amount:.1f}",
                flush=True,
            )
        elif isinstance(event, CombatStartedEvent):
            target = event.target_creature
            target_name = (
                target.species.name if target is not None else event.target_colony_id
            )
            print(
                f"[sim] {name} {event.attacker_species} -> {target_name}",
                flush=True,
            )
        elif isinstance(event, ColonyDefeatedEvent):
            print(f"[sim] {name} {event.colony_id}", flush=True)
        else:
            print(f"[sim] {name}", flush=True)
