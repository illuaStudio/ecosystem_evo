"""ゲームレイヤー: tick 配線と Client 向け facade。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.game.game_director import GameDirector
from src.game.game_message import GameMessage
from src.game.game_monitor import GameMonitor
from src.game.game_state import GameState
from src.game.sim_bridge_factory import make_sim_bridge
from src.sim.bridge import SimBridge
from src.game.colony_session import drain_game_events
from src.game.events import AffiliationDefeatedEvent
from src.sim.events import (
    CombatStartedEvent,
    DeathEvent,
    ItemFoundEvent,
    SimEvent,
    SpawnEvent,
)

if TYPE_CHECKING:
    from src.sim.systems.world import World


class GameController:
    """Client 向け窓口。tick 配線はここ、進行ロジックは GameDirector に委譲。"""

    def __init__(
        self,
        game_config: dict | None = None,
        bridge: SimBridge | None = None,
    ) -> None:
        if game_config is None:
            from src.config import config

            game_config = config.game_player
        self._config = dict(game_config)
        affiliation_id = str(self._config.get("player_affiliation_id", "red_ant"))
        self.state = GameState(player_affiliation_id=affiliation_id)
        self.monitor = GameMonitor(self._config.get("monitor"))
        self.bridge = bridge
        self.director = GameDirector(self.state, bridge)
        self.pending_messages: list[GameMessage] = []
        self.user_message: str = ""
        self.debug_sim_events: bool = False

    def reset_for_world(
        self, world: "World | None" = None, bridge: SimBridge | None = None
    ) -> None:
        if bridge is not None:
            self.bridge = bridge
            self.director.set_bridge(bridge)
        affiliation_id = str(self._config.get("player_affiliation_id", "red_ant"))
        self.state = GameState(player_affiliation_id=affiliation_id)
        self.director = GameDirector(self.state, self.bridge)
        self.pending_messages.clear()
        self.user_message = ""
        self.director.reset()
        if world is None or self.bridge is None:
            return
        from src.game.colony_orchestrator import ColonyOrchestrator
        from src.game.colony_session import attach_colony_orchestrator

        orch = ColonyOrchestrator(world)
        attach_colony_orchestrator(world, orch)
        world.on_sim_tick = orch.update
        self.director.on_world_start(world)
        world.events.drain()

    def spawn_creature(
        self,
        species: str,
        *,
        x: float | None = None,
        y: float | None = None,
        source: str = "game",
    ):
        from src.game.command_builder import spawn_creature as bridge_spawn

        if self.bridge is None:
            return None
        return bridge_spawn(self.bridge, species, x=x, y=y, source=source)

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
        affiliation_id: str | None = None,
        mode: str = "replace",
    ) -> int:
        from src.game.command_builder import apply_mind_profile_to_species

        if self.bridge is None:
            return 0
        return apply_mind_profile_to_species(
            self.bridge,
            species_name,
            profile_id,
            affiliation_id=affiliation_id,
            mode=mode,
        )

    def apply_mind_profile_to_affiliation_caste(
        self,
        affiliation_id: str,
        caste: str,
        profile_id: str,
        *,
        mode: str = "replace",
    ) -> int:
        from src.game.command_builder import apply_mind_profile_to_affiliation_caste

        if self.bridge is None:
            return 0
        return apply_mind_profile_to_affiliation_caste(
            self.bridge,
            affiliation_id,
            caste,
            profile_id,
            mode=mode,
        )

    def on_tick(self, world: "World") -> list[GameMessage]:
        events = world.events.drain()
        game_events = drain_game_events(world)
        if self.debug_sim_events:
            for event in events:
                self._log_sim_event(event)
            for event in game_events:
                self._log_game_event(event)

        tick_messages: list[GameMessage] = []
        tick_messages.extend(self.director.on_sim_events(events, world))
        tick_messages.extend(self.director.on_game_events(game_events, world))

        alerts = self.monitor.check(world, self.state)
        tick_messages.extend(self.director.on_monitor_alerts(alerts, world))

        self.director.update_derived_levels(world)
        tick_messages.extend(self.director.evaluate_unlocks(world))
        self.user_message = self.director.user_message
        self.pending_messages.extend(tick_messages)
        return tick_messages

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
                target.species.name if target is not None else event.target_affiliation_id
            )
            print(
                f"[sim] {name} {event.attacker_species} -> {target_name}",
                flush=True,
            )
        else:
            print(f"[sim] {name}", flush=True)

    @staticmethod
    def _log_game_event(event) -> None:
        name = type(event).__name__
        if isinstance(event, AffiliationDefeatedEvent):
            print(f"[game] {name} {event.affiliation_id}", flush=True)
        else:
            print(f"[game] {name}", flush=True)
