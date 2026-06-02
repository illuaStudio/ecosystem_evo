"""開発 / 防衛 / ストーリー フェーズの遷移。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.game.game_message import GameMessage
from src.game.phases import GamePhase, PhaseConfig, phase_config_from_dict
from src.game.wave_director import WaveDirector

if TYPE_CHECKING:
    from src.sim.bridge import SimBridge
    from src.sim.systems.world import World


@dataclass
class PhaseController:
    config: PhaseConfig = field(default_factory=PhaseConfig)
    player_affiliation_id: str = "red_ant"
    phase: GamePhase = GamePhase.DEVELOPMENT
    phase_ticks: int = 0
    story_text: str = ""
    _story_acknowledged: bool = False
    _next_wave_index: int = 0
    _waves_cycled: bool = False

    @classmethod
    def from_config(cls, game_config: dict | None) -> "PhaseController":
        data = dict(game_config or {})
        affiliation_id = str(data.get("player_affiliation_id", "red_ant"))
        return cls(
            config=phase_config_from_dict(data.get("phases")),
            player_affiliation_id=affiliation_id,
        )

    def reset(self) -> None:
        self.phase = GamePhase.DEVELOPMENT
        self.phase_ticks = 0
        self.story_text = ""
        self._story_acknowledged = False
        self._next_wave_index = 0
        self._waves_cycled = False

    def should_run_sim(self) -> bool:
        return self.phase is not GamePhase.STORY

    @property
    def story_pending(self) -> bool:
        return self.phase is GamePhase.STORY and bool(self.story_text)

    @property
    def next_wave_index(self) -> int:
        return self._next_wave_index

    @property
    def waves_cycled(self) -> bool:
        return self._waves_cycled

    def acknowledge_story(self) -> None:
        if self.phase is GamePhase.STORY:
            self._story_acknowledged = True

    def request_start_defense(self, wave_director: WaveDirector) -> bool:
        if self.phase is not GamePhase.DEVELOPMENT:
            return False
        if wave_director.wave_index >= 0 and wave_director.wave_active:
            return False
        if self._next_wave_index >= len(wave_director.waves):
            return False
        return True

    def on_tick(
        self,
        world: "World",
        bridge: "SimBridge | None",
        wave_director: WaveDirector,
    ) -> list[GameMessage]:
        self.phase_ticks += 1
        messages: list[GameMessage] = []

        if self.phase is GamePhase.DEVELOPMENT:
            messages.extend(self._tick_development(wave_director))
        elif self.phase is GamePhase.DEFENSE:
            messages.extend(self._tick_defense(world, bridge, wave_director))
        elif self.phase is GamePhase.STORY:
            messages.extend(self._tick_story(wave_director))

        return messages

    def start_defense_wave(self, wave_director: WaveDirector, wave_index: int | None = None) -> list[GameMessage]:
        idx = self._next_wave_index if wave_index is None else wave_index
        if idx < 0 or idx >= len(wave_director.waves):
            return []
        self.phase = GamePhase.DEFENSE
        self.phase_ticks = 0
        return wave_director.begin_wave(idx)

    def _tick_development(self, wave_director: WaveDirector) -> list[GameMessage]:
        if not self.config.auto_start_defense:
            return []
        if self._next_wave_index >= len(wave_director.waves):
            return []
        if self.phase_ticks < self.config.development_ticks_before_defense:
            return []
        return self.start_defense_wave(wave_director)

    def _tick_defense(
        self,
        world: "World",
        bridge: "SimBridge | None",
        wave_director: WaveDirector,
    ) -> list[GameMessage]:
        wave_messages, cleared = wave_director.tick(world, bridge)
        messages = list(wave_messages)
        if cleared:
            wave = wave_director.current_wave
            self.story_text = wave.story_on_clear if wave is not None else ""
            self.phase = GamePhase.STORY
            self.phase_ticks = 0
            self._story_acknowledged = False
            self._next_wave_index = wave_director.wave_index + 1
        return messages

    def _tick_story(self, wave_director: WaveDirector) -> list[GameMessage]:
        if not self.config.auto_resume_after_story:
            if self._story_acknowledged:
                return self._enter_development(wave_director)
            return []
        if self._story_acknowledged or self.phase_ticks >= self.config.story_ticks_before_resume:
            return self._enter_development(wave_director)
        return []

    def on_player_defeated(self, wave_director: WaveDirector) -> list[GameMessage]:
        """プレイヤー勢力敗北時: 防衛を中断しストーリーフェーズへ。"""
        if self.phase is not GamePhase.DEFENSE:
            return []
        wave_director.abort_wave()
        self.story_text = self.config.story_on_defeat
        self.phase = GamePhase.STORY
        self.phase_ticks = 0
        self._story_acknowledged = False
        msgs: list[GameMessage] = [
            GameMessage(
                text=self.story_text,
                source="story",
                priority=5,
            )
        ]
        return msgs

    def _enter_development(self, wave_director: WaveDirector) -> list[GameMessage]:
        msgs: list[GameMessage] = []
        if (
            self.config.cycle_waves
            and self._next_wave_index >= len(wave_director.waves)
            and len(wave_director.waves) > 0
        ):
            self._next_wave_index = 0
            self._waves_cycled = True
            msgs.append(
                GameMessage(
                    text="全ウェーブを撃退しました。次の襲撃に備え、開発フェーズが再開しました。",
                    source="phase",
                    priority=3,
                )
            )
        self.phase = GamePhase.DEVELOPMENT
        self.phase_ticks = 0
        self.story_text = ""
        self._story_acknowledged = False
        if not msgs and self._next_wave_index > 0:
            msgs.append(
                GameMessage(
                    text="開発フェーズに戻りました。",
                    source="phase",
                    priority=2,
                )
            )
        return msgs
