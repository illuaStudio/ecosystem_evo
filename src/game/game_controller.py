"""ゲームレイヤー: tick 配線と Client 向け facade。"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.game.game_director import GameDirector
from src.game.game_message import GameMessage, stamp_messages, with_elapsed
from src.game.game_monitor import GameMonitor
from src.game.game_state import GameState
from src.game.phase_controller import PhaseController
from src.game.phases import GamePhase
from src.game.sim_bridge_factory import make_sim_bridge
from src.game.wave_director import WaveDirector
from src.sim.bridge import SimBridge
from src.game.colony_session import drain_game_events
from src.game.events import AffiliationDefeatedEvent
from src.sim.events import (
    AffiliationAllAccessRemovedEvent,
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
        self.phase_controller = PhaseController.from_config(self._config)
        self.wave_director = WaveDirector.from_json(
            player_affiliation_id=self.state.player_affiliation_id
        )
        from src.game.phase_ai import PhaseAIDirector

        self.phase_ai = PhaseAIDirector.from_game_config(self._config)
        self.pending_messages: list[GameMessage] = []
        self.user_message: str = ""
        self.debug_sim_events: bool = False

    def reset_for_world(
        self, world: "World | None" = None, bridge: SimBridge | None = None
    ) -> None:
        from src.config import config
        from src.game.sim_seed import apply_simulation_seed

        seed = config.sim.get("seed")
        if seed is not None:
            apply_simulation_seed(int(seed))

        if bridge is not None:
            self.bridge = bridge
            self.director.set_bridge(bridge)
        affiliation_id = str(self._config.get("player_affiliation_id", "red_ant"))
        self.state = GameState(player_affiliation_id=affiliation_id)
        self.director = GameDirector(self.state, self.bridge)
        self.phase_controller = PhaseController.from_config(self._config)
        self.wave_director = WaveDirector.from_json(
            player_affiliation_id=affiliation_id
        )
        from src.game.phase_ai import PhaseAIDirector

        self.phase_ai = PhaseAIDirector.from_game_config(self._config)
        self.phase_controller.reset()
        self.wave_director.reset()
        self.phase_ai.reset()
        self.pending_messages.clear()
        self.user_message = ""
        self.director.reset()
        if world is None or self.bridge is None:
            return
        from src.game.colony_orchestrator import ColonyOrchestrator
        from src.game.colony_session import attach_colony_orchestrator

        orch = ColonyOrchestrator(world)
        attach_colony_orchestrator(world, orch)
        # No more direct hook injection into World for layer independence.
        # Maintenance (leaks) and assignments are driven explicitly from game layer.
        self.director.on_world_start(world)
        # Process initial spawn events so that game reactions (affiliation assignment
        # etc.) happen in an event-driven way, even for creatures created during World init.
        initial_events = world.events.drain()
        self.director.on_sim_events(initial_events, world)

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

    def _ensure_affiliation_assignments(self, world: "World") -> None:
        """Ensure creatures with affiliation_data in their species get assigned.

        Delegates to the shared event-reaction logic in colony_session.
        Called at game tick points.
        """
        from src.game.colony_session import ensure_creature_affiliations

        ensure_creature_affiliations(world)

    def should_run_sim(self) -> bool:
        return self.phase_controller.should_run_sim()

    def request_start_defense(self, world: "World | None" = None) -> bool:
        if world is None and self.bridge is not None:
            world = self.bridge.world
        if not self.phase_controller.request_start_defense(self.wave_director, world):
            return False
        msgs = self.phase_controller.start_defense_wave(self.wave_director)
        stamped = stamp_messages(msgs, self.bridge.world if self.bridge else None)
        self.pending_messages.extend(stamped)
        return True

    def acknowledge_story(self) -> None:
        self.phase_controller.acknowledge_story()

    def _handle_phase_player_defeat(self, world: "World | None" = None) -> list[GameMessage]:
        if self.phase_controller.phase is not GamePhase.DEFENSE:
            return []
        if not self.state.has_flag("player_affiliation_defeated"):
            return []
        return self.phase_controller.on_player_defeated(self.wave_director, world)

    @property
    def phase(self) -> GamePhase:
        return self.phase_controller.phase

    def on_tick(self, world: "World") -> list[GameMessage]:
        self._ensure_affiliation_assignments(world)
        tick_messages: list[GameMessage] = []
        prev_phase = self.phase_controller.phase
        tick_messages.extend(
            self.phase_controller.on_tick(world, self.bridge, self.wave_director)
        )
        new_phase = self.phase_controller.phase
        if prev_phase is not new_phase:
            tick_messages.extend(
                self.phase_ai.on_phase_changed(
                    prev_phase, new_phase, world, self.bridge, self.state
                )
            )
        tick_messages.extend(
            self.phase_ai.on_tick(world, self.bridge, self.phase_controller, self.state)
        )
        events = world.events.drain()
        if self.debug_sim_events:
            for event in events:
                self._log_sim_event(event)

        tick_messages.extend(self.director.on_sim_events(events, world))

        # Drain game events AFTER processing sim events, so that side-effects
        # like emitting AffiliationDefeatedEvent from handling AllAccessRemoved
        # are captured in the same tick.
        game_events = drain_game_events(world)
        if self.debug_sim_events:
            for event in game_events:
                self._log_game_event(event)

        tick_messages.extend(self.director.on_game_events(game_events, world))
        tick_messages.extend(self._handle_phase_player_defeat(world))

        alerts = self.monitor.check(world, self.state)
        tick_messages.extend(self.director.on_monitor_alerts(alerts, world))

        self.director.update_derived_levels(world)
        tick_messages.extend(self.director.evaluate_unlocks(world))
        self.user_message = self.director.user_message
        tick_messages = stamp_messages(tick_messages, world)
        self.pending_messages.extend(tick_messages)
        if self.user_message:
            stamped = with_elapsed(self.user_message, world, source="game")
            self.user_message = stamped.text
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
            target_name = target.species.name if target is not None else None
            print(
                f"[sim] {name} {event.attacker_species} -> {target_name}",
                flush=True,
            )
        elif isinstance(event, AffiliationAllAccessRemovedEvent):
            print(f"[sim] {name} {event.affiliation_id}", flush=True)
        else:
            print(f"[sim] {name}", flush=True)

    @staticmethod
    def _log_game_event(event) -> None:
        name = type(event).__name__
        if isinstance(event, AffiliationDefeatedEvent):
            print(f"[game] {name} {event.affiliation_id}", flush=True)
        else:
            print(f"[game] {name}", flush=True)
