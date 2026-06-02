"""フェーズに応じた AI 差し替え（女王・条件付き遷移の補助）。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.game.caste_helpers import creature_matches_affiliation_caste
from src.game.game_message import GameMessage
from src.game.phases import GamePhase

if TYPE_CHECKING:
    from src.game.game_state import GameState
    from src.game.phase_controller import PhaseController
    from src.sim.bridge import SimBridge
    from src.sim.systems.world import World


def count_alive_soldiers(
    world: "World",
    affiliation_id: str,
    soldier_species: tuple[str, ...],
) -> int:
    if not soldier_species:
        return sum(
            1
            for creature in getattr(world, "creatures", ()) or ()
            if getattr(creature, "alive", False)
            and creature_matches_affiliation_caste(creature, affiliation_id, "soldier")
        )
    names = set(soldier_species)
    count = 0
    for creature in getattr(world, "creatures", ()) or ():
        if not getattr(creature, "alive", False):
            continue
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        if get_creature_affiliation_id(creature) != affiliation_id:
            continue
        if creature.species.name in names:
            count += 1
    return count


def find_colony_queen(world: "World", affiliation_id: str):
    queen = None
    fallback = None
    for creature in getattr(world, "creatures", ()) or ():
        from src.sim.utils.affiliation_helpers import get_creature_affiliation_id

        if get_creature_affiliation_id(creature) != affiliation_id:
            continue
        if not creature.species.name.endswith("_queen"):
            continue
        if creature.alive:
            return creature
        if fallback is None:
            fallback = creature
    return queen


def resolve_queen_reproduction_profile(state: "GameState") -> str:
    if state.has_flag("queen_can_spawn_soldiers"):
        return "queen_feed_and_soldiers"
    if state.has_flag("queen_can_reproduce"):
        return "queen_feed_and_workers"
    return "survival_feed_only"


@dataclass
class PhaseAIConfig:
    min_soldiers_before_defense: int = 3
    soldier_species: tuple[str, ...] = ("red_ant_soldier",)
    wave_enemy_species: tuple[str, ...] = ("invader_ant",)
    queen_combat_profile: str = "queen_defense_combat"
    queen_shelter_profile: str = "queen_post_defense"
    queen_combat_max_hp: float = 2800.0
    queen_combat_base_size: float = 26.0


def phase_ai_config_from_dict(raw: dict | None, phases: dict | None = None) -> PhaseAIConfig:
    data = dict(phases or raw or {})
    species = data.get("soldier_species") or ["red_ant_soldier"]
    wave_enemies = data.get("wave_enemy_species") or ["invader_ant"]
    return PhaseAIConfig(
        min_soldiers_before_defense=max(0, int(data.get("min_soldiers_before_defense", 3))),
        soldier_species=tuple(str(s) for s in species),
        wave_enemy_species=tuple(str(s) for s in wave_enemies),
        queen_combat_profile=str(data.get("queen_combat_profile", "queen_defense_combat")),
        queen_shelter_profile=str(data.get("queen_shelter_profile", "queen_post_defense")),
        queen_combat_max_hp=max(100.0, float(data.get("queen_combat_max_hp", 2800.0))),
        queen_combat_base_size=max(1.0, float(data.get("queen_combat_base_size", 26.0))),
    )


@dataclass
class PhaseAIDirector:
    config: PhaseAIConfig = field(default_factory=PhaseAIConfig)
    player_affiliation_id: str = "red_ant"
    _queen_combat_active: bool = False
    _saved_queen_max_hp: float | None = None
    _saved_queen_hp: float | None = None
    _saved_queen_base_size: float | None = None
    _reproduction_profile_id: str = "survival_feed_only"

    @classmethod
    def from_game_config(cls, game_config: dict | None) -> "PhaseAIDirector":
        data = dict(game_config or {})
        affiliation_id = str(data.get("player_affiliation_id", "red_ant"))
        return cls(
            config=phase_ai_config_from_dict(data.get("phases")),
            player_affiliation_id=affiliation_id,
        )

    def reset(self) -> None:
        self._queen_combat_active = False
        self._saved_queen_max_hp = None
        self._saved_queen_hp = None
        self._saved_queen_base_size = None
        self._reproduction_profile_id = "survival_feed_only"

    def soldiers_ready(self, world: "World") -> bool:
        return (
            count_alive_soldiers(
                world, self.player_affiliation_id, self.config.soldier_species
            )
            >= self.config.min_soldiers_before_defense
        )

    def on_phase_changed(
        self,
        prev: GamePhase,
        new: GamePhase,
        world: "World",
        bridge: "SimBridge | None",
        state: "GameState",
    ) -> list[GameMessage]:
        messages: list[GameMessage] = []
        if new is GamePhase.DEFENSE and prev is not GamePhase.DEFENSE:
            messages.extend(self._on_enter_defense(world, bridge, state))
        elif prev is GamePhase.DEFENSE and new is not GamePhase.DEFENSE:
            messages.extend(self._on_leave_defense(world, bridge, state))
        if new is GamePhase.DEVELOPMENT and prev in (GamePhase.STORY, GamePhase.DEFENSE):
            messages.extend(self._on_resume_development(world, bridge, state))
        return messages

    def on_tick(
        self,
        world: "World",
        bridge: "SimBridge | None",
        phase_controller: "PhaseController",
        state: "GameState",
    ) -> list[GameMessage]:
        if phase_controller.phase is not GamePhase.DEFENSE:
            return []
        return self._tick_defense(world, bridge, state)

    def _on_enter_defense(
        self,
        world: "World",
        bridge: "SimBridge | None",
        state: "GameState",
    ) -> list[GameMessage]:
        self._reproduction_profile_id = resolve_queen_reproduction_profile(state)
        self._queen_combat_active = False
        soldiers = count_alive_soldiers(
            world, self.player_affiliation_id, self.config.soldier_species
        )
        return [
            GameMessage(
                text=f"防衛開始: 兵隊アリ {soldiers} 匹が戦線に投入されました。",
                source="phase",
                priority=3,
            )
        ]

    def _on_leave_defense(
        self,
        world: "World",
        bridge: "SimBridge | None",
        state: "GameState",
    ) -> list[GameMessage]:
        msgs: list[GameMessage] = []
        if self._deactivate_queen_combat(world, bridge):
            msgs.append(
                GameMessage(
                    text="女王の緊急戦闘モードを終了しました。",
                    source="phase",
                    priority=2,
                )
            )
        queen = find_colony_queen(world, self.player_affiliation_id)
        if queen is not None and bridge is not None:
            # After emergency combat, force the queen back into the nest and keep her there.
            # We restore her reproduction profile (food + eggs) and then enter shelter so
            # she doesn't wander on the surface.
            profile = resolve_queen_reproduction_profile(state)
            self._apply_queen_profile(bridge, queen, profile, mode="replace")
            try:
                from src.sim.commands import EnterCreatureShelter

                bridge.execute(EnterCreatureShelter(creature_id=id(queen)))
            except Exception:
                pass
            msgs.append(
                GameMessage(
                    text="女王が巣へ戻り、休息します。",
                    source="phase",
                    priority=2,
                )
            )
        return msgs

    def _on_resume_development(
        self,
        world: "World",
        bridge: "SimBridge | None",
        state: "GameState",
    ) -> list[GameMessage]:
        profile = resolve_queen_reproduction_profile(state)
        self._reproduction_profile_id = profile
        queen = find_colony_queen(world, self.player_affiliation_id)
        if queen is None or bridge is None:
            return []
        # During story the sim is paused, so the queen cannot physically move back
        # into shelter. If we replace the mind immediately, we can drop SeekShelter
        # and the queen stays outside. Merge keeps the current "return to nest"
        # actions until she settles, while enabling reproduction actions again.
        self._apply_queen_profile(bridge, queen, profile, mode="merge")
        return [
            GameMessage(
                text="開発フェーズ: 女王が産卵体制に戻りました。",
                source="phase",
                priority=2,
            )
        ]

    def _tick_defense(
        self,
        world: "World",
        bridge: "SimBridge | None",
        state: "GameState",
    ) -> list[GameMessage]:
        if bridge is None:
            return []
        soldiers = count_alive_soldiers(
            world, self.player_affiliation_id, self.config.soldier_species
        )
        if soldiers > 0:
            return []
        if self._queen_combat_active:
            return []
        queen = find_colony_queen(world, self.player_affiliation_id)
        if queen is None or not queen.alive:
            return []
        if self._activate_queen_combat(world, bridge, queen):
            return [
                GameMessage(
                    text="兵隊アリが全滅しました。女王が自ら戦線に出ます。",
                    source="phase",
                    priority=5,
                )
            ]
        return []

    def _activate_queen_combat(self, world: "World", bridge, queen) -> bool:
        self._saved_queen_max_hp = float(queen.max_hp)
        self._saved_queen_hp = float(queen.hp)
        self._saved_queen_base_size = float(queen.traits.get("base_size", 22.0))
        queen.max_hp = self.config.queen_combat_max_hp
        queen.hp = self.config.queen_combat_max_hp
        queen.traits["base_size"] = self.config.queen_combat_base_size
        self._eject_queen_from_shelter(queen)
        ok = self._apply_queen_profile(bridge, queen, self.config.queen_combat_profile)
        self._queen_combat_active = ok
        return ok

    def _deactivate_queen_combat(self, world: "World", bridge) -> bool:
        if not self._queen_combat_active:
            return False
        queen = find_colony_queen(world, self.player_affiliation_id)
        if queen is not None:
            if self._saved_queen_max_hp is not None:
                queen.max_hp = self._saved_queen_max_hp
            if self._saved_queen_hp is not None:
                queen.hp = min(queen.max_hp, self._saved_queen_hp)
            if self._saved_queen_base_size is not None:
                queen.traits["base_size"] = self._saved_queen_base_size
        self._queen_combat_active = False
        self._saved_queen_max_hp = None
        self._saved_queen_hp = None
        self._saved_queen_base_size = None
        return True

    @staticmethod
    def _eject_queen_from_shelter(queen) -> None:
        from src.sim.shelter.state import clear_creature_shelter, is_creature_sheltered

        if not is_creature_sheltered(queen):
            return
        clear_creature_shelter(queen)
        from src.game.shelter_helpers import _restore_mind_after_shelter

        _restore_mind_after_shelter(queen)

    @staticmethod
    def _apply_queen_profile(bridge, queen, profile_id: str, *, mode: str = "replace") -> bool:
        from src.game.command_builder import apply_mind_profile

        return apply_mind_profile(bridge, queen, profile_id, mode=mode)
